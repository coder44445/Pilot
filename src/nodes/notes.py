"""
Notes node: write_note

Receives a single topic via Send — runs in parallel for all topics.
Returns {topic_id: markdown} which LangGraph merges via dict reducer.
"""

from src.llm import LLMClient
from src.prompts import NOTES_SYSTEM, NOTES_USER
from src.display import console


def node_write_note(state: dict) -> dict:
    """
    Write study notes for one topic.
    `state["topic"]` is injected by Send.
    """
    topic   = state["topic"]
    profile = state.get("user_profile", {})
    days    = state.get("days", [])
    tid     = topic["id"]

    # Find depth + time allocation from schedule
    depth      = "standard"
    time_alloc = topic.get("estimated_hours", 1.5)
    for day in days:
        for t in day.get("topics", []):
            if t.get("topic_id") == tid:
                depth      = t.get("depth", "standard")
                time_alloc = t.get("time_allocation", time_alloc)
                break

    # Hard/easy instruction
    title_lower = topic["title"].lower()
    if any(h.lower() in title_lower for h in profile.get("hard_topics", [])):
        hard_easy = "HARD topic: go extra deep, more examples, explain carefully."
    elif any(e.lower() in title_lower for e in profile.get("easy_topics", [])):
        hard_easy = "EASY topic: be concise, add practice exercises."
    else:
        hard_easy = ""

    tldr = "### 📌 TL;DR\n(one sentence summary)\n" if profile.get("include_summaries") else ""
    quiz = "### 🧪 Quiz Yourself\n1. ?\n2. ?\n3. ?\n" if profile.get("include_quizzes") else ""

    llm = LLMClient(
        provider=  state["llm_provider"],
        model=     state["llm_model"],
        ollama_url=state["ollama_url"],
    )

    try:
        notes = llm.chat(
            system_prompt=NOTES_SYSTEM,
            user_prompt=  NOTES_USER.format(
                topic_title=       topic["title"],
                topic_description= topic.get("description", ""),
                subtopics=         ", ".join(topic.get("subtopics", [])),
                skill_level=       profile.get("skill_level", "beginner"),
                goal=              profile.get("goal", "practical_project"),
                learning_style=    profile.get("learning_style", "mixed"),
                depth=             depth,
                hard_easy_instruction=hard_easy,
                tldr_section=      tldr,
                quiz_section=      quiz,
                time_allocation=   time_alloc,
            ),
        )
        console.print(f"  [dim]  ✓ {topic['title']}[/dim]")
    except Exception as e:
        notes = f"## {topic['title']}\n\n*Notes unavailable. Error: {e}*"
        console.print(f"  [yellow]  ⚠ {topic['title']}: {e}[/yellow]")

    return {"notes_map": {tid: notes}}
