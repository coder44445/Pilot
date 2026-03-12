# Interactive Interface Guide

## Overview

Pilot now includes an advanced **interactive interface** that appears during the topic review phase. This allows you to:

- **Query content** using RAG (Retrieval-Augmented Generation) to ask questions about your PDF
- **Correct LLM mistakes** with automatic error detection and suggestions
- **Edit topics** manually (title, difficulty, hours, description)
- **Add custom topics** that the LLM missed
- **Merge duplicate topics** intelligently
- **Update your learner profile** to influence the study plan

## Enabling Interactive Mode

Run Pilot with the `--interactive` flag:

```bash
python main.py --pdf book.pdf --vault ~/MyVault --interactive
```

### Optional Flags

- **`--no-rag`** — Disable RAG features (content search/querying)
  ```bash
  python main.py --pdf book.pdf --vault ~/MyVault --interactive --no-rag
  ```

- **`--skip-corrections`** — Disable automatic error detection
  ```bash
  python main.py --pdf book.pdf --vault ~/MyVault --interactive --skip-corrections
  ```

- **Both** — Minimal interactive mode (just edit/merge topics)
  ```bash
  python main.py --pdf book.pdf --vault ~/MyVault --interactive --no-rag --skip-corrections
  ```

## Menu Options

When you reach the interactive session, you'll see this menu:

```
Menu
  1. Review topics         - See all extracted topics with details
  2. Query content (RAG)   - Ask questions about the PDF content
  3. Edit topic details    - Change title, difficulty, hours, description
  4. Correct LLM mistakes  - Auto-detect and fix extraction errors
  5. Add custom topic      - Create a new topic manually
  6. Merge topics          - Combine two topics into one
  7. Update learner profile- Set hard/easy topics, learning style
  8. Save and continue     - Approve changes and proceed to scheduling
  9. Abort (discard)       - Exit without saving changes
```

---

## 1. Review Topics

View all extracted topics in an organized list:

```
Found 25 topics from PDF extraction.

  1. Python Basics          ~1.5h · beginner
       Introduction to Python syntax and simple programs
  2. Data Structures        ~2.5h · intermediate
       Lists, dictionaries, sets, and their use cases
  3. OOP Concepts           ~3.0h · advanced
       Classes, inheritance, polymorphism, and design patterns
```

**Features:**
- See difficulty level (🟢 beginner, 🟡 intermediate, 🔴 advanced)
- See estimated hours for each topic
- View descriptions to understand what's covered
- Select a topic number to see detailed view

**Detailed View:**
Select a topic to see:
- Full description
- Subtopics (if extracted)
- Enhanced context from PDF (if RAG enabled)
- Related topics based on content similarity

---

## 2. Query Content (RAG)

Ask natural language questions about your PDF to find relevant content:

```
🔍 Query Content (RAG)
---
Ask a question about the PDF content to find relevant topics and excerpts

Question: What are the main machine learning algorithms?
```

**What you get:**

1. **Matched Topics** — Topics from extraction that match your question
   ```
   • Machine Learning Basics (match: 95%)
   • Supervised Learning (match: 88%)
   • Neural Networks (match: 82%)
   ```

2. **Document Excerpts** — Relevant passages from the PDF
   ```
   [1] "Machine learning is a subset of artificial intelligence... supervised learning 
       includes classification and regression..."
   ```

3. **Generated Answer** (if LLM available) — AI-powered synthesis
   ```
   Answer: The main machine learning algorithms include supervised learning (classification, 
   regression), unsupervised learning (clustering), and reinforcement learning...
   ```

**Use cases:**
- **Verify completeness** — "Are there chapters on advanced topics?"
- **Find related content** — "What topics relate to neural networks?"
- **Check coverage** — "Is exception handling covered?"
- **Explore PDFs** — Interactive way to understand document structure

---

## 3. Edit Topic Details

Modify individual topic fields:

```
Editing: Python Basics

  1. Title
  2. Difficulty
  3. Estimated hours
  4. Description
  5. Back

Field to edit: 2

Options: beginner, intermediate, advanced
New difficulty: intermediate
✓ Difficulty updated
```

**Editable fields:**
- **Title** — Topic name
- **Difficulty** — beginner | intermediate | advanced
- **Estimated Hours** — How long to study (e.g., 2.5)
- **Description** — One-sentence summary

**Why edit?**
- Fix LLM extraction errors
- Adjust difficulty based on your knowledge level
- Update estimates based on actual learning pace
- Improve topic descriptions for clarity

---

## 4. Correct LLM Mistakes

Automatically detect and fix common extraction errors:

```
🔧 Correct Mistakes
---
Analyzing topics for potential errors...

Found 3 potential issues:

  1. Duplicate topic detected
     Topic: Machine Learning
     Severity: medium

  2. Missing description
     Topic: Advanced Python
     Severity: low

  3. Invalid difficulty: 'expert'
     Topic: System Design
     Severity: medium
```

**Auto-detected issues:**

### Duplicate Topics
Finds topics with very similar titles:
```
Original: Machine Learning
Duplicate: ML Basics

Options:
  m - Merge (combine descriptions and subtopics)
  1 - Keep first
  2 - Keep second
  s - Skip
```

### Missing Fields
Detects topics without key information:
```
Missing description for "Advanced Python"

Suggested description (from PDF content):
  "Covers decorators, generators, context managers, and advanced OOP patterns"

Use this description? (y/n): y
✓ Description added
```

### Invalid Values
Fixes topics with incorrect field values:
```
Current difficulty: expert
Set to (beginner/intermediate/advanced): advanced
✓ Difficulty corrected
```

**How it works:**
1. Analyzes all topics for consistency
2. Uses PDF content to suggest fixes
3. Presents issues in priority order
4. Lets you accept/modify/skip each fix

---

## 5. Add Custom Topic

Manually create topics the LLM missed:

```
➕ Add Custom Topic
---
Topic title: Docker Fundamentals

Difficulty: beginner | intermediate | advanced
Difficulty: beginner

Estimated hours: 3.0

Description (optional): Learn containerization with Docker

Found related content in PDF. Generate subtopics? (y/n): y
✓ Subtopics added

✓ Topic 'Docker Fundamentals' added
```

**Features:**
- Enter topic details manually
- RAG automatically searches PDF for related content
- LLM can suggest relevant subtopics
- Topics are added to your study plan

**When to use:**
- LLM missed important topics
- You want to add personal learning goals
- You need specialized topics not in the PDF

---

## 6. Merge Topics

Combine two closely related topics:

```
🔀 Merge Topics
---
  1. Machine Learning Basics    ~2.0h · intermediate
  2. Supervised Learning        ~1.5h · intermediate
  3. Neural Networks            ~3.0h · advanced

First topic: 1
Second topic: 2

Merging:
  1. Machine Learning Basics
  2. Supervised Learning

✓ Merged into 'Machine Learning Basics'
```

**What happens:**
- Topic 1 keeps its title
- Descriptions are combined
- Subtopics are merged (duplicates removed)
- Topic 2 is removed
- Difficulty/hours stay from Topic 1

**When to merge:**
- LLM created near-duplicate topics
- Topics are closely related and should be together
- You want to reduce the number of topics

---

## 7. Update Learner Profile

Adjust your learning profile for better study planning:

```
👤 Update Profile
---
Current profile:
  time_available: 2.0 (hours per week)
  learning_style: visual
  hard_topics: ['Calculus', 'Statistics']
  easy_topics: ['Basics', 'Fundamentals']

Field to update: hard_topics
New value for 'hard_topics': ['Machine Learning', 'Advanced Algorithms']
✓ Updated hard_topics
```

**Profile fields:**
- **time_available** — Hours per week you can study
- **learning_style** — visual, auditory, reading, kinesthetic
- **hard_topics** — Topics that are difficult for you
- **easy_topics** — Topics you find easy

**Why update?**
- Hard topics get more time and resources in the study plan
- Easy topics can be covered quickly
- Time available is used to calculate realistic daily schedules
- Learning style influences explanation type and resources

---

## Workflow Examples

### Example 1: Verify and Fix Extraction

```bash
python main.py --pdf python-book.pdf --vault ~/PythonVault --interactive
```

1. **Review** all topics (Menu → 1)
2. **Correct** any issues automatically (Menu → 4)
3. **Edit** topics that still have problems (Menu → 3)
4. **Save** (Menu → 8)

### Example 2: Deep Dive on Related Topics

```bash
python main.py --pdf machine-learning.pdf --vault ~/MLVault --interactive
```

1. **Query** for topics (Menu → 2)
   - "What are the different types of learning?"
   - "How do neural networks work?"
   - "What's the difference between supervised and unsupervised?"

2. **Review** relevant topics (Menu → 1 → select topic)
3. **Merge** related topics (Menu → 6)
4. **Save** (Menu → 8)

### Example 3: Customize Study Plan

```bash
python main.py --pdf advanced-python.pdf --vault ~/AdvPythonVault --interactive
```

1. **Add** topics you want to focus on (Menu → 5)
   - "Async Programming"
   - "Performance Optimization"

2. **Mark hard/easy** in your profile (Menu → 7)
   - Set "Metaclasses" as hard (needs more time)
   - Set "Basic Syntax" as easy (skip basics)

3. **Save** (Menu → 8)

---

## Performance Tips

### For Large PDFs
- Use **`--no-rag`** to skip content search (faster session, less LLM calls)
- Use **`--skip-corrections`** to skip auto-detection (faster process)

### For RAG Queries
- Be **specific** in your questions
- Ask about **topics, concepts, or chapters**
- Avoid very long or vague questions

### For Corrections
- Review automatic suggestions but **verify them**
- Use domain knowledge to override suggestions
- Multiple corrections can be applied in sequence

---

## Troubleshooting

### "RAG features are disabled"
You used `--no-rag` flag. Re-run without it to enable RAG.

### "LLM not available for corrections"
LLM failed to connect. Check:
- Is your LLM provider running? (Ollama, OpenAI)
- Is `OPENAI_API_KEY` set? (for OpenAI)
- Correct `ollama_url`? (for local Ollama)

### Query returned no results
- Try a simpler query
- Use topic names instead of descriptions
- Check if the PDF contains the information

### Duplicate detection too aggressive
Use `--skip-corrections` to disable auto-detection, then manually merge topics.

---

## Advanced: Programmatic Access

You can use the interactive components in your own scripts:

```python
from src.interactive import InteractiveSession
from src.rag_engine import RAGEngine
from src.llm import LLMClient

# Initialize
llm = LLMClient(provider="openai", model="gpt-4o")
rag = RAGEngine(pdf_text, topics, llm)

# Query
result = rag.query("What are the main topics?")
print(result["answer"])

# Interactive session
session = InteractiveSession(pdf_text, topics, profile, llm)
approved, updated_profile, should_continue = session.run_interactive_loop()
```

---

## Summary

| Feature | Purpose | Flag to Disable |
|---------|---------|-----------------|
| **Query (RAG)** | Ask questions about PDF | `--no-rag` |
| **Auto-correct** | Find and fix errors | `--skip-corrections` |
| **Topic Editing** | Modify extracted topics | Always available |
| **Custom Topics** | Add your own topics | Always available |
| **Merging** | Combine related topics | Always available |
| **Profile Update** | Adjust learner settings | Always available |

Start with `--interactive` to unlock all features!
