"""
Extraction nodes:
  - node_extract_pdf    → read PDF from disk
  - node_extract_chunk  → extract topics from one chunk (runs in parallel)
  - node_dedup_topics   → merge all chunk results + optional LLM merge pass
"""

from pathlib import Path

from src.llm import LLMClient
from src.pdf_extractor import extract_pdf_text
from src.prompts import EXTRACT_SYSTEM, EXTRACT_USER, MERGE_SYSTEM, MERGE_USER
from src.utils import repair_json, dedup_topics, ensure_topic_defaults
from src.display import console


def _llm(state: dict) -> LLMClient:
    return LLMClient(
        provider=  state["llm_provider"],
        model=     state["llm_model"],
        ollama_url=state["ollama_url"],
    )


# ── Node: extract_pdf ─────────────────────────────────────────────────────── #

def node_extract_pdf(state: dict) -> dict:
    """
    Read PDF → extract text + metadata.
    Skips if pdf_text is already populated (CLI pre-fills it to avoid double read).
    """
    if state.get("pdf_text"):
        return {"status": "pdf_extracted"}

    console.print("[dim]  node: extract_pdf[/dim]")
    try:
        text, meta = extract_pdf_text(Path(state["pdf_path"]))
        return {"pdf_text": text, "pdf_metadata": meta, "status": "pdf_extracted"}
    except Exception as e:
        return {"error": str(e), "status": "failed"}


# ── Node: extract_chunk ───────────────────────────────────────────────────── #
# Receives extra keys from Send: chunk_text, chunk_num, total_chunks

def node_extract_chunk(state: dict) -> dict:
    """
    Extract topics from one text chunk.
    Injected by Send — runs in parallel with all other chunks.
    """
    chunk_num  = state["chunk_num"]
    total      = state["total_chunks"]
    meta       = state.get("pdf_metadata", {})

    try:
        response = _llm(state).chat(
            system_prompt=EXTRACT_SYSTEM,
            user_prompt=EXTRACT_USER.format(
                title=      meta.get("title", "Unknown"),
                chunk_num=  chunk_num,
                total_chunks=total,
                text=       state["chunk_text"],
            ),
            json_mode=True,
        )
        parsed = repair_json(response)
        topics = parsed.get("topics", [])
        console.print(f"  [dim]chunk {chunk_num}/{total}: {len(topics)} topics[/dim]")
    except Exception as e:
        console.print(f"  [yellow]chunk {chunk_num} failed: {e}[/yellow]")
        topics = []

    # Both fields use operator.add reducer — all parallel results merge automatically
    return {"raw_topics": topics, "chunks_done": 1}


# ── Node: dedup_topics ────────────────────────────────────────────────────── #

def node_dedup_topics(state: dict) -> dict:
    """
    Merge + deduplicate topics from all chunks.
    If > 20 topics remain, run a second LLM pass to consolidate further.
    """
    console.print("[dim]  node: dedup_topics[/dim]")

    raw     = state.get("raw_topics", [])
    meta    = state.get("pdf_metadata", {})
    subject = meta.get("title", "Unknown")
    desc    = ""

    console.print(f"  [dim]  raw: {len(raw)} → deduplicating...[/dim]")
    topics = dedup_topics(raw)
    console.print(f"  [dim]  after dedup: {len(topics)}[/dim]")

    if len(topics) > 20:
        console.print("  [dim]  LLM merge pass...[/dim]")
        raw_list = "\n".join(
            f'- {t["title"]}: {t.get("description", "")}'
            for t in topics
        )
        try:
            resp   = _llm(state).chat(
                system_prompt=MERGE_SYSTEM,
                user_prompt=  MERGE_USER.format(raw_topics=raw_list),
                json_mode=    True,
            )
            merged = repair_json(resp)
            if merged.get("topics"):
                topics  = merged["topics"]
                subject = merged.get("subject", subject)
                desc    = merged.get("description", desc)
                console.print(f"  [dim]  after merge: {len(topics)}[/dim]")
        except Exception as e:
            console.print(f"  [yellow]  merge skipped: {e}[/yellow]")

    topics = ensure_topic_defaults(topics)
    console.print(f"  [green]✓[/green] {len(topics)} topics")

    return {
        "topics":      topics,
        "subject":     subject,
        "description": desc,
        "status":      "topics_extracted",
    }
