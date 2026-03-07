"""
Schedule node — wrapped with @resilient_node.
Skips if schedule already built (idempotent on resume).
"""

from src.llm import LLMClient
from src.prompts import SCHEDULE_SYSTEM, SCHEDULE_USER
from src.utils import repair_json
from src.retry import resilient_node, node_already_done
from src.display import console


@resilient_node("build_schedule", max_retries=3)
def node_build_schedule(state: dict) -> dict:
    """Build day-by-day schedule. Skipped if days already populated."""
    if node_already_done(state, "build_schedule", "days"):
        return {"status": "scheduled"}

    console.print("[dim]  node: build_schedule[/dim]")

    topics  = state.get("approved_topics") or state.get("topics", [])
    profile = state.get("user_profile", {})

    topics_simple = "\n".join(
        f'- id: "{t["id"]}", title: "{t["title"]}", '
        f'difficulty: {t.get("difficulty","intermediate")}, '
        f'hours: {t.get("estimated_hours", 1.5)}'
        for t in topics
    )

    llm = LLMClient(
        provider=  state["llm_provider"],
        model=     state["llm_model"],
        ollama_url=state["ollama_url"],
    )

    resp = llm.chat(
        system_prompt=SCHEDULE_SYSTEM,
        user_prompt=  SCHEDULE_USER.format(
            total_days=    profile.get("total_days", 14),
            hours_per_day= profile.get("hours_per_day", 2),
            skill_level=   profile.get("skill_level", "beginner"),
            goal=          profile.get("goal", "practical_project"),
            hard_topics=   ", ".join(profile.get("hard_topics", [])) or "none",
            easy_topics=   ", ".join(profile.get("easy_topics", [])) or "none",
            topics_simple= topics_simple,
        ),
        json_mode=True,
    )

    schedule = repair_json(resp)
    days     = schedule.get("days", [])

    if not days:
        raise ValueError("LLM returned empty schedule — will retry")

    console.print(f"  [green]✓[/green] {len(days)} days scheduled")
    return {"days": days, "status": "scheduled"}