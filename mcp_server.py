"""
StudyVault MCP Server

Tools:
  start_study_plan(pdf_path, vault_path, ...)  → extract topics, pause for review
  approve_topics(thread_id, ...)               → resume pipeline to completion
  get_status(thread_id)                        → check what stage a run is at

Resources:
  vault://topics/{thread_id}  → formatted topic list for a session

Session state is stored in the LangGraph MemorySaver checkpointer —
no parallel in-memory dict needed. If the process restarts mid-run,
swap MemorySaver for SqliteSaver and state persists across restarts.

Add to Claude Desktop config:
  {
    "mcpServers": {
      "studyvault": {
        "command": "python",
        "args": ["/path/to/study-vault-gen/mcp_server.py"]
      }
    }
  }
"""

import json
import uuid
from typing import Optional

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    raise ImportError("Run: pip install mcp")

from src.graph import build_graph, run_mcp_start, run_mcp_resume
from src.graph_state import default_state

mcp = FastMCP("StudyVault")

# One shared graph instance — its MemorySaver holds all session checkpoints
_graph = build_graph(interrupt_at_review=True)


def _get_checkpoint(thread_id: str) -> Optional[dict]:
    """Read the latest checkpointed state for a thread."""
    thread = {"configurable": {"thread_id": thread_id}}
    snapshot = _graph.get_state(thread)
    return snapshot.values if snapshot else None


# ── Tool: start_study_plan ────────────────────────────────────────────────── #

@mcp.tool()
def start_study_plan(
    pdf_path:          str,
    vault_path:        str,
    total_days:        int  = 14,
    hours_per_day:     int  = 2,
    skill_level:       str  = "beginner",
    goal:              str  = "practical_project",
    learning_style:    str  = "mixed",
    llm_provider:      str  = "ollama",
    llm_model:         str  = "llama3.1",
    ollama_url:        str  = "http://localhost:11434",
    include_quizzes:   bool = True,
    include_summaries: bool = True,
) -> str:
    """
    Start generating a personalized Obsidian study vault from a PDF.

    Runs until topics are extracted, then pauses for your review.
    Returns a thread_id and the full topic list.

    After reviewing, call approve_topics(thread_id, ...) to continue.

    Args:
        pdf_path:       Full path to the PDF file
        vault_path:     Full path to target Obsidian vault folder
        total_days:     Days to complete the plan
        hours_per_day:  Study hours per day
        skill_level:    beginner | basics | intermediate | advanced
        goal:           exam_prep | practical_project | deep_understanding | quick_overview
        learning_style: theory_first | examples_first | mixed
        llm_provider:   openai | ollama
        llm_model:      e.g. gpt-4o, llama3.1, qwen3:4b
        ollama_url:     Ollama server URL
        include_quizzes:    Add quiz questions to each note
        include_summaries:  Add TL;DR to each note
    """
    thread_id = str(uuid.uuid4())[:8]

    user_profile = {
        "total_days":        total_days,
        "hours_per_day":     hours_per_day,
        "total_hours":       total_days * hours_per_day,
        "skill_level":       skill_level,
        "goal":              goal,
        "learning_style":    learning_style,
        "hard_topics":       [],
        "easy_topics":       [],
        "include_quizzes":   include_quizzes,
        "include_summaries": include_summaries,
    }

    state = default_state(
        pdf_path=    pdf_path,
        vault_path=  vault_path,
        llm_provider=llm_provider,
        llm_model=   llm_model,
        ollama_url=  ollama_url,
        user_profile=user_profile,
    )

    try:
        result = run_mcp_start(state, thread_id)
    except Exception as e:
        return json.dumps({"error": str(e), "thread_id": thread_id})

    if result.get("error"):
        return json.dumps({"error": result["error"], "thread_id": thread_id})

    topics = result.get("topics", [])

    return json.dumps({
        "thread_id": thread_id,
        "status":    "awaiting_review",
        "message":   f"Extracted {len(topics)} topics. Review and call approve_topics().",
        "topics": [
            {
                "number":          i + 1,
                "id":              t["id"],
                "title":           t["title"],
                "difficulty":      t.get("difficulty", "intermediate"),
                "estimated_hours": t.get("estimated_hours", 1.5),
                "description":     t.get("description", ""),
            }
            for i, t in enumerate(topics)
        ],
        "next_step": "Call approve_topics(thread_id='{thread_id}', ...) to build your vault.".format(thread_id=thread_id),
    }, indent=2)


# ── Tool: approve_topics ──────────────────────────────────────────────────── #

@mcp.tool()
def approve_topics(
    thread_id:        str,
    approved_indices: Optional[str] = None,
    hard_indices:     Optional[str] = None,
    easy_indices:     Optional[str] = None,
) -> str:
    """
    Resume the pipeline after reviewing topics.

    Args:
        thread_id:        From start_study_plan()
        approved_indices: Comma-separated topic numbers to keep (empty = keep all)
                          e.g. "1,2,3,5,8"
        hard_indices:     Numbers of hard topics — get more time and depth
                          e.g. "3,7"
        easy_indices:     Numbers of easy topics — faster pace
                          e.g. "1,2"
    """
    # Read current state from checkpointer (no separate session dict needed)
    checkpoint = _get_checkpoint(thread_id)
    if not checkpoint:
        return json.dumps({
            "error": f"No session for thread_id '{thread_id}'. Call start_study_plan() first."
        })

    all_topics   = checkpoint.get("topics", [])
    user_profile = dict(checkpoint.get("user_profile", {}))

    # Parse approved
    if approved_indices and approved_indices.strip():
        idxs     = {int(x.strip()) - 1 for x in approved_indices.split(",") if x.strip().isdigit()}
        approved = [t for i, t in enumerate(all_topics) if i in idxs]
    else:
        approved = list(all_topics)

    def _titles(raw: Optional[str]) -> list:
        if not raw:
            return []
        return [
            all_topics[int(x.strip()) - 1]["title"]
            for x in raw.split(",")
            if x.strip().isdigit() and 0 < int(x.strip()) <= len(all_topics)
        ]

    hard = _titles(hard_indices)
    easy = _titles(easy_indices)
    if hard:
        user_profile["hard_topics"] = list(set(user_profile.get("hard_topics", []) + hard))
    if easy:
        user_profile["easy_topics"] = list(set(user_profile.get("easy_topics", []) + easy))

    try:
        final = run_mcp_resume(thread_id, approved, user_profile)
    except Exception as e:
        return json.dumps({"error": str(e)})

    if final.get("error"):
        return json.dumps({"error": final["error"]})

    written = final.get("written_files", [])
    return json.dumps({
        "status":        "complete",
        "vault_path":    checkpoint.get("vault_path", ""),
        "files_written": len(written),
        "preview":       written[:8],
        "message":       f"✅ Vault created with {len(written)} files. Open in Obsidian!",
    }, indent=2)


# ── Tool: get_status ──────────────────────────────────────────────────────── #

@mcp.tool()
def get_status(thread_id: str) -> str:
    """Check the current status of a pipeline run."""
    state = _get_checkpoint(thread_id)
    if not state:
        return json.dumps({"error": f"No session: {thread_id}"})

    return json.dumps({
        "thread_id":    thread_id,
        "status":       state.get("status", "unknown"),
        "topics_count": len(state.get("topics", [])),
        "days_count":   len(state.get("days", [])),
        "notes_count":  len(state.get("notes_map", {})),
        "error":        state.get("error", ""),
    }, indent=2)


# ── Resource: vault://topics/{thread_id} ──────────────────────────────────── #

@mcp.resource("vault://topics/{thread_id}")
def resource_topics(thread_id: str) -> str:
    """Formatted topic list for a session — readable by the MCP client."""
    state = _get_checkpoint(thread_id)
    if not state:
        return f"No session: {thread_id}"

    topics = state.get("topics", [])
    lines  = [f"# Topics ({len(topics)} total)\n"]
    colors = {"beginner": "🟢", "intermediate": "🟡", "advanced": "🔴"}
    for i, t in enumerate(topics, 1):
        icon = colors.get(t.get("difficulty", "intermediate"), "⚪")
        lines.append(
            f"{i:2d}. {icon} **{t['title']}**"
            f" — ~{t.get('estimated_hours', 1.5)}h"
        )
        if t.get("description"):
            lines.append(f"    {t['description']}")
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
