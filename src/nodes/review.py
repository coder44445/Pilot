"""
Human review node — the interrupt point between extraction and scheduling.

CLI mode:  advanced interactive interface with RAG, error correction, and topic editing
MCP mode:  sets status=awaiting_review and exits; MCP client calls
           approve_topics() to inject approved_topics and resume
"""

from src.config import UserProfile
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
    enable_rag   = state.get("_enable_rag", True)
    enable_corrections = state.get("_enable_corrections", True)

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
        topics, user_profile, pdf_text, llm_client, enable_rag, enable_corrections
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


def _get_llm_client(state: dict) -> LLMClient:
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
    llm_client: LLMClient = None,
    enable_rag: bool = True,
    enable_corrections: bool = True,
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
        llm_client=llm_client,
        enable_rag=enable_rag,
        enable_corrections=enable_corrections,
    )
    
    return session.run_interactive_loop()
