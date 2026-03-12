"""
Pilot MCP Server

LLM and default profile settings are read from pilot.config.yml.
Claude Desktop does not need to pass llm_provider, model, etc. —
they come from the config file automatically.

Tools:
  start_study_plan(pdf_path, vault_path, ...)  → extract topics, pause for review
  approve_topics(thread_id, ...)               → resume pipeline to completion
  get_status(thread_id)                        → check run stage

Resources:
  vault://topics/{thread_id}  → topic list for a session

Claude Desktop config (~/.config/claude/claude_desktop_config.json):
  {
    "mcpServers": {
      "pilot": {
        "command": "python",
        "args": ["C:/path/to/Pilot/mcp_server.py"]
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

from src.core.graph import run_mcp_start, run_mcp_resume, get_checkpoint_state
from src.core import default_state
from src.loaders import load_llm_config, load_default_profile, print_config_summary
from src.display import console

mcp = FastMCP("Pilot")

# Load config once at startup
_llm     = load_llm_config()
_profile = load_default_profile()
print_config_summary(console)


# ── Tool: start_study_plan

@mcp.tool()
def start_study_plan(
    pdf_path:       str,
    vault_path:     str,
    total_days:     Optional[int] = None,
    hours_per_day:  Optional[int] = None,
    skill_level:    Optional[str] = None,
    goal:           Optional[str] = None,
    learning_style: Optional[str] = None,
) -> str:
    """
    Start generating a personalized Obsidian study vault from a PDF.

    LLM settings (provider, model, ollama_url) come from pilot.config.yml.
    Profile settings default to pilot.config.yml but can be overridden here.

    Runs until topics are extracted, then pauses for your review.
    Call approve_topics() to continue after reviewing.

    Args:
        pdf_path:      Full path to the PDF file
        vault_path:    Full path to target Obsidian vault folder
        total_days:    Days to complete (default from config)
        hours_per_day: Study hours per day (default from config)
        skill_level:   beginner | basics | intermediate | advanced
        goal:          exam_prep | practical_project | deep_understanding | quick_overview
        learning_style: theory_first | examples_first | mixed
    """
    thread_id = str(uuid.uuid4())[:8]

    # Merge: config defaults ← per-call overrides
    profile = {
        **_profile,
        **({"total_days":     total_days}     if total_days     is not None else {}),
        **({"hours_per_day":  hours_per_day}  if hours_per_day  is not None else {}),
        **({"skill_level":    skill_level}    if skill_level    is not None else {}),
        **({"goal":           goal}           if goal           is not None else {}),
        **({"learning_style": learning_style} if learning_style is not None else {}),
    }
    profile["total_hours"] = int(profile["total_days"]) * int(profile["hours_per_day"])
    profile.setdefault("hard_topics", [])
    profile.setdefault("easy_topics", [])

    state = default_state(
        pdf_path=    pdf_path,
        vault_path=  vault_path,
        llm_provider=_llm["provider"],
        llm_model=   _llm["model"],
        ollama_url=  _llm["ollama_url"],
        user_profile=profile,
    )

    try:
        result = run_mcp_start(state, thread_id, vault_path)
    except Exception as e:
        return json.dumps({"error": str(e), "thread_id": thread_id})

    if result.get("error"):
        return json.dumps({"error": result["error"], "thread_id": thread_id})

    topics = result.get("topics", [])

    return json.dumps({
        "thread_id": thread_id,
        "status":    "awaiting_review",
        "llm":       f"{_llm['provider']} / {_llm['model']}",
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
        "next_step": f"Call approve_topics(thread_id='{thread_id}') to build your vault.",
    }, indent=2)


# Tool: approve_topics 

@mcp.tool()
def approve_topics(
    thread_id:        str,
    vault_path:       str,
    approved_indices: Optional[str] = None,
    hard_indices:     Optional[str] = None,
    easy_indices:     Optional[str] = None,
) -> str:
    """
    Resume the pipeline after reviewing topics.

    Args:
        thread_id:        From start_study_plan()
        vault_path:       Same vault_path used in start_study_plan()
        approved_indices: Comma-separated topic numbers to keep (empty = keep all)
        hard_indices:     Topic numbers that need extra depth e.g. "3,7"
        easy_indices:     Topic numbers to cover faster e.g. "1,2"
    """
    state = get_checkpoint_state(thread_id, vault_path)
    if not state:
        return json.dumps({
            "error": f"No session for thread_id '{thread_id}'. Call start_study_plan() first."
        })

    all_topics   = state.get("topics", [])
    user_profile = dict(state.get("user_profile", {}))

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
        final = run_mcp_resume(thread_id, vault_path, approved, user_profile)
    except Exception as e:
        return json.dumps({"error": str(e)})

    written = final.get("written_files", [])
    failed  = list(set(final.get("failed_nodes", [])))

    return json.dumps({
        "status":        "complete" if not failed else "complete_with_errors",
        "vault_path":    vault_path,
        "files_written": len(written),
        "failed_nodes":  failed,
        "preview":       written[:8],
        "message":       f"Vault created with {len(written)} files. Open in Obsidian!"
                         + (f" ({len(failed)} node(s) had errors)" if failed else ""),
    }, indent=2)


# Tool: get_status

@mcp.tool()
def get_status(thread_id: str, vault_path: str) -> str:
    """Check the current status of a pipeline run."""
    state = get_checkpoint_state(thread_id, vault_path)
    if not state:
        return json.dumps({"error": f"No session: {thread_id}"})

    return json.dumps({
        "thread_id":    thread_id,
        "status":       state.get("status", "unknown"),
        "llm":          f"{_llm['provider']} / {_llm['model']}",
        "topics_count": len(state.get("topics", [])),
        "days_count":   len(state.get("days", [])),
        "notes_count":  len(state.get("notes_map", {})),
        "failed_nodes": list(set(state.get("failed_nodes", []))),
    }, indent=2)


# Resource: vault://topics/{thread_id}

@mcp.resource("vault://topics/{thread_id}/{vault_path}")
def resource_topics(thread_id: str, vault_path: str) -> str:
    state = get_checkpoint_state(thread_id, vault_path)
    if not state:
        return f"No session: {thread_id}"

    topics = state.get("topics", [])
    icons  = {"beginner": "🟢", "intermediate": "🟡", "advanced": "🔴"}
    lines  = [f"# Topics — {state.get('subject', '')} ({len(topics)} total)\n"]
    for i, t in enumerate(topics, 1):
        icon = icons.get(t.get("difficulty", "intermediate"), "⚪")
        lines.append(f"{i:2d}. {icon} **{t['title']}** — ~{t.get('estimated_hours', 1.5)}h")
        if t.get("description"):
            lines.append(f"    {t['description']}")
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()