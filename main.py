#!/usr/bin/env python3
"""
Pilot CLI

LLM settings are read from pilot.config.yml — no need to pass --llm or --model
unless you want to override the config for a specific run.

Usage:
  python main.py --pdf book.pdf --vault ~/MyVault
  python main.py --pdf book.pdf --vault ~/MyVault --llm openai --model gpt-4o
  python main.py --pdf book.pdf --vault ~/MyVault --restart
"""

import argparse
import sys
from pathlib import Path

from src.config import LLMConfig, UserProfile
from src.config_loader import load_llm_config, print_config_summary
from src.graph_state import default_state
from src.graph import run_cli, make_thread_id
from src.llm import LLMClient
from src.pdf_extractor import extract_pdf_text
from src.questionnaire import run_questionnaire
from src.display import console, print_banner, print_success, print_error


def main():
    print_banner()

    parser = argparse.ArgumentParser(
        description="Generate a personalized Obsidian study vault from a PDF."
    )
    parser.add_argument("--pdf",        required=True,  help="Path to PDF file")
    parser.add_argument("--vault",      required=True,  help="Path to Obsidian vault folder")
    parser.add_argument("--llm",        choices=["openai", "ollama"], default=None,
                        help="Override config: openai | ollama")
    parser.add_argument("--model",      default=None,
                        help="Override config: e.g. qwen3:4b, gpt-4o")
    parser.add_argument("--ollama-url", default=None,
                        help="Override config: Ollama server URL")
    parser.add_argument("--restart",    action="store_true",
                        help="Ignore saved checkpoints and start over")
    args = parser.parse_args()

    pdf_path   = Path(args.pdf)
    vault_path = Path(args.vault)

    if not pdf_path.exists():
        print_error(f"PDF not found: {pdf_path}")
        sys.exit(1)

    # LLM config: file → CLI override
    cfg = load_llm_config()

    provider   = args.llm        or cfg["provider"]
    model      = args.model      or cfg["model"]
    ollama_url = args.ollama_url or cfg["ollama_url"]

    print_config_summary(console)

    llm_cfg = LLMConfig(
        provider=  provider,
        model=     model,
        ollama_url=ollama_url,
    )

    # Validate connection once upfront
    LLMClient(
        provider=  llm_cfg.provider,
        model=     llm_cfg.resolved_model(),
        ollama_url=llm_cfg.ollama_url,
    ).validate()

    # Resume check
    thread_id = make_thread_id(str(pdf_path), str(vault_path))
    db_path   = vault_path / ".studyvault_checkpoints.db"

    if db_path.exists() and not args.restart:
        console.print(
            f"\n[bold yellow]↩ Resuming from checkpoint[/bold yellow] "
            f"[dim](thread: {thread_id})[/dim]"
            f"\n[dim]  Completed nodes will be skipped. Use --restart to start over.[/dim]\n"
        )
        state = default_state(
            pdf_path=    str(pdf_path),
            vault_path=  str(vault_path),
            llm_provider=llm_cfg.provider,
            llm_model=   llm_cfg.resolved_model(),
            ollama_url=  llm_cfg.ollama_url,
            user_profile={},
        )
        final = run_cli(state, force_restart=False)

    else:
        # Fresh start
        console.print(f"\n[bold]📄 Reading:[/bold] {pdf_path.name}")
        pdf_text, metadata = extract_pdf_text(pdf_path)
        console.print(
            f"   Pages: {metadata['pages']} | ~{metadata['word_count']:,} words"
        )

        profile = UserProfile.from_dict(run_questionnaire(metadata))

        console.print("\n[bold yellow]🚀 Starting pipeline...[/bold yellow]")
        console.print(
            f"[dim]  Checkpoints: {db_path}[/dim]"
            f"\n[dim]  If this crashes, rerun the same command to resume.[/dim]\n"
        )

        state = default_state(
            pdf_path=    str(pdf_path),
            vault_path=  str(vault_path),
            llm_provider=llm_cfg.provider,
            llm_model=   llm_cfg.resolved_model(),
            ollama_url=  llm_cfg.ollama_url,
            user_profile=profile.to_dict(),
        )
        state["pdf_text"]     = pdf_text
        state["pdf_metadata"] = metadata

        final = run_cli(state, force_restart=args.restart)

    # Done
    if not final:
        print_error("Pipeline produced no output.")
        sys.exit(1)

    written = final.get("written_files", [])
    failed  = list(set(final.get("failed_nodes", [])))

    if written:
        print_success(vault_path, written)

    if failed:
        console.print(
            f"\n[yellow]⚠  {len(failed)} node(s) had errors.[/yellow]"
            f"\n[dim]   Rerun to retry — completed nodes will be skipped.[/dim]"
        )


if __name__ == "__main__":
    main()