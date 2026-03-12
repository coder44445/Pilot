"""
Reads pilot.config.yml from the project root.

Both the CLI and MCP server use this so LLM settings are
configured in one place and never need to be passed as arguments.

Falls back to safe defaults if the file is missing or a key is absent.
Raises a clear error if the file exists but is malformed YAML.
"""

import os
from pathlib import Path
from typing import Optional

# Project root = directory containing this src/ folder
_ROOT = Path(__file__).parent.parent.parent
_CONFIG_FILE = _ROOT / "config" / "pilot.config.yml"

# Defaults (used when key is missing from config)
_LLM_DEFAULTS = {
    "provider":   "ollama",
    "model":      "qwen3:4b",
    "ollama_url": "http://localhost:11434",
}

_PROFILE_DEFAULTS = {
    "total_days":        14,
    "hours_per_day":     2,
    "skill_level":       "beginner",
    "goal":              "practical_project",
    "learning_style":    "mixed",
    "include_quizzes":   True,
    "include_summaries": True,
}


def _load_yaml() -> dict:
    """Load and parse pilot.config.yml. Returns {} if file not found."""
    if not _CONFIG_FILE.exists():
        return {}
    try:
        import yaml
        with open(_CONFIG_FILE, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        # PyYAML not installed — try a minimal key=value parser as fallback
        return _minimal_parse(_CONFIG_FILE)
    except Exception as e:
        raise ValueError(
            f"Could not parse {_CONFIG_FILE}:\n  {e}\n"
            f"  Check the file for YAML syntax errors."
        )


def _minimal_parse(path: Path) -> dict:
    """
    Bare-minimum YAML parser for flat key: value lines.
    Only used if PyYAML is not installed.
    Handles the llm: and defaults: sections by ignoring section headers.
    """
    result: dict = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.endswith(":"):
            continue
        if ":" in line:
            key, _, val = line.partition(":")
            val = val.strip().strip('"').strip("'")
            if val.lower() == "true":
                val = True
            elif val.lower() == "false":
                val = False
            elif val.isdigit():
                val = int(val)
            result[key.strip()] = val
    return result


def load_llm_config() -> dict:
    """
    Return LLM config from pilot.config.yml.

    Returns dict with keys: provider, model, ollama_url
    Falls back to defaults for any missing key.
    Checks OPENAI_API_KEY env var as well.
    """
    raw  = _load_yaml()
    llm  = raw.get("llm", raw)   # support both nested and flat

    cfg = {
        "provider":   llm.get("provider",   _LLM_DEFAULTS["provider"]),
        "model":      llm.get("model",       _LLM_DEFAULTS["model"]),
        "ollama_url": llm.get("ollama_url",  _LLM_DEFAULTS["ollama_url"]),
    }

    # Allow openai_api_key in config (less secure than env var but convenient)
    api_key = llm.get("openai_api_key") or os.environ.get("OPENAI_API_KEY", "")
    if api_key:
        os.environ["OPENAI_API_KEY"] = api_key

    return cfg


def load_default_profile() -> dict:
    """
    Return default study profile from pilot.config.yml.
    Used by MCP server (CLI always asks interactively instead).
    """
    raw      = _load_yaml()
    defaults = raw.get("defaults", raw)

    return {
        k: defaults.get(k, _PROFILE_DEFAULTS[k])
        for k in _PROFILE_DEFAULTS
    }


def config_file_path() -> Path:
    return _CONFIG_FILE


def print_config_summary(console) -> None:
    """Print current effective config to the terminal."""
    llm     = load_llm_config()
    profile = load_default_profile()
    source  = str(_CONFIG_FILE) if _CONFIG_FILE.exists() else "built-in defaults"

    console.print(f"\n[dim]Config: {source}[/dim]")
    url_part = f" ({llm['ollama_url']})" if llm['provider'] == 'ollama' else ""
    console.print(
        f"[dim]  LLM: {llm['provider']} / {llm['model']}{url_part}[/dim]"
    )
    console.print(
        f"[dim]  Defaults: {profile['total_days']}d × {profile['hours_per_day']}h/d, "
        f"{profile['skill_level']}, {profile['goal']}[/dim]\n"
    )