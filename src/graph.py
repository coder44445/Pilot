"""
StudyVault LangGraph pipeline — topology only.

This file contains ONLY:
  - Node registration
  - Edge routing functions
  - Graph compilation

Zero business logic lives here. All logic is in src/nodes/*.py
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Send

from src.graph_state import PipelineState
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


# ── Routing functions ──────────────────────────────────────────────────────── #

def _route_extract_pdf(state: dict):
    """Fan-out: one Send per text chunk."""
    if state.get("error"):
        return END
    chunks = chunk_text(state["pdf_text"])
    return [
        Send("extract_chunk", {
            **state,
            "chunk_text":   chunk,
            "chunk_num":    i + 1,
            "total_chunks": len(chunks),
        })
        for i, chunk in enumerate(chunks)
    ]


def _route_dedup(state: dict):
    if state.get("error"):
        return END
    return "human_review"


def _route_review(state: dict):
    """
    In MCP mode the graph interrupted before this node.
    After resume, status will be 'reviewed' — continue to schedule.
    """
    if state.get("status") == "awaiting_review":
        return END
    if state.get("error"):
        return END
    return "build_schedule"


def _route_schedule(state: dict):
    """Fan-out: one Send per topic that appears in the schedule."""
    if state.get("error"):
        return END

    topics = state.get("approved_topics") or state.get("topics", [])
    days   = state.get("days", [])

    scheduled_ids = {
        t.get("topic_id")
        for day in days
        for t in day.get("topics", [])
        if t.get("topic_id")
    } or {t["id"] for t in topics}

    relevant = [t for t in topics if t["id"] in scheduled_ids]
    return [Send("write_note", {**state, "topic": t}) for t in relevant]


def _always_vault(state: dict):
    return "write_vault"


def _always_end(state: dict):
    return END


# ── Graph builder ──────────────────────────────────────────────────────────── #

def build_graph(interrupt_at_review: bool = False):
    """
    Compile the StudyVault graph.

    Args:
        interrupt_at_review: True in MCP mode — graph pauses before
                             human_review and waits for resume.
    """
    g = StateGraph(PipelineState)

    g.add_node("extract_pdf",    node_extract_pdf)
    g.add_node("extract_chunk",  node_extract_chunk)
    g.add_node("dedup_topics",   node_dedup_topics)
    g.add_node("human_review",   node_human_review)
    g.add_node("build_schedule", node_build_schedule)
    g.add_node("write_note",     node_write_note)
    g.add_node("write_vault",    node_write_vault)

    g.set_entry_point("extract_pdf")

    g.add_conditional_edges("extract_pdf",    _route_extract_pdf)
    g.add_conditional_edges("extract_chunk",  lambda s: "dedup_topics")
    g.add_conditional_edges("dedup_topics",   _route_dedup)
    g.add_conditional_edges("human_review",   _route_review)
    g.add_conditional_edges("build_schedule", _route_schedule)
    g.add_conditional_edges("write_note",     _always_vault)
    g.add_edge("write_vault", END)

    kwargs = {"checkpointer": MemorySaver()}
    if interrupt_at_review:
        kwargs["interrupt_before"] = ["human_review"]

    return g.compile(**kwargs)


# ── Convenience runners ────────────────────────────────────────────────────── #

def run_cli(initial_state: dict) -> dict:
    """Run full pipeline (CLI mode, interactive review)."""
    graph  = build_graph(interrupt_at_review=False)
    thread = {"configurable": {"thread_id": "cli"}}
    final  = None
    for step in graph.stream(initial_state, thread, stream_mode="values"):
        final = step
    return final or {}


def run_mcp_start(initial_state: dict, thread_id: str) -> dict:
    """Start pipeline in MCP mode. Pauses before human_review."""
    graph  = build_graph(interrupt_at_review=True)
    thread = {"configurable": {"thread_id": thread_id}}
    final  = None
    for step in graph.stream(
        {**initial_state, "_mcp_mode": True},
        thread,
        stream_mode="values",
    ):
        final = step
    return final or {}


def run_mcp_resume(thread_id: str, approved_topics: list, user_profile: dict) -> dict:
    """Resume pipeline after human review in MCP mode."""
    graph  = build_graph(interrupt_at_review=True)
    thread = {"configurable": {"thread_id": thread_id}}

    graph.update_state(
        thread,
        {
            "approved_topics": approved_topics,
            "user_profile":    user_profile,
            "status":          "reviewed",
        },
        as_node="human_review",
    )

    final = None
    for step in graph.stream(None, thread, stream_mode="values"):
        final = step
    return final or {}
