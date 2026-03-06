"""
Generates a structured study plan from PDF text + user profile using an LLM.

v3: proper chunked extraction
- PDF split into ~6k-word chunks, each sent separately to the LLM
- Topics extracted per chunk, then merged + deduplicated by title similarity
- Small-model safe: each call is small and focused
- Robust JSON repair (truncation, <think> tags, fences, trailing commas)
- Interactive topic review before scheduling
"""

import json
import re
from src.llm import LLMClient
from src.display import console


# ── Chunking ───────────────────────────────────────────────────────────────── #

CHUNK_SIZE_WORDS = 6_000
CHUNK_OVERLAP    = 200


def _chunk_text(text, chunk_size=CHUNK_SIZE_WORDS, overlap=CHUNK_OVERLAP):
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start += chunk_size - overlap
    return chunks


def _dedup_topics(all_topics):
    """Merge topics from multiple chunks. Dedup by normalised title."""
    seen = {}

    def _norm(title):
        return re.sub(r'[^a-z0-9]', '', title.lower())

    for t in all_topics:
        key = _norm(t.get("title", ""))
        if not key:
            continue
        if key not in seen:
            seen[key] = dict(t)
        else:
            existing = set(seen[key].get("subtopics", []))
            new      = set(t.get("subtopics", []))
            seen[key]["subtopics"] = sorted(existing | new)
            if len(t.get("description", "")) > len(seen[key].get("description", "")):
                seen[key]["description"] = t["description"]

    result = []
    for i, t in enumerate(seen.values(), 1):
        t["id"] = f"t{i}"
        result.append(t)
    return result


# ── Prompts ────────────────────────────────────────────────────────────────── #

EXTRACTION_SYSTEM = """You extract topic lists from educational text.
Output ONLY valid JSON. No thinking tags, no explanation, no markdown fences."""

EXTRACTION_PROMPT = """Extract topics/chapters from this book segment.

Book: {title}  |  Segment {chunk_num} of {total_chunks}
---
{text}
---

Output ONLY this JSON (3-8 topics from this segment):
{{
  "topics": [
    {{"title": "Topic Title", "difficulty": "beginner", "estimated_hours": 1.5, "description": "one sentence", "subtopics": ["sub1", "sub2"]}}
  ]
}}

difficulty must be: beginner, intermediate, or advanced.
Output ONLY the JSON object."""


MERGE_SYSTEM = """You are a curriculum designer. Output ONLY valid JSON. No explanation."""

MERGE_PROMPT = """Consolidate these book topics: remove true duplicates, merge very similar ones.

{raw_topics}

Output ONLY:
{{
  "subject": "short subject name",
  "description": "one sentence about the book",
  "topics": [
    {{"title": "Topic Title", "difficulty": "beginner", "estimated_hours": 1.5, "description": "one sentence", "subtopics": ["sub1"]}}
  ]
}}"""


PLANNING_SYSTEM = """You are a study planner. Output ONLY valid JSON. No explanation."""

PLANNING_PROMPT = """Create a {total_days}-day study schedule.

Topics (use these exact ids):
{topics_simple}

- Day 1 = orientation
- Day {total_days} = review + consolidation
- Every 5-7 days = review day
- {hours_per_day}h per day
- Skill: {skill_level}, Goal: {goal}
- Hard topics: {hard_topics}
- Easy topics: {easy_topics}

Output JSON:
{{
  "days": [
    {{
      "day": 1,
      "title": "Day title",
      "type": "orientation",
      "total_hours": {hours_per_day},
      "day_goal": "By end of today you will...",
      "notes": "",
      "topics": [
        {{"topic_id": "t1", "topic_title": "Title", "focus": "focus area", "time_allocation": 1.5, "depth": "overview", "activities": ["activity 1", "activity 2"]}}
      ]
    }}
  ]
}}"""


NOTES_SYSTEM = """You write study notes in Markdown. Be clear and practical."""

NOTES_PROMPT = """Write study notes for: {topic_title}

Description: {topic_description}
Subtopics: {subtopics}
Level: {skill_level} | Goal: {goal} | Style: {learning_style} | Depth: {depth}
{hard_easy_instruction}

Structure:
## {topic_title}
### What You'll Learn
### Core Concepts
### Key Points
{tldr_section}
### Examples
### Common Mistakes
{quiz_section}
### Related Topics (use [[wiki-link]] format)
---
*Estimated study time: {time_allocation}h*"""


# ── JSON repair ────────────────────────────────────────────────────────────── #

def _repair_json(raw):
    text = raw.strip()
    # Strip <think> blocks (qwen3, deepseek-r1)
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    # Strip markdown fences
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find first {
    m = re.search(r'\{', text)
    if m:
        text = text[m.start():]

    # Fix trailing commas
    text = re.sub(r',\s*([}\]])', r'\1', text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Close truncated JSON
    text = _close_truncated(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Could not parse LLM JSON.\nError: {e}\nResponse:\n{raw[:500]}"
        )


def _close_truncated(text):
    stack = []
    in_string = False
    escape_next = False
    for ch in text:
        if escape_next:
            escape_next = False
            continue
        if ch == '\\' and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in ('{', '['):
            stack.append('}' if ch == '{' else ']')
        elif ch in ('}', ']') and stack and stack[-1] == ch:
            stack.pop()
    text = text.rstrip().rstrip(',')
    return text + ''.join(reversed(stack))


# ── Interactive topic review ───────────────────────────────────────────────── #

def review_topics(topics, user_profile):
    console.print("\n" + "─" * 60)
    console.print("[bold cyan]📋 Review Extracted Topics[/bold cyan]")
    console.print("─" * 60)
    console.print(f"\n[bold]Found {len(topics)} topics:[/bold]\n")

    for i, t in enumerate(topics, 1):
        diff_color = {"beginner": "green", "intermediate": "yellow", "advanced": "red"}.get(
            t.get("difficulty", "intermediate"), "white"
        )
        console.print(
            f"  [bold]{i:2d}.[/bold] [{diff_color}]{t['title']}[/{diff_color}]"
            f"  [dim]~{t.get('estimated_hours', 1.5)}h · {t.get('difficulty', '?')}[/dim]"
        )
        if t.get("description"):
            console.print(f"       [dim]{t['description'][:90]}[/dim]")

    console.print("\n[dim]Legend: [green]beginner[/green]  [yellow]intermediate[/yellow]  [red]advanced[/red][/dim]")
    console.print("\n  [bold]a[/bold] = Accept all  |  [bold]r[/bold] = Remove  |  [bold]h[/bold] = Mark hard/easy  |  [bold]rh[/bold] = Both")

    choice = input("\nEnter a/r/h/rh [a]: ").strip().lower() or "a"

    if 'r' in choice:
        topics = _remove_topics(topics)
    if 'h' in choice or (
        choice == 'a'
        and not user_profile.get("hard_topics")
        and not user_profile.get("easy_topics")
    ):
        _mark_hard_easy(topics, user_profile)

    console.print(f"\n[green]✓ Proceeding with {len(topics)} topics[/green]")
    return topics


def _remove_topics(topics):
    console.print("\nNumbers to [bold red]REMOVE[/bold red] (comma-sep, Enter = keep all):")
    raw = input("Remove: ").strip()
    if not raw:
        return topics
    to_remove = {int(p.strip()) - 1 for p in raw.split(",") if p.strip().isdigit() and 0 < int(p.strip()) <= len(topics)}
    removed = [topics[i]["title"] for i in sorted(to_remove)]
    if removed:
        console.print(f"  [dim]Removed: {', '.join(removed)}[/dim]")
    return [t for i, t in enumerate(topics) if i not in to_remove]


def _mark_hard_easy(topics, user_profile):
    console.print("\n[bold red]HARD[/bold red] topic numbers (comma-sep, Enter = skip):")
    hard = _pick_titles(input("Hard: ").strip(), topics)
    console.print("[bold green]EASY[/bold green] topic numbers (comma-sep, Enter = skip):")
    easy = _pick_titles(input("Easy: ").strip(), topics)

    if hard:
        user_profile["hard_topics"] = list(set(user_profile.get("hard_topics", []) + hard))
        console.print(f"  [red]Hard:[/red] {', '.join(hard)}")
    if easy:
        user_profile["easy_topics"] = list(set(user_profile.get("easy_topics", []) + easy))
        console.print(f"  [green]Easy:[/green] {', '.join(easy)}")


def _pick_titles(raw, topics):
    titles = []
    for p in raw.split(","):
        p = p.strip()
        if p.isdigit():
            idx = int(p) - 1
            if 0 <= idx < len(topics):
                titles.append(topics[idx]["title"])
    return titles


# ── Main pipeline ──────────────────────────────────────────────────────────── #

def generate_study_plan(llm, pdf_text, user_profile, pdf_metadata):
    """
    1. Chunk PDF → extract topics per chunk → dedup → optional LLM merge
    2. Interactive review
    3. Schedule
    4. Notes
    """

    # ── Step 1: Chunked extraction ── #
    console.print("  [dim]Step 1/3: Extracting topics from full PDF (chunked)...[/dim]")

    chunks = _chunk_text(pdf_text)
    total_chunks = len(chunks)
    console.print(f"  [dim]  {total_chunks} chunks × ~{CHUNK_SIZE_WORDS:,} words[/dim]")

    all_raw_topics = []
    subject_guess = pdf_metadata.get("title", "Unknown")
    description_guess = ""

    for i, chunk in enumerate(chunks, 1):
        console.print(f"  [dim]  Chunk {i}/{total_chunks}...[/dim]", end="")
        try:
            response = llm.chat(
                system_prompt=EXTRACTION_SYSTEM,
                user_prompt=EXTRACTION_PROMPT.format(
                    title=pdf_metadata.get("title", "Unknown"),
                    chunk_num=i,
                    total_chunks=total_chunks,
                    text=chunk,
                ),
                json_mode=True,
            )
            parsed = _repair_json(response)
            chunk_topics = parsed.get("topics", [])
            all_raw_topics.extend(chunk_topics)
            if not description_guess:
                subject_guess = parsed.get("subject", subject_guess)
                description_guess = parsed.get("description", "")
            console.print(f" {len(chunk_topics)} topics")
        except Exception as e:
            console.print(f" [yellow]⚠ skipped ({e})[/yellow]")

    console.print(f"  [dim]  Raw: {len(all_raw_topics)} → deduplicating...[/dim]")
    topics = _dedup_topics(all_raw_topics)
    console.print(f"  [dim]  After dedup: {len(topics)} unique topics[/dim]")

    # LLM merge pass if > 20 topics
    if len(topics) > 20:
        console.print("  [dim]  LLM merge pass...[/dim]")
        raw_list = "\n".join(f'- {t["title"]}: {t.get("description","")}' for t in topics)
        try:
            merge_resp = llm.chat(
                system_prompt=MERGE_SYSTEM,
                user_prompt=MERGE_PROMPT.format(raw_topics=raw_list),
                json_mode=True,
            )
            merged = _repair_json(merge_resp)
            if merged.get("topics"):
                topics = merged["topics"]
                subject_guess = merged.get("subject", subject_guess)
                description_guess = merged.get("description", description_guess)
                console.print(f"  [dim]  After merge: {len(topics)} topics[/dim]")
        except Exception as e:
            console.print(f"  [yellow]  ⚠ merge skipped ({e})[/yellow]")

    # Normalise fields
    for i, t in enumerate(topics):
        t["id"] = f"t{i+1}"
        t.setdefault("title", f"Topic {i+1}")
        t.setdefault("description", "")
        t.setdefault("subtopics", [])
        t.setdefault("estimated_hours", 1.5)
        t.setdefault("difficulty", "intermediate")

    console.print(f"  [green]✓[/green] {len(topics)} topics from full PDF")

    # ── Step 2: Review ── #
    topics = review_topics(topics, user_profile)

    # ── Step 3: Schedule ── #
    console.print("\n[bold yellow]🧠 Building schedule...[/bold yellow]")

    topics_simple = "\n".join(
        f'- id: "{t["id"]}", title: "{t["title"]}", difficulty: {t.get("difficulty","intermediate")}, hours: {t.get("estimated_hours",1.5)}'
        for t in topics
    )

    planning_resp = llm.chat(
        system_prompt=PLANNING_SYSTEM,
        user_prompt=PLANNING_PROMPT.format(
            total_days=user_profile["total_days"],
            hours_per_day=user_profile["hours_per_day"],
            skill_level=user_profile["skill_level"],
            goal=user_profile["goal"],
            learning_style=user_profile.get("learning_style", "mixed"),
            hard_topics=", ".join(user_profile.get("hard_topics", [])) or "none",
            easy_topics=", ".join(user_profile.get("easy_topics", [])) or "none",
            topics_simple=topics_simple,
        ),
        json_mode=True,
    )

    schedule = _repair_json(planning_resp)
    days = schedule.get("days", [])
    console.print(f"  [green]✓[/green] {len(days)} days scheduled")

    # ── Step 4: Notes ── #
    console.print("\n[bold yellow]📝 Writing notes...[/bold yellow]")

    topic_map = {t["id"]: t for t in topics}

    scheduled_ids = set()
    for day in days:
        for t in day.get("topics", []):
            if t.get("topic_id"):
                scheduled_ids.add(t["topic_id"])
    if not scheduled_ids:
        scheduled_ids = {t["id"] for t in topics}

    notes_map = {}
    total = len(scheduled_ids)

    for i, tid in enumerate(sorted(scheduled_ids), 1):
        td = topic_map.get(tid)
        if not td:
            continue

        console.print(f"  [dim]  {i}/{total}: {td['title']}[/dim]")

        depth = "standard"
        time_alloc = td.get("estimated_hours", 1.5)
        for day in days:
            for t in day.get("topics", []):
                if t.get("topic_id") == tid:
                    depth = t.get("depth", "standard")
                    time_alloc = t.get("time_allocation", time_alloc)
                    break

        title_lower = td["title"].lower()
        if any(h.lower() in title_lower for h in user_profile.get("hard_topics", [])):
            hard_easy = "HARD topic: go extra deep, more examples."
        elif any(e.lower() in title_lower for e in user_profile.get("easy_topics", [])):
            hard_easy = "EASY topic: be concise, add practice exercises."
        else:
            hard_easy = ""

        tldr = "### TL;DR\n(one sentence)\n" if user_profile.get("include_summaries") else ""
        quiz = "### Quiz Yourself\n1. ?\n2. ?\n3. ?\n" if user_profile.get("include_quizzes") else ""

        try:
            notes = llm.chat(
                system_prompt=NOTES_SYSTEM,
                user_prompt=NOTES_PROMPT.format(
                    topic_title=td["title"],
                    topic_description=td.get("description", ""),
                    subtopics=", ".join(td.get("subtopics", [])),
                    skill_level=user_profile["skill_level"],
                    goal=user_profile["goal"],
                    learning_style=user_profile.get("learning_style", "mixed"),
                    depth=depth,
                    hard_easy_instruction=hard_easy,
                    tldr_section=tldr,
                    quiz_section=quiz,
                    time_allocation=time_alloc,
                ),
            )
            notes_map[tid] = notes
        except Exception as e:
            console.print(f"  [yellow]  ⚠ {td['title']}: {e}[/yellow]")
            notes_map[tid] = f"## {td['title']}\n\n*Notes unavailable. Error: {e}*"

    console.print(f"  [green]✓[/green] Notes for {len(notes_map)} topics")

    return {
        "subject": subject_guess,
        "description": description_guess,
        "topics": topics,
        "topic_map": topic_map,
        "days": days,
        "notes_map": notes_map,
        "user_profile": user_profile,
        "pdf_metadata": pdf_metadata,
    }
