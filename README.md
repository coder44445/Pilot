# Pilot

> Turn any PDF into a personalized, day-by-day Obsidian study vault — in one command.

---

## Before You Start

Pilot needs write access to the folder where your vault will be created.
If the folder doesn't exist yet, Pilot will create it — but only if you have permission to write there.

**Windows**

Right-click the parent folder (e.g. `C:\Users\YourName\`) → Properties → Security → Edit → give your user **Full Control**.

Or use a folder inside your user directory where you already have write access:
```
C:\Users\YourName\Documents\MyVault
```
Avoid paths like `C:\Program Files\` or `C:\Windows\` — Windows blocks writes there.

**macOS / Linux**

```bash
# Check permissions
ls -ld /path/to/your/vault

# Fix if needed
chmod u+w /path/to/your/vault

# If the folder doesn't exist yet, create it first
mkdir -p /path/to/your/vault
```

**Running as admin / sudo — don't.**
It will work, but files created as root can cause permission issues later when Obsidian (running as your normal user) tries to read them. Fix the folder permissions instead.

---

## What It Does

1. **Ingests a PDF** — extracts all text, respects structure
2. **Asks you 7 questions** — time available, skill level, hard/easy topics, goal
3. **Calls an LLM** — OpenAI or local Ollama (your choice)
4. **Writes an Obsidian vault** with:
   - `_Index.md` — master hub linking everything
   - `Days/Day 01 - ....md` through `Day N` — daily study plans with tasks
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
ollama pull qwen3:4b       # Recommended for most machines
ollama pull qwen3:0.6b     # If you're on a machine
ollama serve
```

---

## Usage

### Basic

```bash
python main.py --pdf path/to/book.pdf --vault ~/Documents/MyVault
```

### Using URLs

Instead of a PDF, provide a URL to extract content from:

```bash
python main.py --url https://example.com/article --vault ~/Documents/MyVault
```

Requires: `pip install requests beautifulsoup4`

### Specify LLM upfront

```bash
# OpenAI
python main.py --pdf book.pdf --vault ~/vault --llm openai --model gpt-4o

# Ollama
python main.py --pdf book.pdf --vault ~/vault --llm ollama --model qwen3:4b
```

### Resume after a crash or interruption

Just run the exact same command again. Pilot saves progress after every step — completed nodes are skipped automatically.

```bash
# First run (interrupted halfway)
python main.py --pdf book.pdf --vault ~/vault --llm ollama --model qwen3:4b

# Rerun — resumes from where it stopped, PDF is not re-read
python main.py --pdf book.pdf --vault ~/vault --llm ollama --model qwen3:4b
```

### Force a fresh start

```bash
python main.py --pdf book.pdf --vault ~/vault --llm ollama --model qwen3:4b --restart
```

### Add new topics to an existing vault

```bash
# Generate new topics from a different source and merge them into your vault
# Preserves all your existing notes and just adds new topics
python main.py --pdf new_book.pdf --vault ~/vault --merge
```

This is useful for:
- Adding supplementary material to your existing vault
- Covering more topics without losing your manual edits
- Building a comprehensive study guide from multiple sources

---

## Docker Setup

### Quick Start (All-in-One)

If you have Docker and Docker Compose installed:

```bash
# 1. Place your PDFs in ./input/
cp path/to/your/book.pdf ./input/

# 2. Run the full stack (Pilot + Ollama)
docker-compose up --build

# 3. In another terminal, run Pilot
docker-compose exec pilot python main.py --pdf /data/input/book.pdf --vault /data/output/MyVault
```

Generated vaults appear in `./output/` on your machine.

### Using an Existing Ollama Instance

If you already have Ollama running (not in Docker):

1. Update `docker-compose.yml`:
   ```yaml
   environment:
     OLLAMA_HOST: "http://host.docker.internal:11434"  # macOS/Windows
     # or
     OLLAMA_HOST: "http://172.17.0.1:11434"  # Linux
   ```

2. Run just the Pilot service:
   ```bash
   docker run -it \
     --rm \
     -v ./input:/data/input \
     -v ./output:/data/output \
     -v ./pilot.config.yml:/app/pilot.config.yml \
     -e OLLAMA_HOST=http://host.docker.internal:11434 \
     pilot-app \
     python main.py --pdf /data/input/book.pdf --vault /data/output/MyVault
   ```

### Setup Instructions

1. **Install Docker:**
   - [Docker Desktop](https://www.docker.com/products/docker-desktop) (macOS/Windows)
   - [Docker Engine](https://docs.docker.com/engine/install/) (Linux)

2. **Organize your files:**
   ```bash
   mkdir input output
   cp your_book.pdf input/
   ```

3. **Configure pilot.config.yml** (if needed):
   ```yaml
   llm:
     provider: ollama
     model: qwen3:4b
     ollama_url: http://ollama:11434
   ```

4. **Optional: Pull Ollama models in advance:**
   ```bash
   # Download the model once (speeds up first run)
   docker-compose run ollama ollama pull qwen3:4b
   ```

5. **Run:**
   ```bash
   docker-compose up
   # Then in another terminal:
   docker-compose exec pilot python main.py --pdf /data/input/book.pdf --vault /data/output/MyVault
   ```

### Troubleshooting Docker

**Port 11434 already in use:**
```yaml
# In docker-compose.yml, change the Ollama port:
ports:
  - "11435:11434"  # Use 11435 instead
```

**Ollama service fails to start:**
- Check logs: `docker-compose logs ollama`
- Ensure at least 4GB RAM available for Docker
- On Windows/macOS, increase Docker's memory in Docker Desktop settings

**Permission errors in output folder:**
```bash
# Fix ownership
sudo chown -R $USER:$USER output/
```

---

## What the Vault Looks Like

```
MyVault/
└── Python Crash Course/
    ├── _Index.md                          ← Start here
    ├── Days/
    │   ├── Day 01 - Orientation.md
    │   ├── Day 02 - Variables and Data Types.md
    │   ├── Day 07 - Review Day.md
    │   └── ...
    ├── Notes/
    │   ├── Variables and Data Types.md
    │   ├── Functions.md
    │   ├── Classes and OOP.md
    │   └── ...
    ├── .anki/
    │   └── Flashcards.csv                 ← Anki import-ready quizzes
    └── Meta/
        ├── Progress Tracker.md
        └── Profile.md
```

---

## Personalization

| Question | Effect |
|----------|--------|
| Hard topics | More time, deeper notes, more examples |
| Easy topics | Faster pace, adds practice exercises |
| Goal (exam / project / deep / quick) | Changes note depth and activity types |
| Skill level | Calibrates terminology and assumed prior knowledge |
| Learning style | Theory-first vs examples-first structure |

---

## Obsidian Tips

- **Graph view** (Ctrl+G) — see topic connections via `[[wiki-links]]`
- **Dataview plugin** — query your progress: `TABLE status FROM "Days"`
- **Checkboxes** — check off activities in the day files as you complete them

---

## Troubleshooting

**"Permission denied" when writing files**
→ See the [Before You Start](#before-you-start) section above.

**"Cannot reach Ollama"**
→ Make sure `ollama serve` is running in a separate terminal.

**Ollama truncating input / slow responses**
→ Use a model with at least 4k context. `qwen3:4b` is the recommended minimum.
→ Check that `ollama serve` shows no errors in its terminal.

**Pipeline crashed halfway**
→ Just rerun the same command. Progress is saved automatically.

**Want to start over from scratch**
→ Add `--restart` to your command, or delete `{vault}/.pilot_checkpoints.db`.

---

## Requirements

- Python 3.10+
- `pymupdf` or `pdfplumber`
- `langgraph`, `langgraph-checkpoint-sqlite`
- `openai` (if using OpenAI) or Ollama running locally
- `rich`

---

## Roadmap

- [x] URL / website scraping → same pipeline ✅
- [ ] YouTube transcript support
- [x] Anki flashcard export from quiz sections ✅
- [x] Re-run on existing vault to add new topics ✅
- [ ] Obsidian plugin (no CLI needed)