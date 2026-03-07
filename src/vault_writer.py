"""
Writes the generated study plan into an Obsidian vault.

Safety features:
- preflight_check: creates vault dir if missing, verifies write permission, checks disk space
- sanitize_filename: strips Windows-invalid chars, collapses spaces, truncates to 80 chars
- _safe_write: atomic write via .tmp + rename, isolated per-file so one failure doesnt crash all
- Windows long path support via \\\\?\\  prefix
- Emoji stripped from filenames on Windows
"""

import os
import re
import shutil
import platform
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Tuple

from src.display import console

_IS_WINDOWS = platform.system() == "Windows"

# Characters invalid in Windows filenames
_WIN_INVALID_CHARS = r'\/:*?"<>|'

# Emoji regex - strip on Windows to avoid explorer/cmd issues
_EMOJI_RE = re.compile(
    "[\U0001F300-\U0001F9FF"
    "\U00002600-\U000027BF"
    "\U0001FA00-\U0001FAFF]+",
    flags=re.UNICODE,
)


def sanitize_filename(name: str, max_len: int = 80) -> str:
    """Make a string safe as a filename on Windows + POSIX."""
    for ch in _WIN_INVALID_CHARS:
        name = name.replace(ch, " ")
    if _IS_WINDOWS:
        name = _EMOJI_RE.sub("", name)
    name = " ".join(name.split())   # collapse whitespace
    name = name[:max_len].strip()
    return name or "untitled"


def _win_path(p: Path) -> Path:
    """Prepend long-path prefix on Windows to bypass 260-char MAX_PATH."""
    if _IS_WINDOWS:
        resolved = str(p.resolve())
        if not resolved.startswith("\\\\?\\"):
            return Path("\\\\?\\" + resolved)
    return p


def _safe_write(path: Path, content: str) -> bool:
    """
    Atomic file write: write to .tmp then rename.
    Returns True on success. Logs error and returns False on failure.
    Does NOT raise — callers collect failures and continue.
    """
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        _win_path(tmp).write_text(content, encoding="utf-8")
        _win_path(tmp).replace(_win_path(path))
        return True
    except PermissionError as e:
        console.print(f"  [red]Permission denied:[/red] {path.name} — {e}")
    except OSError as e:
        console.print(f"  [red]Write error:[/red] {path.name} — {e}")
    try:
        if tmp.exists():
            tmp.unlink()
    except Exception:
        pass
    return False


def _mkdir(path: Path) -> None:
    """Create directory tree. Raises clear RuntimeError on failure."""
    try:
        _win_path(path).mkdir(parents=True, exist_ok=True)
    except PermissionError:
        raise RuntimeError(
            f"Cannot create directory: {path}\n"
            f"  Check write access to: {path.parent}"
        )
    except OSError as e:
        raise RuntimeError(f"Cannot create directory {path}: {e}")


def preflight_check(vault_path: Path, estimated_files: int = 50) -> None:
    """
    Validate vault_path before any writes begin.

    - Creates the directory if it does not exist
    - Verifies write permission with a probe file
    - Checks available disk space
    Raises RuntimeError with actionable message on failure.
    """
    if not vault_path.exists():
        console.print(f"  [dim]Creating vault: {vault_path}[/dim]")
        try:
            _win_path(vault_path).mkdir(parents=True, exist_ok=True)
        except PermissionError:
            raise RuntimeError(
                f"Cannot create vault directory: {vault_path}\n"
                f"  Do you have write permission in: {vault_path.parent}?\n"
                f"  On Windows: try a path inside your user folder, e.g. C:\\Users\\YourName\\Vault"
            )
        except OSError as e:
            raise RuntimeError(f"Cannot create vault directory {vault_path}: {e}")

    if not vault_path.is_dir():
        raise RuntimeError(f"Vault path is not a directory: {vault_path}")

    # Permission probe
    probe = vault_path / ".studyvault_probe"
    try:
        _win_path(probe).write_text("ok", encoding="utf-8")
        _win_path(probe).unlink()
    except PermissionError:
        raise RuntimeError(
            f"No write permission: {vault_path}\n"
            f"  Windows: right-click folder > Properties > Security > allow Full Control\n"
            f"  Linux/macOS: chmod u+w \"{vault_path}\""
        )
    except OSError as e:
        raise RuntimeError(f"Cannot write to {vault_path}: {e}")

    # Disk space (rough: 50KB per file)
    try:
        free = shutil.disk_usage(vault_path).free
        need = estimated_files * 50 * 1024
        if free < need:
            raise RuntimeError(
                f"Low disk space: {free // 1024 // 1024}MB free, "
                f"~{need // 1024 // 1024}MB needed.\n"
                f"  Free up space on {vault_path.anchor}"
            )
    except OSError:
        pass

    console.print(f"  [green]✓[/green] Vault path OK: {vault_path}")


def write_vault(
    vault_path:   Path,
    study_plan:   dict,
    user_profile: dict,
    pdf_metadata: dict,
) -> List[str]:
    """
    Write all vault markdown files.
    Returns list of successfully written relative paths.
    Continues writing even if individual files fail.
    """
    subject    = sanitize_filename(study_plan.get("subject", "Study Plan"))
    base       = vault_path / subject
    start_date = datetime.today()
    n_topics   = len(study_plan.get("topics", []))
    n_days     = len(study_plan.get("days", []))

    preflight_check(vault_path, estimated_files=n_topics + n_days + 5)

    for folder in ["Days", "Notes", "Meta"]:
        _mkdir(base / folder)

    written: List[str] = []
    failed:  List[str] = []
    tag_slug = subject.lower().replace(" ", "-")

    # ── Topic notes ───────────────────────────────────────────────────────── #
    topic_file_map: dict = {}

    for topic in study_plan.get("topics", []):
        tid   = topic["id"]
        fname = sanitize_filename(topic["title"])
        notes = study_plan.get("notes_map", {}).get(
            tid, f"## {topic['title']}\n\nNotes coming soon."
        )

        content = "\n".join([
            "---",
            f'title: "{topic["title"]}"',
            "type: note",
            f'topic_id: "{tid}"',
            f'difficulty: "{topic.get("difficulty", "unknown")}"',
            f'estimated_hours: {topic.get("estimated_hours", 1.5)}',
            f"tags: [study, {tag_slug}]",
            f'created: {datetime.today().strftime("%Y-%m-%d")}',
            "---",
            "",
            notes,
        ])

        path = base / "Notes" / f"{fname}.md"
        if _safe_write(path, content):
            topic_file_map[tid] = fname
            written.append(f"{subject}/Notes/{fname}.md")
        else:
            failed.append(f"Notes/{fname}.md")

    # ── Day files ─────────────────────────────────────────────────────────── #
    days: list = study_plan.get("days", [])
    day_titles: List[Tuple] = []

    for day_data in days:
        day_num      = day_data.get("day", 0)
        raw_title    = day_data.get("title", f"Day {day_num}")
        day_title    = sanitize_filename(raw_title)
        day_filename = f"Day {day_num:02d} - {day_title}"
        day_date     = start_date + timedelta(days=day_num - 1)

        topics_md = ""
        for t in day_data.get("topics", []):
            tid       = t.get("topic_id", "")
            note_name = topic_file_map.get(tid, t.get("topic_title", "Unknown"))
            acts      = "\n".join(f"  - [ ] {a}" for a in t.get("activities", []))
            topics_md += (
                f"\n### [[Notes/{note_name}|{note_name}]]\n"
                f"- **Focus:** {t.get('focus', '')}\n"
                f"- **Time:** {t.get('time_allocation', 0)}h\n"
                f"- **Depth:** {t.get('depth', 'standard')}\n\n"
                f"**Activities:**\n{acts}\n"
            )

        prev_link = f"[[Days/Day {day_num-1:02d}]]" if day_num > 1 else "*(start)*"
        next_link = f"[[Days/Day {day_num+1:02d}]]" if day_num < len(days) else "*(finish)*"

        lines = [
            "---",
            f'title: "Day {day_num}: {raw_title}"',
            "type: day-plan",
            f"day: {day_num}",
            f'date: {day_date.strftime("%Y-%m-%d")}',
            "status: not-started",
            f'total_hours: {day_data.get("total_hours", user_profile.get("hours_per_day", 2))}',
            f"tags: [study-day, {tag_slug}]",
            "---",
            "",
            f"# Day {day_num}: {raw_title}",
            "",
            f"> **Goal:** {day_data.get('day_goal', '')}",
            "",
            "| | |",
            "|---|---|",
            f'| Date | {day_date.strftime("%A, %B %d %Y")} |',
            f'| Time | {day_data.get("total_hours", 2)}h |',
            f'| Type | {day_data.get("type", "study").capitalize()} |',
            "",
        ]
        if day_data.get("notes"):
            lines += [f'> {day_data["notes"]}', ""]

        lines += [
            "---",
            "",
            "## Topics for Today",
            topics_md,
            "---",
            "",
            "## My Notes",
            "*(Add your notes here)*",
            "",
            "---",
            "",
            f"<- {prev_link} | [[_Index]] | {next_link} ->",
        ]

        path = base / "Days" / f"{day_filename}.md"
        if _safe_write(path, "\n".join(lines)):
            day_titles.append((day_num, day_filename, raw_title, day_data.get("type", "study")))
            written.append(f"{subject}/Days/{day_filename}.md")
        else:
            failed.append(f"Days/{day_filename}.md")

    # ── Index ─────────────────────────────────────────────────────────────── #
    days_table = "\n".join(
        f"| [[Days/Day {n:02d} - {sanitize_filename(t)}|Day {n}]] | {t} | {dt.capitalize()} |"
        for n, _, t, dt in day_titles
    )
    notes_links = "\n".join(
        f"- [[Notes/{fname}|{fname}]]"
        for fname in topic_file_map.values()
    )

    index_lines = [
        "---",
        f'title: "{study_plan.get("subject", "Study Plan")}"',
        "type: index",
        f'created: {datetime.today().strftime("%Y-%m-%d")}',
        f'total_days: {user_profile.get("total_days", "?")}',
        "tags: [index]",
        "---",
        "",
        f'# {study_plan.get("subject", "Study Plan")}',
        "",
        f'> {study_plan.get("description", "")}',
        "",
        "| | |",
        "|---|---|",
        f'| Total Days | {user_profile.get("total_days")} |',
        f'| Hours/Day  | {user_profile.get("hours_per_day")}h |',
        f'| Total Hours| {user_profile.get("total_hours")}h |',
        f'| Skill Level| {str(user_profile.get("skill_level","")).capitalize()} |',
        f'| Goal       | {str(user_profile.get("goal","")).replace("_"," ").title()} |',
        f'| Source     | {pdf_metadata.get("title", "PDF")} |',
        "",
        "---",
        "",
        "## Study Schedule",
        "",
        "| Day | Title | Type |",
        "|-----|-------|------|",
        days_table,
        "",
        "---",
        "",
        "## All Notes",
        "",
        notes_links,
        "",
        "---",
        "",
        "## Progress",
        "",
        "![[Meta/Progress Tracker]]",
        "",
        "---",
        f'*Generated by StudyVault on {datetime.today().strftime("%Y-%m-%d")}*',
    ]

    if _safe_write(base / "_Index.md", "\n".join(index_lines)):
        written.append(f"{subject}/_Index.md")
    else:
        failed.append("_Index.md")

    # ── Progress tracker ──────────────────────────────────────────────────── #
    progress_rows = "\n".join(
        f"| [[Days/Day {n:02d} - {sanitize_filename(t)}|Day {n}]] | {t} | Not Started | |"
        for n, _, t, _ in day_titles
    )
    total_days = user_profile.get("total_days", 14)
    tracker_lines = [
        "---",
        'title: "Progress Tracker"',
        "type: tracker",
        "---",
        "",
        "# Progress Tracker",
        "",
        "| Day | Title | Status | Notes |",
        "|-----|-------|--------|-------|",
        progress_rows,
        "",
        "## Milestones",
        "- [ ] Completed Day 1",
        f"- [ ] Reached halfway (Day {total_days // 2})",
        f"- [ ] Finished all {total_days} days!",
    ]
    if _safe_write(base / "Meta" / "Progress Tracker.md", "\n".join(tracker_lines)):
        written.append(f"{subject}/Meta/Progress Tracker.md")

    # ── Profile ───────────────────────────────────────────────────────────── #
    profile_lines = [
        "---",
        'title: "Study Profile"',
        "type: meta",
        "---",
        "",
        "# Study Profile",
        "",
        "| Setting | Value |",
        "|---------|-------|",
        f'| Total Days | {user_profile.get("total_days")} |',
        f'| Hours/Day | {user_profile.get("hours_per_day")}h |',
        f'| Skill Level | {user_profile.get("skill_level")} |',
        f'| Goal | {user_profile.get("goal")} |',
        f'| Learning Style | {user_profile.get("learning_style")} |',
        f'| Hard Topics | {", ".join(user_profile.get("hard_topics", [])) or "None"} |',
        f'| Easy Topics | {", ".join(user_profile.get("easy_topics", [])) or "None"} |',
        f'| Quizzes | {"Yes" if user_profile.get("include_quizzes") else "No"} |',
        f'| TL;DRs  | {"Yes" if user_profile.get("include_summaries") else "No"} |',
    ]
    if _safe_write(base / "Meta" / "Profile.md", "\n".join(profile_lines)):
        written.append(f"{subject}/Meta/Profile.md")

    # ── Summary ───────────────────────────────────────────────────────────── #
    if failed:
        console.print(f"\n  [yellow]Warning: {len(failed)} file(s) could not be written:[/yellow]")
        for f in failed[:10]:
            console.print(f"    [dim]- {f}[/dim]")

    return written