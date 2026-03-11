"""
Terminal display utilities using the Rich library.
Falls back to plain print if Rich isn't installed.
"""

import sys
from pathlib import Path
from typing import List

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    # On Windows, use legacy mode to avoid encoding issues with Unicode box characters
    console = Console(legacy_windows=True) if sys.platform == "win32" else Console()
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

    class _FallbackConsole:
        def print(self, *args, **kwargs):
            # Strip rich markup tags for plain output
            import re
            text = " ".join(str(a) for a in args)
            text = re.sub(r'\[.*?\]', '', text)
            print(text)

    console = _FallbackConsole()


def print_banner():
    try:
        if HAS_RICH:
            text = Text()
            text.append("  Pilot  ", style="bold white on dark_blue")
            text.append("  PDF to Obsidian Study Plan Generator", style="dim")
            console.print(Panel(text, border_style="blue", padding=(0, 2)))
        else:
            print("\n" + "=" * 60)
            print("  Pilot — PDF to Obsidian Study Plan Generator")
            print("=" * 60)
    except Exception:
        # Fallback for Windows encoding issues
        print("\n" + "=" * 60)
        print("  Pilot — PDF to Obsidian Study Plan Generator")
        print("=" * 60)


def print_success(vault_path: Path, written_files: List[str]):
    if HAS_RICH:
        console.print(f"\n[bold green]✅ Done! Vault created at:[/bold green] {vault_path}")
        console.print(f"[dim]  {len(written_files)} files written[/dim]")
        console.print("\n[bold]Next steps:[/bold]")
        console.print("  1. Open Obsidian → Open folder as vault → select your vault path")
        console.print("  2. Open [bold]📚 Index.md[/bold] to start")
        console.print("  3. Enable [bold]Graph view[/bold] to see topic connections")
        console.print("  4. Use the [bold]Progress Tracker[/bold] to track your journey\n")
    else:
        print(f"\n✅ Done! Vault created at: {vault_path}")
        print(f"  {len(written_files)} files written")
        print("\nNext steps:")
        print("  1. Open Obsidian → Open folder as vault")
        print("  2. Open 📚 Index.md to start")
        print("  3. Enable Graph view to see topic connections")


def print_error(msg: str):
    if HAS_RICH:
        console.print(f"[bold red]❌ Error:[/bold red] {msg}")
    else:
        print(f"❌ Error: {msg}")
