"""
Planning node: build_schedule

Takes approved topics + user profile → generates day-by-day schedule.
"""

from src.llm import LLMClient
from src.prompts import SCHEDULE_SYSTEM, SCHEDULE_USER
from src.utils import repair_json
from src.display import console


def node_build_schedule(state: dict) -> dict:
    """Generate a day-by-day study schedule from approved topics."""
    console.print("[dim]  node: build_schedule[/dim]")

    topics  = state.get("approved_topics") or state.get("topics", [])
    profile = state.get("user_profile", {})

    topics_simple = "\n".join(
        f'- id: "{t["id"]}", title: "{t["title"]}", '
        f'difficulty: {t.get("difficulty", "intermediate")}, '
        f'hours: {t.get("estimated_hours", 1.5)}'
        for t in topics
    )

    llm = LLMClient(
        provider=  state["llm_provider"],
        model=     state["llm_model"],
        ollama_url=state["ollama_url"],
    )

    try:
        resp = llm.chat(
            system_prompt=SCHEDULE_SYSTEM,
            user_prompt=  SCHEDULE_USER.format(
                total_days=   profile.get("total_days", 14),
                hours_per_day=profile.get("hours_per_day", 2),
                skill_level=  profile.get("skill_level", "beginner"),
                goal=         profile.get("goal", "practical_project"),
                hard_topics=  ", ".join(profile.get("hard_topics", [])) or "none",
                easy_topics=  ", ".join(profile.get("easy_topics", [])) or "none",
                topics_simple=topics_simple,
            ),
            json_mode=True,
        )
        schedule = repair_json(resp)
        days     = schedule.get("days", [])
        console.print(f"  [green]✓[/green] {len(days)} days scheduled")
        return {"days": days, "status": "scheduled"}

    except Exception as e:
        return {"error": str(e), "status": "failed"}
