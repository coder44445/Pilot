#!/usr/bin/env python3
"""
Pilot CLI

LLM settings are read from pilot.config.yml — no need to pass --llm or --model
unless you want to override the config for a specific run.

Usage:
  python main.py --pdf book.pdf --vault ~/MyVault
  python main.py --url https://example.com/article --vault ~/MyVault
  python main.py --pdf book.pdf --vault ~/MyVault --llm openai --model gpt-4o
  python main.py --pdf book.pdf --vault ~/MyVault --restart
"""

import argparse
import sys
from pathlib import Path

from src.config import LLMConfig, UserProfile
from src.config_loader import load_llm_config, print_config_summary
from src.graph_state import default_state
from src.graph import run_cli, make_thread_id, get_checkpoint_state
from src.llm import LLMClient
from src.pdf_extractor import extract_pdf_text
from src.url_extractor import extract_url_text
from src.questionnaire import run_questionnaire
from src.vault_merger import check_vault_exists, load_existing_topics, merge_topics, get_vault_subject
from src.display import console, print_banner, print_success, print_error


def main():
    print_banner()

    parser = argparse.ArgumentParser(
        description="Generate a personalized Obsidian study vault from a PDF or URL."
    )
    parser.add_argument("--pdf",        default=None,  help="Path to PDF file")
    parser.add_argument("--url",        default=None,  help="URL to web page")
    parser.add_argument("--vault",      required=True,  help="Path to Obsidian vault folder")
    parser.add_argument("--llm",        choices=["openai", "ollama"], default=None,
                        help="Override config: openai | ollama")
    parser.add_argument("--model",      default=None,
                        help="Override config: e.g. qwen3:4b, gpt-4o")
    parser.add_argument("--ollama-url", default=None,
                        help="Override config: Ollama server URL")
    parser.add_argument("--restart",    action="store_true",
                        help="Ignore saved checkpoints and start over")
    parser.add_argument("--merge",      action="store_true",
                        help="Add new topics to existing vault without overwriting notes")
    parser.add_argument("--interactive", action="store_true",
                        help="Enable advanced interactive topic review with RAG and corrections")
    parser.add_argument("--no-rag",     action="store_true",
                        help="Disable RAG features in interactive mode")
    parser.add_argument("--skip-corrections", action="store_true",
                        help="Skip automatic error detection and correction suggestions")
    args = parser.parse_args()

    # Validate input source
    if not args.pdf and not args.url:
        print_error("Must provide either --pdf or --url")
        sys.exit(1)
    
    if args.pdf and args.url:
        print_error("Cannot provide both --pdf and --url — choose one")
        sys.exit(1)

    vault_path = Path(args.vault)

    # Extract content from source
    if args.pdf:
        pdf_path = Path(args.pdf)
        if not pdf_path.exists():
            print_error(f"PDF not found: {pdf_path}")
            sys.exit(1)
        console.print(f"\n[bold]📄 Reading:[/bold] {pdf_path.name}")
        text, metadata = extract_pdf_text(pdf_path)
        source_id = str(pdf_path)
        console.print(f"   Pages: {metadata['pages']} | ~{metadata['word_count']:,} words")
    else:
        console.print(f"\n[bold]🌐 Fetching:[/bold] {args.url}")
        try:
            text, metadata = extract_url_text(args.url)
            source_id = args.url
            console.print(f"   Title: {metadata['title']} | ~{metadata['word_count']:,} words")
        except Exception as e:
            print_error(str(e))
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
    thread_id = make_thread_id(source_id, str(vault_path))
    db_path   = vault_path / ".pilot_checkpoints.db"

    if db_path.exists() and not args.restart:
        console.print(
            f"\n[bold yellow]↩ Resuming from checkpoint[/bold yellow] "
            f"[dim](thread: {thread_id})[/dim]"
            f"\n[dim]  Completed nodes will be skipped. Use --restart to start over.[/dim]\n"
        )
        # Load checkpoint state to recover user_profile
        checkpoint_state = get_checkpoint_state(thread_id, str(vault_path))
        recovered_profile = checkpoint_state.get("user_profile", {})
        
        state = default_state(
            pdf_path=    source_id,
            vault_path=  str(vault_path),
            llm_provider=llm_cfg.provider,
            llm_model=   llm_cfg.resolved_model(),
            ollama_url=  llm_cfg.ollama_url,
            user_profile=recovered_profile,
            interactive_mode=args.interactive,
            enable_rag=not args.no_rag,
            enable_corrections=not args.skip_corrections,
        )
        final = run_cli(state, force_restart=False)

    else:
        # Fresh start or merge mode
        profile = UserProfile.from_dict(run_questionnaire(metadata))

        console.print("\n[bold yellow]🚀 Starting pipeline...[/bold yellow]")
        console.print(
            f"[dim]  Checkpoints: {db_path}[/dim]"
            f"\n[dim]  If this crashes, rerun the same command to resume.[/dim]\n"
        )

        state = default_state(
            pdf_path=    source_id,
            vault_path=  str(vault_path),
            llm_provider=llm_cfg.provider,
            llm_model=   llm_cfg.resolved_model(),
            ollama_url=  llm_cfg.ollama_url,
            user_profile=profile.to_dict(),
            interactive_mode=args.interactive,
            enable_rag=not args.no_rag,
            enable_corrections=not args.skip_corrections,
        )
        state["pdf_text"]     = text
        state["pdf_metadata"] = metadata
        
        # Merge mode: load existing topics and merge with new ones
        if args.merge:
            if check_vault_exists(vault_path):
                console.print("[dim]  Loading existing vault topics...[/dim]")
                existing = load_existing_topics(vault_path)
                console.print(f"[dim]  Found {len(existing)} existing topics[/dim]")
                
                # Merge new topics with existing ones
                merged_topics, new_ids = merge_topics(state.get("topics", []), existing)
                if merged_topics:
                    state["topics"] = merged_topics
                    state["_merge_mode"] = True
                    state["_existing_topic_ids"] = list(existing.keys())
                    state["_new_topic_ids"] = new_ids
                    console.print(f"[dim]  Will add {len(new_ids)} new topics[/dim]")
            else:
                console.print("[yellow]  ⚠  No existing vault found — running fresh[/yellow]")

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