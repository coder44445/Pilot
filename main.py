#!/usr/bin/env python3
"""StudyVault CLI — LangGraph pipeline"""

import argparse
import sys
from pathlib import Path

from src.config import LLMConfig, UserProfile
from src.graph_state import default_state
from src.graph import run_cli
from src.llm import LLMClient
from src.pdf_extractor import extract_pdf_text
from src.questionnaire import run_questionnaire
from src.display import console, print_banner, print_success, print_error


def main():
    print_banner()

    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf",       required=True)
    parser.add_argument("--vault",     required=True)
    parser.add_argument("--llm",       choices=["openai", "ollama"], default=None,required=True)
    parser.add_argument("--model",     default=None,)
    parser.add_argument("--ollama-url", default="http://localhost:11434")
    args = parser.parse_args()

    pdf_path   = Path(args.pdf)
    vault_path = Path(args.vault)

    if not pdf_path.exists():
        print_error(f"PDF not found: {pdf_path}")
        sys.exit(1)

    # Choose provider
    provider = args.llm
    if not provider:
        console.print("\n[bold cyan]Which LLM?[/bold cyan]")
        console.print("  [bold]1[/bold] → OpenAI  [bold]2[/bold] → Ollama")
        provider = "openai" if input("1 or 2: ").strip() == "1" else "ollama"

    llm_cfg = LLMConfig(
        provider=   provider,
        model=      args.model or "",
        ollama_url= args.ollama_url,
    )

    # Validate connection once — not per-node
    LLMClient(
        provider=   llm_cfg.provider,
        model=      llm_cfg.resolved_model(),
        ollama_url= llm_cfg.ollama_url,
    ).validate()

    # Extract PDF once here so the graph node skips it
    console.print(f"\n[bold]📄 Reading:[/bold] {pdf_path.name}")
    pdf_text, metadata = extract_pdf_text(pdf_path)
    console.print(f"   Pages: {metadata['pages']} | ~{metadata['word_count']:,} words")

    # Questionnaire → UserProfile
    profile = UserProfile.from_dict(run_questionnaire(metadata))

    console.print("\n[bold yellow]🚀 Starting LangGraph pipeline...[/bold yellow]")

    state = default_state(
        pdf_path=    str(pdf_path),
        vault_path=  str(vault_path),
        llm_provider=llm_cfg.provider,
        llm_model=   llm_cfg.resolved_model(),
        ollama_url=  llm_cfg.ollama_url,
        user_profile=profile.to_dict(),
    )
    # Pre-fill pdf_text so graph skips re-extraction
    state["pdf_text"]    = pdf_text
    state["pdf_metadata"] = metadata

    final = run_cli(state)

    if final.get("error"):
        print_error(final["error"])
        sys.exit(1)

    print_success(vault_path, final.get("written_files", []))


if __name__ == "__main__":
    main()
