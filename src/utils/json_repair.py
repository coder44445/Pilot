"""
Robust JSON repair for small-model LLM outputs.

Handles the most common failure modes:
  - <think>...</think> tags  (qwen3, deepseek-r1)
  - ```json ... ``` fences
  - Truncated output (missing closing brackets/braces)
  - Trailing commas before } or ]
"""

import re
import json


def repair_json(raw: str) -> dict:
    """
    Parse LLM output as JSON, recovering from common failure modes.
    Raises ValueError with a clear message if all recovery attempts fail.
    """
    text = raw.strip()

    # 1. Strip <think> blocks
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    # 2. Strip markdown fences
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    # 3. Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 4. Find first { and work from there
    m = re.search(r"\{", text)
    if m:
        text = text[m.start():]

    # 5. Fix trailing commas before } or ]
    text = re.sub(r",\s*([}\]])", r"\1", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 6. Close truncated JSON
    text = _close_truncated(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Could not parse LLM output as JSON.\n"
            f"Parse error: {e}\n"
            f"Response (first 500 chars):\n{raw[:500]}"
        )


def _close_truncated(text: str) -> str:
    """
    Walk the string tracking open brackets/braces.
    Append whatever closing tokens are needed to make it valid.
    """
    stack = []
    in_string   = False
    escape_next = False

    for ch in text:
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in ("{", "["):
            stack.append("}" if ch == "{" else "]")
        elif ch in ("}", "]") and stack and stack[-1] == ch:
            stack.pop()

    text = text.rstrip().rstrip(",")
    return text + "".join(reversed(stack))
