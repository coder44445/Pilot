"""
Writes the generated study plan into an Obsidian vault.

Vault structure:
  {vault}/
  └── {subject}/
      ├── 📚 Index.md              ← Main hub, overview, backlinks to all days
      ├── 🗓️ Schedule Overview.md  ← Full schedule table
      ├── Days/
      │   ├── Day 01 - Title.md
      │   ├── Day 02 - Title.md
      │   └── ...
      ├── Notes/
      │   ├── Topic Name.md
      │   └── ...
      └── Meta/
          ├── Progress Tracker.md
          └── Profile.md
"""

from pathlib import Path
from datetime import datetime, timedelta
from typing import List


def sanitize_filename(name: str) -> str:
    """Remove characters that are invalid in filenames."""
    invalid = r'\/:*?"<>|'
    for ch in invalid:
        name = name.replace(ch, "")
    return name.strip()


def write_vault(vault_path: Path, study_plan: dict, user_profile: dict, pdf_metadata: dict) -> List[str]:
    """
    Write all vault files. Returns list of created file paths (relative to vault).
    """
    subject = sanitize_filename(study_plan["subject"])
    base = vault_path / subject

    # Create folder structure
    (base / "Days").mkdir(parents=True, exist_ok=True)
    (base / "Notes").mkdir(parents=True, exist_ok=True)
    (base / "Meta").mkdir(parents=True, exist_ok=True)

    written = []
    start_date = datetime.today()

    # --- Write topic notes ---
    topic_file_map = {}  # topic_id → Note filename (without .md)
    for topic in study_plan["topics"]:
        tid = topic["id"]
        fname = sanitize_filename(topic["title"])
        notes_content = study_plan["notes_map"].get(tid, f"## {topic['title']}\n\nNotes coming soon.")

        # Add frontmatter
        frontmatter = f"""---
title: "{topic['title']}"
type: note
topic_id: "{tid}"
difficulty: "{topic.get('difficulty', 'unknown')}"
estimated_hours: {topic.get('estimated_hours', 1.5)}
tags: [study, {subject.lower().replace(' ', '-')}]
created: {datetime.today().strftime('%Y-%m-%d')}
---

"""
        file_path = base / "Notes" / f"{fname}.md"
        file_path.write_text(frontmatter + notes_content, encoding="utf-8")
        topic_file_map[tid] = fname
        written.append(f"{subject}/Notes/{fname}.md")

    # --- Write day files ---
    days = study_plan["days"]
    day_titles = []

    for day_data in days:
        day_num = day_data["day"]
        day_title = sanitize_filename(day_data["title"])
        day_filename = f"Day {day_num:02d} - {day_title}"
        day_date = start_date + timedelta(days=day_num - 1)

        day_topics_section = ""
        for t in day_data.get("topics", []):
            tid = t.get("topic_id", "")
            note_name = topic_file_map.get(tid, t.get("topic_title", "Unknown"))
            activities = "\n".join(f"  - [ ] {act}" for act in t.get("activities", []))
            day_topics_section += f"""
### [[{note_name}]]
- **Focus:** {t.get('focus', '')}
- **Time:** {t.get('time_allocation', 0)}h
- **Depth:** {t.get('depth', 'standard')}

**Activities:**
{activities}

"""

        # Prev/next navigation
        prev_link = f"[[Day {day_num - 1:02d}]]" if day_num > 1 else "*(start)*"
        next_link = f"[[Day {day_num + 1:02d}]]" if day_num < len(days) else "*(finish)*"

        day_content = f"""---
title: "Day {day_num}: {day_data['title']}"
type: day-plan
day: {day_num}
date: {day_date.strftime('%Y-%m-%d')}
status: not-started
total_hours: {day_data.get('total_hours', user_profile['hours_per_day'])}
tags: [study-day, {subject.lower().replace(' ', '-')}]
---

# Day {day_num}: {day_data['title']}

> **Goal:** {day_data.get('day_goal', '')}

| | |
|---|---|
| 📅 Date | {day_date.strftime('%A, %B %d %Y')} |
| ⏱ Time | {day_data.get('total_hours', user_profile['hours_per_day'])}h |
| 🏷 Type | {day_data.get('type', 'study').capitalize()} |

{f"> 💡 **Note:** {day_data['notes']}" if day_data.get('notes') else ''}

---

## 📚 Topics for Today
{day_topics_section}

---

## ✅ Daily Checklist
- [ ] Read all topics for today
- [ ] Take notes in your own words
- [ ] Review key concepts before ending

---

## 📝 My Notes
*(Add your personal notes here)*

---

## 🔄 Navigation
← {prev_link} | [[📚 Index]] | {next_link} →
"""

        file_path = base / "Days" / f"{day_filename}.md"
        file_path.write_text(day_content, encoding="utf-8")
        day_titles.append((day_num, day_filename, day_data["title"], day_data.get("type", "study")))
        written.append(f"{subject}/Days/{day_filename}.md")

    # --- Write Index ---
    days_table = "\n".join(
        f"| [[Day {num:02d} - {sanitize_filename(title)}\\|Day {num}]] | {title} | {dtype.capitalize()} |"
        for num, _, title, dtype in day_titles
    )

    notes_links = "\n".join(
        f"- [[{fname}]]"
        for fname in topic_file_map.values()
    )

    index_content = f"""---
title: "{study_plan['subject']}"
type: index
created: {datetime.today().strftime('%Y-%m-%d')}
total_days: {user_profile['total_days']}
hours_per_day: {user_profile['hours_per_day']}
goal: {user_profile['goal']}
tags: [index, study-vault, {subject.lower().replace(' ', '-')}]
---

# 📚 {study_plan['subject']}

> {study_plan['description']}

---

## 🗺️ Overview

| Metric | Value |
|--------|-------|
| 📅 Total Days | {user_profile['total_days']} |
| ⏱ Hours/Day | {user_profile['hours_per_day']}h |
| 🎯 Total Hours | {user_profile['total_hours']}h |
| 🧠 Skill Level | {user_profile['skill_level'].capitalize()} |
| 🏁 Goal | {user_profile['goal'].replace('_', ' ').title()} |
| 📖 Source | {pdf_metadata.get('title', 'PDF')} |

---

## 🗓️ Study Schedule

| Day | Title | Type |
|-----|-------|------|
{days_table}

---

## 📝 All Notes

{notes_links}

---

## 📊 Progress

![[Progress Tracker]]

---
*Generated by StudyVault on {datetime.today().strftime('%Y-%m-%d')}*
"""

    (base / "📚 Index.md").write_text(index_content, encoding="utf-8")
    written.append(f"{subject}/📚 Index.md")

    # --- Write Progress Tracker ---
    progress_rows = "\n".join(
        f"| [[Day {num:02d} - {sanitize_filename(title)}\\|Day {num}]] | {title} | ⬜ Not Started | |"
        for num, _, title, _ in day_titles
    )

    progress_content = f"""---
title: "Progress Tracker"
type: tracker
tags: [tracker, {subject.lower().replace(' ', '-')}]
---

# 📊 Progress Tracker — {study_plan['subject']}

Update the status column as you go:
- ⬜ Not Started
- 🔄 In Progress  
- ✅ Complete
- ⏭ Skipped

| Day | Title | Status | Notes |
|-----|-------|--------|-------|
{progress_rows}

---

## 🏆 Milestones
- [ ] Completed Day 1 (Orientation)
- [ ] Reached halfway point (Day {user_profile['total_days'] // 2})
- [ ] Completed final review
- [ ] Finished all {user_profile['total_days']} days! 🎉
"""

    (base / "Meta" / "Progress Tracker.md").write_text(progress_content, encoding="utf-8")
    written.append(f"{subject}/Meta/Progress Tracker.md")

    # --- Write Profile ---
    profile_content = f"""---
title: "Study Profile"
type: meta
---

# 🧠 Your Study Profile

| Setting | Value |
|---------|-------|
| 📅 Total Days | {user_profile['total_days']} |
| ⏱ Hours/Day | {user_profile['hours_per_day']}h |
| 🧠 Skill Level | {user_profile['skill_level']} |
| 🏁 Goal | {user_profile['goal']} |
| 📖 Learning Style | {user_profile['learning_style']} |
| 🔴 Hard Topics | {', '.join(user_profile['hard_topics']) or 'None specified'} |
| 🟢 Easy Topics | {', '.join(user_profile['easy_topics']) or 'None specified'} |
| 🧪 Quizzes | {'Enabled' if user_profile['include_quizzes'] else 'Disabled'} |
| 📌 TL;DRs | {'Enabled' if user_profile['include_summaries'] else 'Disabled'} |
"""

    (base / "Meta" / "Profile.md").write_text(profile_content, encoding="utf-8")
    written.append(f"{subject}/Meta/Profile.md")

    return written
