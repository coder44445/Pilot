"""
Human review node — the interrupt point between extraction and scheduling.

CLI mode:  advanced interactive interface with RAG, error correction, and topic editing
MCP mode:  sets status=awaiting_review and exits; MCP client calls
           approve_topics() to inject approved_topics and resume
"""

from pydantic import NonNegativeFloat
from src.display import console
from src.interactive import InteractiveSession
from src.llm import LLMClient


def node_human_review(state: dict) -> dict:
    """Pause for human review of extracted topics with interactive interface."""
    console.print("[dim]  node: human_review[/dim]")

    topics       = state.get("topics", [])
    user_profile = state.get("user_profile", {})
    pdf_text     = state.get("pdf_text", "")
    is_mcp       = state.get("_mcp_mode", False)

    if is_mcp:
        # MCP path: signal awaiting_review, graph pauses here.
        # approved_topics defaults to all — overwritten by approve_topics() call.
        return {
            "approved_topics": topics,
            "status": "awaiting_review",
        }

    # CLI path: advanced interactive interface
    llm_client = _get_llm_client(state)
    approved, updated_profile, should_continue = _interactive_review(
        topics, user_profile, pdf_text, llm_client
    )

    if should_continue:
        return {
            "approved_topics": approved,
            "user_profile":    updated_profile,
            "status":          "reviewed",
        }
    else:
        # User aborted - still return approved topics but mark as not fully reviewed
        return {
            "approved_topics": approved,
            "user_profile":    updated_profile,
            "status":          "reviewed",
        }


def _get_llm_client(state: dict) -> LLMClient | None:
    """Get an LLM client from state for interactive operations."""
    try:
        llm_provider = state.get("llm_provider", "ollama")
        llm_model = state.get("llm_model")
        ollama_url = state.get("ollama_url", "http://localhost:11434")
        
        client = LLMClient(
            provider=llm_provider,
            model=llm_model,
            ollama_url=ollama_url
        )
        return client
    except Exception:
        # Return None if LLM not available - interactive session will handle it
        return None


def _interactive_review(
    topics: list,
    user_profile: dict,
    pdf_text: str,
    llm_client: LLMClient | None = None
) -> tuple[list, dict, bool]:
    """
    Run advanced interactive review with RAG and error correction.
    
    Returns:
        (approved_topics, updated_user_profile, should_continue)
    """
    session = InteractiveSession(
        pdf_text=pdf_text,
        topics=topics,
        user_profile=user_profile,
        llm_client=llm_client
    )
    
    return session.run_interactive_loop()


def _mark_hard_easy(topics: list, user_profile: dict) -> dict:
    profile = dict(user_profile)

    console.print("\n[bold red]HARD[/bold red] topic numbers (comma-sep, Enter = skip):")
    hard = _pick_titles(input("Hard: ").strip(), topics)

    console.print("[bold green]EASY[/bold green] topic numbers (comma-sep, Enter = skip):")
    easy = _pick_titles(input("Easy: ").strip(), topics)

    if hard:
        profile["hard_topics"] = list(set(profile.get("hard_topics", []) + hard))
        console.print(f"  [red]Hard:[/red] {', '.join(hard)}")
    if easy:
        profile["easy_topics"] = list(set(profile.get("easy_topics", []) + easy))
        console.print(f"  [green]Easy:[/green] {', '.join(easy)}")

    return profile


def _pick_titles(raw: str, topics: list) -> list:
    return [
        topics[int(p.strip()) - 1]["title"]
        for p in raw.split(",")
        if p.strip().isdigit() and 0 < int(p.strip()) <= len(topics)
    ]
