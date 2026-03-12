"""
Vault merger — merge new topics with existing vault without overwriting.

Supports re-running Pilot on an existing vault to add new topics while
preserving user's manual edits to existing notes.
"""

import re
from pathlib import Path
from typing import Dict, List, Tuple


def load_existing_topics(vault_path: Path) -> Dict[str, dict]:
    """
    Load existing topics from a vault's Notes/ folder.
    Returns {topic_id: {title, filename, ...}}.
    """
    topics = {}
    notes_dir = vault_path / "Notes"
    
    if not notes_dir.exists():
        return topics
    
    for note_file in notes_dir.glob("*.md"):
        # Parse front matter to extract metadata
        try:
            content = note_file.read_text(encoding="utf-8")
            match = re.search(r'topic_id: "([^"]+)"', content)
            if match:
                topic_id = match.group(1)
                topics[topic_id] = {
                    "id": topic_id,
                    "title": note_file.stem,
                    "filename": note_file.name,
                    "exists": True,
                }
        except Exception:
            pass
    
    return topics


def merge_topics(
    new_topics: List[dict],
    existing_topics: Dict[str, dict]
) -> Tuple[List[dict], List[str]]:
    """
    Merge new topics with existing ones.
    Returns (merged_topics, new_topic_ids).
    
    - Existing topics are preserved (not overwritten by LLM)
    - New topics are added
    - Duplicates are skipped
    """
    merged = {}
    
    # Add all existing topics first (preserve user edits)
    for topic_id, topic in existing_topics.items():
        merged[topic_id] = topic
    
    # Add new topics (or update if they don't exist in vault yet)
    new_ids = []
    for topic in new_topics:
        tid = topic.get("id")
        if tid not in merged:
            merged[tid] = topic
            new_ids.append(tid)
        else:
            # Update metadata but preserve the existing note file
            existing = merged[tid]
            merged[tid] = {
                **topic,
                "id": tid,
                "exists": existing.get("exists", False),
                "filename": existing.get("filename", ""),
            }
    
    return list(merged.values()), new_ids


def check_vault_exists(vault_path: Path) -> bool:
    """Check if a vault structure already exists."""
    return (vault_path / "Notes").exists() or (vault_path / "Days").exists()


def get_vault_subject(vault_path: Path) -> str:
    """
    Extract subject name from existing vault.
    Looks for subdirectory that contains Notes/ and Days/.
    """
    # Usually the structure is vault_path/SubjectName/Notes, Days, etc.
    for item in vault_path.iterdir():
        if item.is_dir() and (
            (item / "Notes").exists() or (item / "Days").exists()
        ):
            return item.name
    
    return vault_path.name
