"""
Extraction nodes — all wrapped with @resilient_node for retry + idempotency.

node_extract_pdf:   reads PDF — skipped if pdf_text already in state
node_extract_chunk: per-chunk LLM call — failed chunks log and continue
node_dedup_topics:  merge + dedup — skipped if topics already in state
"""

from pathlib import Path

from src.llm import LLMClient
from src.pdf_extractor import extract_pdf_text
from src.prompts import EXTRACT_SYSTEM, EXTRACT_USER, MERGE_SYSTEM, MERGE_USER
from src.utils import repair_json, dedup_topics, ensure_topic_defaults
from src.retry import resilient_node, node_already_done
from src.display import console


def _llm(state: dict) -> LLMClient:
    return LLMClient(
        provider=  state["llm_provider"],
        model=     state["llm_model"],
        ollama_url=state["ollama_url"],
    )


# extract_pdf

@resilient_node("extract_pdf", max_retries=2)
def node_extract_pdf(state: dict) -> dict:
    """Read PDF. Skipped if pdf_text already populated (idempotent)."""
    if node_already_done(state, "extract_pdf", "pdf_text"):
        return {"status": "pdf_extracted"}

    console.print("[dim]  node: extract_pdf[/dim]")
    text, meta = extract_pdf_text(Path(state["pdf_path"]))
    return {"pdf_text": text, "pdf_metadata": meta, "status": "pdf_extracted"}


# extract_chunk 
# No @resilient_node here — chunk failures are expected and handled inline.
# A bad chunk just contributes 0 topics; the dedup stage catches the gap.

def node_extract_chunk(state: dict) -> dict:
    """Extract topics from one chunk. Per-chunk failures are non-fatal."""
    chunk_num = state["chunk_num"]
    total     = state["total_chunks"]
    meta      = state.get("pdf_metadata", {})

    try:
        response = _llm(state).chat(
            system_prompt=EXTRACT_SYSTEM,
            user_prompt=EXTRACT_USER.format(
                title=        meta.get("title", "Unknown"),
                chunk_num=    chunk_num,
                total_chunks= total,
                text=         state["chunk_text"],
            ),
            json_mode=True,
        )
        parsed = repair_json(response)
        topics = parsed.get("topics", [])
        console.print(f"  [dim]chunk {chunk_num}/{total}: {len(topics)} topics[/dim]")
    except Exception as e:
        console.print(f"  [yellow]  chunk {chunk_num} failed ({e}) — continuing[/yellow]")
        topics = []

    return {"raw_topics": topics, "chunks_done": 1}


# dedup_topics

@resilient_node("dedup_topics", max_retries=2)
def node_dedup_topics(state: dict) -> dict:
    """Dedup raw topics. Skipped if topics already populated (idempotent)."""
    if node_already_done(state, "dedup_topics", "topics"):
        return {"status": "topics_extracted"}

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
            f'- {t["title"]}: {t.get("description","")}'
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
            console.print(f"  [yellow]  merge skipped ({e})[/yellow]")

    topics = ensure_topic_defaults(topics)
    console.print(f"  [green]✓[/green] {len(topics)} topics")

    return {
        "topics":  topics,
        "subject": subject,
        "description": desc,
        "status":  "topics_extracted",
    }