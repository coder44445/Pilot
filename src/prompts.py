"""
All LLM prompts in one file.

Keeping prompts here means:
  - Easy to tune without touching node logic
  - Easy to A/B test different prompt styles
  - Easy to add a new input source (URL scraping) by adding prompts here
"""


# ── Topic extraction (per chunk) ───────────────────────────────────────────── #

EXTRACT_SYSTEM = """\
You extract topic lists from educational text.
Output ONLY valid JSON. No thinking tags, no explanation, no markdown fences.\
"""

EXTRACT_USER = """\
Extract topics/chapters from this book segment.

Book: {title}  |  Segment {chunk_num} of {total_chunks}
---
{text}
---

Output ONLY this JSON (3-8 topics from this segment):
{{
  "topics": [
    {{
      "title": "Topic Title",
      "difficulty": "beginner",
      "estimated_hours": 1.5,
      "description": "one sentence",
      "subtopics": ["sub1", "sub2"]
    }}
  ]
}}

difficulty must be: beginner, intermediate, or advanced.
Only include topics present in THIS segment.
Output ONLY the JSON object.\
"""


# ── Topic merge / consolidation ────────────────────────────────────────────── #

MERGE_SYSTEM = """\
You are a curriculum designer. Output ONLY valid JSON. No explanation.\
"""

MERGE_USER = """\
Consolidate these book topics. Remove true duplicates, merge very similar ones, keep distinct topics.

{raw_topics}

Output ONLY:
{{
  "subject": "short subject name",
  "description": "one sentence about the book",
  "topics": [
    {{
      "title": "Topic Title",
      "difficulty": "beginner",
      "estimated_hours": 1.5,
      "description": "one sentence",
      "subtopics": ["sub1"]
    }}
  ]
}}\
"""


# ── Study schedule ─────────────────────────────────────────────────────────── #

SCHEDULE_SYSTEM = """\
You are a study planner. Output ONLY valid JSON. No explanation.\
"""

SCHEDULE_USER = """\
Create a {total_days}-day study schedule.

Topics (use these exact ids):
{topics_simple}

Constraints:
- Day 1 = orientation overview
- Day {total_days} = review + consolidation
- Every 5-7 days include a review day
- {hours_per_day}h available per day
- Skill level: {skill_level} | Goal: {goal}
- Hard topics (more time + depth): {hard_topics}
- Easy topics (less time, add practice): {easy_topics}

Output ONLY this JSON:
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
        {{
          "topic_id": "t1",
          "topic_title": "Title",
          "focus": "specific focus area",
          "time_allocation": 1.5,
          "depth": "overview",
          "activities": ["activity 1", "activity 2"]
        }}
      ]
    }}
  ]
}}\
"""


# ── Topic notes ────────────────────────────────────────────────────────────── #

NOTES_SYSTEM = """\
You write study notes in Markdown. Be clear, practical, and memorable.\
"""

NOTES_USER = """\
Write study notes for: {topic_title}

Description: {topic_description}
Subtopics: {subtopics}
Level: {skill_level} | Goal: {goal} | Style: {learning_style} | Depth: {depth}
{hard_easy_instruction}

Structure your notes exactly like this:

## {topic_title}

### 🎯 What You'll Learn
- (2-3 learning outcomes)

### 📖 Core Concepts
(Main explanation with examples)

### 🔑 Key Points
- (bullet list of the most important things)

{tldr_section}

### 💡 Examples
(2-3 concrete examples or analogies)

### ⚠️ Common Mistakes
(2-3 things people commonly get wrong)

{quiz_section}

### 🔗 Related Topics
(use [[wiki-link]] format)

---
*Estimated study time: {time_allocation}h*\
"""
