"""
LangGraph state schema.

Split into InputConfig (static) + PipelineState (mutable).
This makes it clear what's config vs. what's pipeline data,
and keeps things clean as we add new input sources.
"""

from typing import Annotated
from typing_extensions import TypedDict
import operator


class InputConfig(TypedDict):
    """Set once at pipeline start. Nodes read but never write these."""
    pdf_path:     str
    vault_path:   str
    llm_provider: str
    llm_model:    str
    ollama_url:   str
    user_profile: dict   # UserProfile.to_dict() — serialisable for checkpointing


class PipelineState(InputConfig):
    """
    Full pipeline state. Annotated fields use reducers for parallel fan-in:
      raw_topics:  lists from parallel chunk nodes are concatenated
      chunks_done: ints are summed
      notes_map:   dicts are merged
    """
    # PDF
    pdf_text:        str
    pdf_metadata:    dict

    # Chunk extraction (parallel)
    raw_topics:      Annotated[list, operator.add]
    chunks_done:     Annotated[int,  operator.add]
    total_chunks:    int

    # After dedup + merge
    topics:          list
    subject:         str
    description:     str

    # After human review
    approved_topics: list

    # Schedule
    days:            list

    # Notes (parallel)
    notes_map:       Annotated[dict, lambda a, b: {**a, **b}]

    # Output + control
    written_files:   list
    status:          str
    error:           str
    _mcp_mode:       bool


def default_state(
    pdf_path:     str,
    vault_path:   str,
    llm_provider: str,
    llm_model:    str,
    ollama_url:   str,
    user_profile: dict,
) -> dict:
    """Fully initialised state with safe defaults."""
    return {
        "pdf_path":       pdf_path,
        "vault_path":     vault_path,
        "llm_provider":   llm_provider,
        "llm_model":      llm_model,
        "ollama_url":     ollama_url,
        "user_profile":   user_profile,
        "pdf_text":       "",
        "pdf_metadata":   {},
        "raw_topics":     [],
        "chunks_done":    0,
        "total_chunks":   0,
        "topics":         [],
        "subject":        "",
        "description":    "",
        "approved_topics": [],
        "days":           [],
        "notes_map":      {},
        "written_files":  [],
        "status":         "starting",
        "error":          "",
        "_mcp_mode":      False,
    }
