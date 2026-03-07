#!/usr/bin/env python3
"""
Pilot CLI

Run once to start. If interrupted or crashed, run the exact same command again
to resume from where it stopped — PDF is never re-read, completed nodes are skipped.

Usage:
  python main.py --pdf book.pdf --vault ~/MyVault --llm ollama --model qwen3:4b
  python main.py --pdf book.pdf --vault ~/MyVault --restart   # force fresh start
"""

import argparse
import sys
from pathlib import Path

from src.config import LLMConfig, UserProfile
from src.graph_state import default_state
from src.graph import run_cli, make_thread_id
from src.llm import LLMClient
from src.pdf_extractor import extract_pdf_text
from src.questionnaire import run_questionnaire
from src.retry import summarise_errors
from src.display import console, print_banner, print_success, print_error


def main():
    print_banner()

    parser = argparse.ArgumentParser(
        description="Generate a personalized Obsidian study vault from a PDF."
    )
    parser.add_argument("--pdf",        required=True,  help="Path to PDF file")
    parser.add_argument("--vault",      required=True,  help="Path to Obsidian vault folder")
    parser.add_argument("--llm",        choices=["openai", "ollama"], default=None)
    parser.add_argument("--model",      default=None,   help="e.g. qwen3:4b, gpt-4o")
    parser.add_argument("--ollama-url", default="http://localhost:11434")
    parser.add_argument("--restart",    action="store_true",
                        help="Ignore saved checkpoints and start over")
    args = parser.parse_args()

    pdf_path   = Path(args.pdf)
    vault_path = Path(args.vault)

    if not pdf_path.exists():
        print_error(f"PDF not found: {pdf_path}")
        sys.exit(1)

    # LLM provider
    provider = args.llm
    if not provider:
        console.print("\n[bold cyan]Which LLM?[/bold cyan]")
        console.print("  [bold]1[/bold] → OpenAI  [bold]2[/bold] → Ollama")
        provider = "openai" if input("1 or 2 [2]: ").strip() == "1" else "ollama"

    llm_cfg = LLMConfig(
        provider=  provider,
        model=     args.model or "",
        ollama_url=args.ollama_url,
    )

    # Validate connection once upfront
    client = LLMClient(
        provider=  llm_cfg.provider,
        model=     llm_cfg.resolved_model(),
        ollama_url=llm_cfg.ollama_url,
    )
    client.validate()

    # Check for existing checkpoint
    thread_id = make_thread_id(str(pdf_path), str(vault_path))
    db_path   = vault_path / ".pilot_checkpoints.db"

    if db_path.exists() and not args.restart:
        console.print(
            f"\n[bold yellow]Found existing checkpoint[/bold yellow] "
            f"[dim](thread: {thread_id})[/dim]"
            f"\n[dim]Resuming — completed nodes will be skipped automatically.[/dim]"
            f"\n[dim]Run with --restart to start over.[/dim]\n"
        )
        # On resume we don't need to re-read the PDF or re-run the questionnaire —
        # all that is in the checkpoint. Build a minimal state; the graph will
        # skip any node whose output is already present.
        state = default_state(
            pdf_path=    str(pdf_path),
            vault_path=  str(vault_path),
            llm_provider=llm_cfg.provider,
            llm_model=   llm_cfg.resolved_model(),
            ollama_url=  llm_cfg.ollama_url,
            user_profile={},   # loaded from checkpoint
        )
        final = run_cli(state, force_restart=False)

    else:
        # Fresh start
        console.print(f"\n[bold]📄 Reading:[/bold] {pdf_path.name}")
        pdf_text, metadata = extract_pdf_text(pdf_path)
        console.print(
            f"   Pages: {metadata['pages']} | "
            f"~{metadata['word_count']:,} words"
        )

        profile = UserProfile.from_dict(run_questionnaire(metadata))

        console.print("\n[bold yellow]🚀 Starting pipeline...[/bold yellow]")
        console.print(
            f"[dim]  Checkpoints saved to: {db_path}[/dim]"
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
        # Pre-fill PDF content so extract_pdf node skips disk read
        state["pdf_text"]     = pdf_text
        state["pdf_metadata"] = metadata

        final = run_cli(state, force_restart=args.restart)

    # Done
    if not final:
        print_error("Pipeline produced no output.")
        sys.exit(1)

    failed = final.get("failed_nodes", [])
    written = final.get("written_files", [])

    if written:
        print_success(vault_path, written)

    if failed:
        console.print(
            f"\n[yellow]⚠  {len(set(failed))} node(s) had errors but the vault was still built.[/yellow]"
            f"\n[dim]   Rerun the same command — failed nodes will be retried,[/dim]"
            f"\n[dim]   successful ones will be skipped.[/dim]"
        )


if __name__ == "__main__":
    main()