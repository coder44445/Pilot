"""
Text chunking and topic deduplication utilities.

Kept separate so they can be reused by URL scraping later
without importing anything from the pipeline.
"""

import re


CHUNK_SIZE_WORDS = 1500
CHUNK_OVERLAP    = 200


def chunk_text(
    text:       str,
    chunk_size: int = CHUNK_SIZE_WORDS,
    overlap:    int = CHUNK_OVERLAP,
) -> list[str]:
    """
    Split text into overlapping word-based chunks.

    Overlap ensures topics that span a chunk boundary
    are captured by at least one chunk.
    """
    words  = text.split()
    chunks = []
    start  = 0

    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start += chunk_size - overlap

    return chunks


def dedup_topics(all_topics: list[dict]) -> list[dict]:
    """
    Merge topics collected from multiple chunks.

    Strategy:
    - Normalise title → lowercase alphanum only
    - Keep first occurrence as canonical entry
    - Merge subtopics from duplicates (union)
    - Keep the longer description
    - Re-assign clean sequential ids (t1, t2, ...)
    """
    seen: dict[str, dict] = {}

    def _norm(title: str) -> str:
        return re.sub(r"[^a-z0-9]", "", title.lower())

    for topic in all_topics:
        key = _norm(topic.get("title", ""))
        if not key:
            continue

        if key not in seen:
            seen[key] = dict(topic)
        else:
            existing = set(seen[key].get("subtopics", []))
            incoming = set(topic.get("subtopics", []))
            seen[key]["subtopics"] = sorted(existing | incoming)

            if len(topic.get("description", "")) > len(seen[key].get("description", "")):
                seen[key]["description"] = topic["description"]

    result = []
    for i, topic in enumerate(seen.values(), 1):
        topic["id"] = f"t{i}"
        result.append(topic)

    return result


def ensure_topic_defaults(topics: list[dict]) -> list[dict]:
    """Ensure every topic has all required fields with safe defaults."""
    for i, t in enumerate(topics):
        t["id"]                      = f"t{i + 1}"
        t.setdefault("title",          f"Topic {i + 1}")
        t.setdefault("description",    "")
        t.setdefault("subtopics",      [])
        t.setdefault("estimated_hours", 1.5)
        t.setdefault("difficulty",     "intermediate")
    return topics
