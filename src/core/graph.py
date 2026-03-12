"""
Pilot LangGraph pipeline.

KEY BEHAVIOURS:
  1. Persistent checkpoints via SqliteSaver — survives process crashes/restarts
  2. SqliteSaver MUST be used as a context manager (with block) — fixed here
  3. Deterministic thread_id from pdf_path+vault_path — same inputs always resume
  4. Nodes are idempotent — skip themselves if output already in state
  5. Errors recorded in state, never stop the graph — @resilient_node handles retry
"""

import hashlib
from contextlib import contextmanager
from pathlib import Path

from langgraph.graph import StateGraph, END
from langgraph.types import Send

from .graph_state import PipelineState, STATUS_AWAITING_REVIEW
from src.utils.chunking import chunk_text
from src.nodes import (
    node_extract_pdf,
    node_extract_chunk,
    node_dedup_topics,
    node_human_review,
    node_build_schedule,
    node_write_note,
    node_write_vault,
)
from src.retry import summarise_errors
from src.display import console


# Thread ID 

def make_thread_id(pdf_path: str, vault_path: str) -> str:
    key = f"{Path(pdf_path).resolve()}::{Path(vault_path).resolve()}"
    return hashlib.md5(key.encode()).hexdigest()[:12]


# Checkpointer context manager

@contextmanager
def _checkpointer(vault_path: str):
    """
    Yield a checkpointer, properly opened and closed.

    SqliteSaver requires a context manager — calling methods on a closed
    connection raises sqlite3.ProgrammingError. This wrapper ensures it's
    always opened before use and closed after.

    Falls back to MemorySaver if langgraph-checkpoint-sqlite is not installed.
    """
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
        db_path = Path(vault_path) / ".pilot_checkpoints.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with SqliteSaver.from_conn_string(str(db_path)) as cp:
            yield cp
    except ImportError:
        console.print(
            "[yellow]  langgraph-checkpoint-sqlite not installed — "
            "using in-memory checkpoints (progress lost on restart)[/yellow]\n"
            "[dim]  Fix: pip install langgraph-checkpoint-sqlite[/dim]"
        )
        from langgraph.checkpoint.memory import MemorySaver
        yield MemorySaver()


# Routing

def _route_after_pdf(state: dict):
    if "extract_pdf" in state.get("failed_nodes", []):
        console.print("[red]  extract_pdf failed — cannot continue[/red]")
        return END
    if state.get("topics"):
        console.print("  [dim]topics already built — skipping chunk extraction[/dim]")
        return "dedup_topics"
    chunks = chunk_text(state["pdf_text"])
    console.print(f"  [dim]splitting into {len(chunks)} chunks[/dim]")
    return [
        Send("extract_chunk", {
            **state,
            "chunk_text":   chunk,
            "chunk_num":    i + 1,
            "total_chunks": len(chunks),
        })
        for i, chunk in enumerate(chunks)
    ]


def _route_after_chunk(state: dict):
    return "dedup_topics"


def _route_after_dedup(state: dict):
    if "dedup_topics" in state.get("failed_nodes", []) and not state.get("topics"):
        console.print("[red]  dedup_topics failed with no topics — cannot schedule[/red]")
        return END
    return "human_review"


def _route_after_review(state: dict):
    if state.get("status") == STATUS_AWAITING_REVIEW:
        return END
    return "build_schedule"


def _route_after_schedule(state: dict):
    if "build_schedule" in state.get("failed_nodes", []) and not state.get("days"):
        console.print("[yellow]  schedule failed — writing vault without day plan[/yellow]")
        return "write_vault"

    topics    = state.get("approved_topics") or state.get("topics", [])
    days      = state.get("days", [])
    notes_done = set(state.get("notes_map", {}).keys())

    scheduled_ids = {
        t.get("topic_id")
        for day in days
        for t in day.get("topics", [])
    } or {t["id"] for t in topics}

    pending = [
        t for t in topics
        if t["id"] in scheduled_ids and t["id"] not in notes_done
    ]

    if not pending:
        console.print("  [dim]all notes already written — skipping to vault[/dim]")
        return "write_vault"

    console.print(f"  [dim]writing {len(pending)} notes ({len(notes_done)} already done)[/dim]")
    return [Send("write_note", {**state, "topic": t}) for t in pending]


def _route_after_note(state: dict):
    return "write_vault"


# Graph builder

def _build_graph(checkpointer, interrupt_at_review: bool = False):
    g = StateGraph(PipelineState)

    g.add_node("extract_pdf",    node_extract_pdf)
    g.add_node("extract_chunk",  node_extract_chunk)
    g.add_node("dedup_topics",   node_dedup_topics)
    g.add_node("human_review",   node_human_review)
    g.add_node("build_schedule", node_build_schedule)
    g.add_node("write_note",     node_write_note)
    g.add_node("write_vault",    node_write_vault)

    g.set_entry_point("extract_pdf")

    g.add_conditional_edges("extract_pdf",    _route_after_pdf)
    g.add_conditional_edges("extract_chunk",  lambda s: _route_after_chunk(s))
    g.add_conditional_edges("dedup_topics",   _route_after_dedup)
    g.add_conditional_edges("human_review",   _route_after_review)
    g.add_conditional_edges("build_schedule", _route_after_schedule)
    g.add_conditional_edges("write_note",     _route_after_note)
    g.add_edge("write_vault", END)

    kwargs = {"checkpointer": checkpointer}
    if interrupt_at_review:
        kwargs["interrupt_before"] = ["human_review"]

    return g.compile(**kwargs)


# CLI runner

def run_cli(initial_state: dict, force_restart: bool = False) -> dict:
    vault_path = initial_state["vault_path"]
    thread_id  = make_thread_id(initial_state["pdf_path"], vault_path)
    thread_cfg = {"configurable": {"thread_id": thread_id}}

    with _checkpointer(vault_path) as cp:
        graph = _build_graph(cp, interrupt_at_review=False)

        existing = graph.get_state(thread_cfg)
        if existing and existing.values and not force_restart:
            status = existing.values.get("status", "unknown")
            if status == "complete":
                console.print(
                    f"\n[green]✓ Already completed.[/green]"
                    f"\n[dim]  Use --restart to regenerate.[/dim]"
                )
                return existing.values
            console.print(
                f"\n[bold yellow]↩ Resuming[/bold yellow] "
                f"[dim](status: {status}, thread: {thread_id})[/dim]"
            )
            input_state = None
        else:
            if force_restart:
                console.print("[dim]  force_restart — ignoring checkpoint[/dim]")
            console.print(f"[dim]  checkpoint thread: {thread_id}[/dim]")
            input_state = initial_state

        final = None
        try:
            for step in graph.stream(input_state, thread_cfg, stream_mode="values"):
                final = step
        except KeyboardInterrupt:
            console.print(
                "\n[yellow]Interrupted — progress saved.[/yellow]"
                "\n[dim]Rerun the same command to resume.[/dim]"
            )
            snapshot = graph.get_state(thread_cfg)
            return snapshot.values if snapshot else {}

    final = final or {}
    summarise_errors(final)
    return final


# MCP runners

def run_mcp_start(initial_state: dict, thread_id: str, vault_path: str) -> dict:
    thread_cfg = {"configurable": {"thread_id": thread_id}}
    with _checkpointer(vault_path) as cp:
        graph = _build_graph(cp, interrupt_at_review=True)
        final = None
        for step in graph.stream(
            {**initial_state, "_mcp_mode": True},
            thread_cfg,
            stream_mode="values",
        ):
            final = step
    return final or {}


def run_mcp_resume(thread_id: str, vault_path: str, approved_topics: list, user_profile: dict) -> dict:
    thread_cfg = {"configurable": {"thread_id": thread_id}}
    with _checkpointer(vault_path) as cp:
        graph = _build_graph(cp, interrupt_at_review=True)
        graph.update_state(
            thread_cfg,
            {"approved_topics": approved_topics, "user_profile": user_profile, "status": "reviewed"},
            as_node="human_review",
        )
        final = None
        for step in graph.stream(None, thread_cfg, stream_mode="values"):
            final = step
    return final or {}


def get_checkpoint_state(thread_id: str, vault_path: str) -> dict:
    with _checkpointer(vault_path) as cp:
        graph    = _build_graph(cp)
        snapshot = graph.get_state({"configurable": {"thread_id": thread_id}})
    return snapshot.values if snapshot else {}