"""
LangGraph state schema.

InputConfig  — static config, set once, never mutated by nodes
PipelineState — full state including all mutable pipeline data

Error/retry fields:
  node_errors:    dict of {node_name: [error_str, ...]} — full history per node
  failed_nodes:   set-as-list of node names that failed this run
  retry_counts:   dict of {node_name: int} — how many times retried
  status:         current pipeline stage (see STATUS_* constants)
"""

from pydantic import BaseModel
from typing import Annotated
from typing_extensions import TypedDict
import operator


# Status constants

STATUS_STARTING         = "starting"
STATUS_PDF_EXTRACTED    = "pdf_extracted"
STATUS_TOPICS_EXTRACTED = "topics_extracted"
STATUS_AWAITING_REVIEW  = "awaiting_review"
STATUS_REVIEWED         = "reviewed"
STATUS_SCHEDULED        = "scheduled"
STATUS_NOTES_WRITTEN    = "notes_written"
STATUS_COMPLETE         = "complete"
STATUS_FAILED           = "failed"     # node failed but pipeline continues with retry


# State schema

class InputConfig(TypedDict):
    pdf_path:     str
    vault_path:   str
    llm_provider: str
    llm_model:    str
    ollama_url:   str
    user_profile: dict


class PipelineState(InputConfig):
    # PDF
    pdf_text:        str
    pdf_metadata:    dict

    # Chunk extraction (parallel fan-in)
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

    # Notes (parallel fan-in)
    notes_map:       Annotated[dict, lambda a, b: {**a, **b}]

    # Output
    written_files:   list

    # Error tracking — each node appends its errors, never overwrites
    node_errors:     Annotated[dict, lambda a, b: {**a, **b}]   # {node: [errors]}
    failed_nodes:    Annotated[list, operator.add]               # accumulates failures
    retry_counts:    Annotated[dict, lambda a, b: {**a, **b}]   # {node: count}

    # Pipeline control
    status:          str
    _mcp_mode:       bool
    
    # Interactive mode (for advanced review, RAG, and corrections)
    _interactive_mode:    bool
    _enable_rag:          bool
    _enable_corrections:  bool
    
    # Merge mode (for adding topics to existing vaults)
    _merge_mode:     bool
    _existing_topic_ids: list
    _new_topic_ids:  list


def default_state(
    pdf_path:     str,
    vault_path:   str,
    llm_provider: str,
    llm_model:    str,
    ollama_url:   str,
    user_profile: dict,
    interactive_mode: bool = False,
    enable_rag: bool = True,
    enable_corrections: bool = True,
) -> dict:
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
        "node_errors":    {},
        "failed_nodes":   [],
        "retry_counts":   {},
        "status":         STATUS_STARTING,
        "_mcp_mode":      False,
        "_interactive_mode":    interactive_mode,
        "_enable_rag":          enable_rag,
        "_enable_corrections":  enable_corrections,
        "_merge_mode":    False,
        "_existing_topic_ids": [],
        "_new_topic_ids":  [],
    }