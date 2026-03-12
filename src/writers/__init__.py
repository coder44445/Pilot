"""
Output writers for study materials
"""

from .vault import write_vault, get_index_path
from .anki import export_anki_deck
from .vault_merger import check_vault_exists, load_existing_topics, merge_topics, get_vault_subject

__all__ = [
    "write_vault",
    "get_index_path",
    "export_anki_deck",
    "check_vault_exists",
    "load_existing_topics",
    "merge_topics",
    "get_vault_subject",
]
