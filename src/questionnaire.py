"""
Interactive CLI questionnaire to build a user profile for personalization.
"""

from typing import Optional
from src.display import console


def ask(prompt: str, default: Optional[str] = None, validator=None) -> str:
    """Ask a question and return the answer, with optional default and validation."""
    while True:
        suffix = f" [{default}]" if default else ""
        answer = input(f"\n{prompt}{suffix}: ").strip()

        if not answer and default is not None:
            return default

        if not answer:
            console.print("[red]  ✗ This field is required.[/red]")
            continue

        if validator:
            error = validator(answer)
            if error:
                console.print(f"[red]  ✗ {error}[/red]")
                continue

        return answer


def ask_list(prompt: str) -> list[str]:
    """Ask for a comma-separated list of items."""
    raw = input(f"\n{prompt} (comma-separated, or press Enter to skip): ").strip()
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def validate_positive_int(val: str) -> Optional[str]:
    try:
        n = int(val)
        if n <= 0:
            return "Please enter a number greater than 0."
    except ValueError:
        return "Please enter a valid number."
    return None


def run_questionnaire(pdf_metadata: dict) -> dict:
    """
    Run the personalization questionnaire and return a user profile dict.
    """
    console.print("\n" + "─" * 60)
    console.print("[bold cyan]📋 Let's personalize your study plan[/bold cyan]")
    console.print("─" * 60)

    # --- Time commitment ---
    console.print("\n[bold]⏱  Time commitment[/bold]")

    total_days = ask(
        "How many days do you have to complete this?",
        default="14",
        validator=validate_positive_int,
    )

    hours_per_day = ask(
        "How many hours can you study per day?",
        default="2",
        validator=validate_positive_int,
    )

    # --- Prior knowledge ---
    console.print("\n[bold]🧠 Your background[/bold]")

    skill_level = ask(
        "What's your current level with this subject?\n"
        "  1 = Complete beginner\n"
        "  2 = Some basics\n"
        "  3 = Intermediate\n"
        "  4 = Advanced\n"
        "Enter 1-4",
        default="1",
        validator=lambda v: None if v in ("1", "2", "3", "4") else "Enter 1, 2, 3, or 4",
    )

    skill_labels = {"1": "beginner", "2": "basics", "3": "intermediate", "4": "advanced"}
    skill_level_label = skill_labels[skill_level]

    # --- Hard / easy topics ---
    console.print("\n[bold]🎯 Topic weighting[/bold]")
    console.print("[dim]These help the plan spend MORE time on hard topics,[/dim]")
    console.print("[dim]and go DEEPER on easy topics so you can practice them.[/dim]")

    hard_topics = ask_list(
        "What topics do you find hard or want to focus on most?"
    )

    easy_topics = ask_list(
        "What topics are already easy or familiar to you?"
    )

    # --- Goal ---
    console.print("\n[bold]🏁 Goal[/bold]")
    console.print("  1 = Pass an exam / test")
    console.print("  2 = Build a project / apply it practically")
    console.print("  3 = Deep understanding / research")
    console.print("  4 = Quick overview / skim")

    goal_choice = ask(
        "What's your main goal?",
        default="1",
        validator=lambda v: None if v in ("1", "2", "3", "4") else "Enter 1-4",
    )

    goal_labels = {
        "1": "exam_prep",
        "2": "practical_project",
        "3": "deep_understanding",
        "4": "quick_overview",
    }
    goal_label = goal_labels[goal_choice]

    # --- Learning style ---
    console.print("\n[bold]📚 Learning style[/bold]")
    console.print("  1 = Theory first, then examples")
    console.print("  2 = Examples first, then theory")
    console.print("  3 = Mix of both")

    def _validate_style(v: str):
        if v not in ("1", "2", "3"):
            return "Enter 1, 2, or 3"
        return None

    style_choice = ask(
        "How do you prefer to learn?",
        default="3",
        validator=_validate_style,
    )

    style_labels = {
        "1": "theory_first",
        "2": "examples_first",
        "3": "mixed",
    }
    style_label = style_labels[style_choice]

    # --- Output preferences ---
    console.print("\n[bold]📝 Output preferences[/bold]")

    include_quizzes = ask(
        "Include quiz questions at the end of each day? (yes/no)",
        default="yes",
        validator=lambda v: None if v.lower() in ("yes", "no", "y", "n") else "Enter yes or no",
    )

    include_summaries = ask(
        "Include a TL;DR summary for each topic? (yes/no)",
        default="yes",
        validator=lambda v: None if v.lower() in ("yes", "no", "y", "n") else "Enter yes or no",
    )

    profile = {
        "total_days": int(total_days),
        "hours_per_day": int(hours_per_day),
        "total_hours": int(total_days) * int(hours_per_day),
        "skill_level": skill_level_label,
        "hard_topics": hard_topics,
        "easy_topics": easy_topics,
        "goal": goal_label,
        "learning_style": style_label,
        "include_quizzes": include_quizzes.lower() in ("yes", "y"),
        "include_summaries": include_summaries.lower() in ("yes", "y"),
        "pdf_title": pdf_metadata.get("title", "Unknown"),
    }

    console.print("\n[bold green]✓ Profile captured![/bold green]")
    return profile
