"""
Human review node — the interrupt point between extraction and scheduling.

CLI mode:  interactive terminal prompt, blocks until user responds
MCP mode:  sets status=awaiting_review and exits; MCP client calls
           approve_topics() to inject approved_topics and resume
"""

from src.config import UserProfile
from src.display import console


def node_human_review(state: dict) -> dict:
    """Pause for human review of extracted topics."""
    console.print("[dim]  node: human_review[/dim]")

    topics       = state.get("topics", [])
    user_profile = state.get("user_profile", {})
    is_mcp       = state.get("_mcp_mode", False)

    if is_mcp:
        # MCP path: signal awaiting_review, graph pauses here.
        # approved_topics defaults to all — overwritten by approve_topics() call.
        return {
            "approved_topics": topics,
            "status": "awaiting_review",
        }

    # CLI path: interactive terminal
    approved, updated_profile = _interactive_review(topics, user_profile)

    return {
        "approved_topics": approved,
        "user_profile":    updated_profile,
        "status":          "reviewed",
    }


def _interactive_review(topics: list, user_profile: dict) -> tuple[list, dict]:
    """Run the terminal review UI. Returns (approved_topics, updated_profile)."""
    console.print("\n" + "─" * 60)
    console.print("[bold cyan]📋 Review Extracted Topics[/bold cyan]")
    console.print("─" * 60)
    console.print(f"\n[bold]Found {len(topics)} topics:[/bold]\n")

    _print_topic_list(topics)

    console.print(
        "\n  [bold]a[/bold]  = Accept all  "
        " [bold]r[/bold]  = Remove some  "
        " [bold]h[/bold]  = Mark hard/easy  "
        " [bold]rh[/bold] = Both"
    )
    choice = input("\nEnter a/r/h/rh [a]: ").strip().lower() or "a"

    if "r" in choice:
        topics = _remove_topics(topics)
    if "h" in choice or (
        choice == "a"
        and not user_profile.get("hard_topics")
        and not user_profile.get("easy_topics")
    ):
        user_profile = _mark_hard_easy(topics, user_profile)

    console.print(f"\n[green]✓ Proceeding with {len(topics)} topics[/green]")
    return topics, user_profile


def _print_topic_list(topics: list) -> None:
    diff_colors = {"beginner": "green", "intermediate": "yellow", "advanced": "red"}
    for i, t in enumerate(topics, 1):
        color = diff_colors.get(t.get("difficulty", "intermediate"), "white")
        console.print(
            f"  [bold]{i:2d}.[/bold] [{color}]{t['title']}[/{color}]"
            f"  [dim]~{t.get('estimated_hours', 1.5)}h · {t.get('difficulty', '?')}[/dim]"
        )
        if t.get("description"):
            console.print(f"       [dim]{t['description'][:90]}[/dim]")
    console.print(
        "\n[dim]Legend: [green]beginner[/green]  "
        "[yellow]intermediate[/yellow]  [red]advanced[/red][/dim]"
    )


def _remove_topics(topics: list) -> list:
    console.print("\nNumbers to [bold red]REMOVE[/bold red] (comma-sep, Enter = keep all):")
    raw = input("Remove: ").strip()
    if not raw:
        return topics

    to_remove = {
        int(p.strip()) - 1
        for p in raw.split(",")
        if p.strip().isdigit() and 0 < int(p.strip()) <= len(topics)
    }
    removed = [topics[i]["title"] for i in sorted(to_remove)]
    if removed:
        console.print(f"  [dim]Removed: {', '.join(removed)}[/dim]")
    return [t for i, t in enumerate(topics) if i not in to_remove]


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
