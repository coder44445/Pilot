"""
Vault writing node — resilient, idempotent.
Skips files already written on disk.
"""

from pathlib import Path
from src.vault_writer import write_vault as _write_vault
from src.retry import resilient_node, node_already_done
from src.display import console


@resilient_node("write_vault", max_retries=2)
def node_write_vault(state: dict) -> dict:
    if node_already_done(state, "write_vault", "written_files"):
        return {"status": "complete"}

    console.print("[dim]  node: write_vault[/dim]")

    topics = state.get("approved_topics") or state.get("topics", [])
    study_plan = {
        "subject":     state.get("subject", "Study Plan"),
        "description": state.get("description", ""),
        "topics":      topics,
        "topic_map":   {t["id"]: t for t in topics},
        "days":        state.get("days", []),
        "notes_map":   state.get("notes_map", {}),
    }

    # Check if in merge mode
    merge_mode = state.get("_merge_mode", False)
    existing_ids = state.get("_existing_topic_ids", [])

    written = _write_vault(
        Path(state["vault_path"]),
        study_plan,
        state.get("user_profile", {}),
        state.get("pdf_metadata", {}),
        merge_mode=merge_mode,
        existing_topic_ids=existing_ids,
    )

    if not written:
        raise ValueError("write_vault produced no files — will retry")

    console.print(f"  [green]✓[/green] {len(written)} files written")
    return {"written_files": written, "status": "complete"}