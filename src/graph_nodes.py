"""
LangGraph nodes for the Pliot pipeline.

Each node:
  - Takes the full PilotState
  - Returns a PARTIAL dict (only the keys it updates)
  - Is a plain Python function — LangGraph handles the wiring

Node graph:
  extract_pdf
      ↓
  chunk_and_extract  (fan-out: one Send per chunk)
      ↓  (fan-in: all chunks merged via Annotated[list, operator.add])
  dedup_topics
      ↓
  human_review       ← INTERRUPT — waits for resume_after_review()
      ↓
  build_schedule
      ↓
  write_notes        (fan-out: one Send per topic)
      ↓  (fan-in: notes merged via Annotated[dict, ...])
  write_vault
"""

import re
import json
from pathlib import Path

from src.llm import LLMClient
from src.pdf_extractor import extract_pdf_text
from src.vault_writer import write_vault as _write_vault
from src.display import console
from src.planner import (
    EXTRACTION_SYSTEM, EXTRACTION_PROMPT,
    MERGE_SYSTEM, MERGE_PROMPT,
    PLANNING_SYSTEM, PLANNING_PROMPT,
    NOTES_SYSTEM, NOTES_PROMPT,
    _repair_json, _dedup_topics, CHUNK_SIZE_WORDS,
)


def _make_llm(state: dict) -> LLMClient:
    return LLMClient(
        provider=state.get("llm_provider", "ollama"),
        model=state.get("llm_model"),
        ollama_url=state.get("ollama_url", "http://localhost:11434"),
    )


# ── Node 1: extract_pdf ────────────────────────────────────────────────────── #

def node_extract_pdf(state: dict) -> dict:
    """Read PDF from disk, extract text and metadata."""
    console.print("[dim]  node: extract_pdf[/dim]")
    try:
        text, metadata = extract_pdf_text(Path(state["pdf_path"]))
        return {
            "pdf_text": text,
            "pdf_metadata": metadata,
            "status": "pdf_extracted",
        }
    except Exception as e:
        return {"error": str(e), "status": "failed"}


# ── Node 2: extract_chunk ─────────────────────────────────────────────────── #
# Called once PER CHUNK via LangGraph Send — runs in parallel

def node_extract_chunk(state: dict) -> dict:
    """
    Extract topics from a single text chunk.
    `state` here is the full graph state PLUS two extra keys injected by Send:
      - chunk_text: str
      - chunk_num:  int
    """
    chunk_text  = state["chunk_text"]
    chunk_num   = state["chunk_num"]
    total       = state["total_chunks"]
    metadata    = state.get("pdf_metadata", {})

    llm = _make_llm(state)
    try:
        response = llm.chat(
            system_prompt=EXTRACTION_SYSTEM,
            user_prompt=EXTRACTION_PROMPT.format(
                title=metadata.get("title", "Unknown"),
                chunk_num=chunk_num,
                total_chunks=total,
                text=chunk_text,
            ),
            json_mode=True,
        )
        parsed = _repair_json(response)
        topics = parsed.get("topics", [])
        console.print(f"  [dim]chunk {chunk_num}/{total}: {len(topics)} topics[/dim]")
    except Exception as e:
        console.print(f"  [yellow]chunk {chunk_num} failed: {e}[/yellow]")
        topics = []

    # operator.add merges all parallel raw_topics lists automatically
    return {
        "raw_topics": topics,
        "chunks_done": 1,
    }


# ── Node 3: dedup_topics ───────────────────────────────────────────────────── #

def node_dedup_topics(state: dict) -> dict:
    """Deduplicate raw topics from all chunks. LLM merge if > 20."""
    console.print("[dim]  node: dedup_topics[/dim]")

    all_topics = state.get("raw_topics", [])
    metadata   = state.get("pdf_metadata", {})
    llm        = _make_llm(state)

    console.print(f"  [dim]  raw: {len(all_topics)} → deduplicating...[/dim]")
    topics = _dedup_topics(all_topics)
    console.print(f"  [dim]  after dedup: {len(topics)}[/dim]")

    subject     = metadata.get("title", "Unknown")
    description = ""

    if len(topics) > 20:
        console.print("  [dim]  LLM merge pass...[/dim]")
        raw_list = "\n".join(f'- {t["title"]}: {t.get("description","")}' for t in topics)
        try:
            resp = llm.chat(
                system_prompt=MERGE_SYSTEM,
                user_prompt=MERGE_PROMPT.format(raw_topics=raw_list),
                json_mode=True,
            )
            merged = _repair_json(resp)
            if merged.get("topics"):
                topics      = merged["topics"]
                subject     = merged.get("subject", subject)
                description = merged.get("description", description)
                console.print(f"  [dim]  after merge: {len(topics)}[/dim]")
        except Exception as e:
            console.print(f"  [yellow]  merge skipped: {e}[/yellow]")

    # Normalise
    for i, t in enumerate(topics):
        t["id"] = f"t{i+1}"
        t.setdefault("title",          f"Topic {i+1}")
        t.setdefault("description",    "")
        t.setdefault("subtopics",      [])
        t.setdefault("estimated_hours", 1.5)
        t.setdefault("difficulty",     "intermediate")

    console.print(f"  [green]✓[/green] {len(topics)} unique topics")

    return {
        "topics":      topics,
        "subject":     subject,
        "description": description,
        "status":      "topics_extracted",
    }


# ── Node 4: human_review (INTERRUPT point) ────────────────────────────────── #

def node_human_review(state: dict) -> dict:
    """
    In CLI mode: interactive prompt.
    In MCP mode: this node sets status='awaiting_review' and the graph
    is interrupted here. The MCP client calls resume_after_review() to continue.
    """
    console.print("[dim]  node: human_review[/dim]")

    topics       = state.get("topics", [])
    user_profile = state.get("user_profile", {})
    is_mcp       = state.get("_mcp_mode", False)

    if is_mcp:
        # Signal to MCP caller that we're waiting
        return {
            "approved_topics": topics,   # default: all approved
            "status": "awaiting_review",
        }

    # CLI interactive mode (reuse existing logic from planner.py)
    from src.planner import review_topics
    approved = review_topics(topics, user_profile)

    return {
        "approved_topics": approved,
        "user_profile":    user_profile,   # may be mutated by review (hard/easy)
        "status":          "reviewed",
    }


# ── Node 5: build_schedule ────────────────────────────────────────────────── #

def node_build_schedule(state: dict) -> dict:
    """Generate day-by-day schedule from approved topics."""
    console.print("[dim]  node: build_schedule[/dim]")

    topics       = state.get("approved_topics", state.get("topics", []))
    user_profile = state.get("user_profile", {})
    llm          = _make_llm(state)

    topics_simple = "\n".join(
        f'- id: "{t["id"]}", title: "{t["title"]}", '
        f'difficulty: {t.get("difficulty","intermediate")}, '
        f'hours: {t.get("estimated_hours",1.5)}'
        for t in topics
    )

    try:
        resp = llm.chat(
            system_prompt=PLANNING_SYSTEM,
            user_prompt=PLANNING_PROMPT.format(
                total_days=user_profile.get("total_days", 14),
                hours_per_day=user_profile.get("hours_per_day", 2),
                skill_level=user_profile.get("skill_level", "beginner"),
                goal=user_profile.get("goal", "practical_project"),
                learning_style=user_profile.get("learning_style", "mixed"),
                hard_topics=", ".join(user_profile.get("hard_topics", [])) or "none",
                easy_topics=", ".join(user_profile.get("easy_topics", [])) or "none",
                topics_simple=topics_simple,
            ),
            json_mode=True,
        )
        schedule = _repair_json(resp)
        days = schedule.get("days", [])
        console.print(f"  [green]✓[/green] {len(days)} days scheduled")
        return {"days": days, "status": "scheduled"}
    except Exception as e:
        return {"error": str(e), "status": "failed"}


# ── Node 6: write_note ────────────────────────────────────────────────────── #
# Called once PER TOPIC via LangGraph Send — runs in parallel

def node_write_note(state: dict) -> dict:
    """
    Write notes for a single topic.
    Extra keys injected by Send:
      - topic: dict  (the full topic object)
    """
    topic        = state["topic"]
    user_profile = state.get("user_profile", {})
    days         = state.get("days", [])
    llm          = _make_llm(state)

    tid = topic["id"]

    # Find depth + time from schedule
    depth      = "standard"
    time_alloc = topic.get("estimated_hours", 1.5)
    for day in days:
        for t in day.get("topics", []):
            if t.get("topic_id") == tid:
                depth      = t.get("depth", "standard")
                time_alloc = t.get("time_allocation", time_alloc)
                break

    title_lower = topic["title"].lower()
    if any(h.lower() in title_lower for h in user_profile.get("hard_topics", [])):
        hard_easy = "HARD topic: go extra deep, more examples."
    elif any(e.lower() in title_lower for e in user_profile.get("easy_topics", [])):
        hard_easy = "EASY topic: be concise, add practice exercises."
    else:
        hard_easy = ""

    tldr = "### TL;DR\n(one sentence)\n" if user_profile.get("include_summaries") else ""
    quiz = "### Quiz Yourself\n1. ?\n2. ?\n3. ?\n" if user_profile.get("include_quizzes") else ""

    try:
        notes = llm.chat(
            system_prompt=NOTES_SYSTEM,
            user_prompt=NOTES_PROMPT.format(
                topic_title=topic["title"],
                topic_description=topic.get("description", ""),
                subtopics=", ".join(topic.get("subtopics", [])),
                skill_level=user_profile.get("skill_level", "beginner"),
                goal=user_profile.get("goal", "practical_project"),
                learning_style=user_profile.get("learning_style", "mixed"),
                depth=depth,
                hard_easy_instruction=hard_easy,
                tldr_section=tldr,
                quiz_section=quiz,
                time_allocation=time_alloc,
            ),
        )
        console.print(f"  [dim]  ✓ {topic['title']}[/dim]")
    except Exception as e:
        notes = f"## {topic['title']}\n\n*Notes unavailable. Error: {e}*"
        console.print(f"  [yellow]  ⚠ {topic['title']}: {e}[/yellow]")

    # Annotated[dict, merge] will merge all {tid: notes} dicts from parallel nodes
    return {"notes_map": {tid: notes}}


# ── Node 7: write_vault ───────────────────────────────────────────────────── #

def node_write_vault(state: dict) -> dict:
    """Write all Obsidian markdown files."""
    console.print("[dim]  node: write_vault[/dim]")

    study_plan = {
        "subject":     state.get("subject", "Study Plan"),
        "description": state.get("description", ""),
        "topics":      state.get("approved_topics", state.get("topics", [])),
        "topic_map":   {t["id"]: t for t in state.get("approved_topics", state.get("topics", []))},
        "days":        state.get("days", []),
        "notes_map":   state.get("notes_map", {}),
        "user_profile": state.get("user_profile", {}),
        "pdf_metadata": state.get("pdf_metadata", {}),
    }

    try:
        written = _write_vault(
            Path(state["vault_path"]),
            study_plan,
            state.get("user_profile", {}),
            state.get("pdf_metadata", {}),
        )
        console.print(f"  [green]✓[/green] {len(written)} files written")
        return {"written_files": written, "status": "complete"}
    except Exception as e:
        return {"error": str(e), "status": "failed"}
