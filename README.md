# 📚 StudyVault

> Turn any PDF into a personalized, day-by-day Obsidian study vault — in one command.

---

## What It Does

1. **Ingests a PDF** — extracts all text, respects structure
2. **Asks you 7 questions** — time available, skill level, hard/easy topics, goal
3. **Calls an LLM** — OpenAI or local Ollama (your choice)
4. **Writes an Obsidian vault** with:
   - `📚 Index.md` — master hub linking everything
   - `Days/Day 01 - ...md` through `Day N` — daily study plans with tasks
   - `Notes/Topic Name.md` — deep notes per topic with examples, quizzes, TL;DRs
   - `Meta/Progress Tracker.md` — checkbox-based progress tracker
   - Full `[[wiki-links]]` between topics for the graph view

---

## Setup

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

For PDF extraction, install **one** of:
```bash
pip install pymupdf        # Recommended (fast, accurate)
pip install pdfplumber     # Alternative
```

For LLM access:
```bash
pip install openai         # If using OpenAI
# For Ollama — no pip install needed, just run Ollama locally
```

### 2. Set up your LLM

**Option A — OpenAI:**
```bash
export OPENAI_API_KEY=sk-...
```

**Option B — Ollama (local, free):**
```bash
# Install Ollama from https://ollama.com
ollama serve
ollama pull llama3.1       # Or any other model
```

---

## Usage

### Basic usage

```bash
python main.py --pdf path/to/your/book.pdf --vault ~/Documents/ObsidianVault
```

### Specify LLM upfront (skips the prompt)

```bash
# OpenAI
python main.py --pdf book.pdf --vault ~/vault --llm openai

# Ollama with a specific model
python main.py --pdf book.pdf --vault ~/vault --llm ollama --model llama3.2
```

### Full example

```bash
python main.py \
  --pdf "Python Crash Course.pdf" \
  --vault ~/Documents/MyVault \
  --llm openai \
  --model gpt-4o
```

---

## What the Vault Looks Like

```
MyVault/
└── Python Crash Course/
    ├── 📚 Index.md              ← Start here
    ├── Days/
    │   ├── Day 01 - Orientation & Overview.md
    │   ├── Day 02 - Variables and Data Types.md
    │   ├── Day 03 - Control Flow.md
    │   ├── Day 07 - Review Day.md
    │   └── ...
    ├── Notes/
    │   ├── Variables and Data Types.md
    │   ├── Functions.md
    │   ├── Classes and OOP.md
    │   └── ...
    └── Meta/
        ├── Progress Tracker.md
        └── Profile.md
```

---

## Personalization Logic

The tool asks you about:

| Question | Effect on plan |
|----------|---------------|
| Hard topics | Gets 20-40% more time, deeper notes, more examples |
| Easy topics | Goes faster but includes practice exercises |
| Goal (exam/project/deep/quick) | Changes note depth and activity types |
| Skill level | Calibrates terminology and assumed prior knowledge |
| Learning style | Theory-first vs examples-first structure |

---

## Obsidian Tips

1. **Graph view** — Open it (Ctrl+G) to see topic connections via `[[wiki-links]]`
2. **Daily notes** — Use the day files as your daily note template
3. **Dataview plugin** — Query your progress: `TABLE status FROM "Days"`
4. **Checkboxes** — Check off activities as you complete them

---

## Roadmap

- [ ] URL/website scraping → same pipeline
- [ ] YouTube transcript support
- [ ] Spaced repetition flashcard export (Anki)
- [ ] Re-run on the same vault to add new topics
- [ ] Obsidian plugin version (no CLI needed)

---

## Requirements

- Python 3.10+
- `pymupdf` or `pdfplumber`
- `openai` (if using OpenAI) or Ollama running locally
- `rich` (optional, for pretty terminal output)
