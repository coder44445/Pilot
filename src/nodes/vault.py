"""
Vault node: write_vault

Assembles final study_plan dict and delegates to vault_writer.
"""

from pathlib import Path

from src.vault_writer import write_vault as _write_vault
from src.display import console


def node_write_vault(state: dict) -> dict:
    """Write all Obsidian markdown files from pipeline state."""
    console.print("[dim]  node: write_vault[/dim]")

    topics = state.get("approved_topics") or state.get("topics", [])

    study_plan = {
        "subject":      state.get("subject", "Study Plan"),
        "description":  state.get("description", ""),
        "topics":       topics,
        "topic_map":    {t["id"]: t for t in topics},
        "days":         state.get("days", []),
        "notes_map":    state.get("notes_map", {}),
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
