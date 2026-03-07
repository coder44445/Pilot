"""
Node retry and error recording utilities.

Instead of nodes returning {"error": ..., "status": "failed"}
and stopping the graph, they use:

  @resilient_node("node_name", max_retries=3)
  def my_node(state): ...

Which:
  1. Retries the node up to max_retries times with backoff
  2. On final failure: records the error in node_errors, adds to failed_nodes
  3. Returns a partial state update — graph continues to next node
  4. Skips re-running if the node already succeeded (idempotency check)

Checkpointing:
  Uses SqliteSaver so state survives process restarts.
  The DB is written to {vault_path}/.pilot_checkpoint.db
  On retry run, already-completed nodes are skipped automatically.
"""

import time
import traceback
import functools
from typing import Callable

from src.display import console


MAX_RETRY_DELAYS = [5, 15, 30]   # seconds between retries


def resilient_node(node_name: str, max_retries: int = 3):
    """
    Decorator that adds retry + error recording to a node function.

    Usage:
        @resilient_node("build_schedule", max_retries=3)
        def node_build_schedule(state):
            ...
            return {"days": [...], "status": "scheduled"}

    On success: returns the node's result normally.
    On failure after all retries: logs error, returns partial state,
                                  graph continues to next node.
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(state: dict) -> dict:
            retries = state.get("retry_counts", {}).get(node_name, 0)
            errors  = state.get("node_errors",  {}).get(node_name, [])

            for attempt in range(max_retries):
                try:
                    result = fn(state)
                    # Success — clear any previous failures for this node
                    return {
                        **result,
                        "retry_counts": {node_name: 0},
                    }
                except Exception as e:
                    err_str = f"{type(e).__name__}: {e}"
                    tb      = traceback.format_exc()
                    errors  = errors + [err_str]

                    if attempt < max_retries - 1:
                        delay = MAX_RETRY_DELAYS[min(attempt, len(MAX_RETRY_DELAYS) - 1)]
                        console.print(
                            f"\n  [yellow]⚠ [{node_name}] attempt {attempt+1}/{max_retries} failed:[/yellow]"
                            f"\n  [dim]  {err_str}[/dim]"
                            f"\n  [dim]  retrying in {delay}s...[/dim]"
                        )
                        time.sleep(delay)
                    else:
                        # Final failure
                        console.print(
                            f"\n  [red]✗ [{node_name}] failed after {max_retries} attempts:[/red]"
                            f"\n  [dim]  {err_str}[/dim]"
                            f"\n  [dim]  Pipeline continues — this node will be skipped.[/dim]"
                        )
                        return {
                            "node_errors":  {node_name: errors},
                            "failed_nodes": [node_name],
                            "retry_counts": {node_name: retries + max_retries},
                            "status":       f"partial_{node_name}_failed",
                        }

        return wrapper
    return decorator


def node_already_done(state: dict, node_name: str, check_key: str) -> bool:
    """
    Idempotency check — skip a node if its output already exists in state.
    Prevents recomputing expensive steps (PDF read, chunk extraction) on resume.

    Args:
        state:      current pipeline state
        node_name:  name for logging
        check_key:  state key to check (e.g. "pdf_text", "topics", "days")

    Returns True if node should be skipped.
    """
    value = state.get(check_key)
    has_value = bool(value) if not isinstance(value, (int, float)) else value > 0

    if has_value:
        console.print(f"  [dim]↩ [{node_name}] already done — skipping[/dim]")
        return True
    return False


def summarise_errors(state: dict) -> None:
    """Print a summary of all node errors at the end of the pipeline."""
    node_errors  = state.get("node_errors", {})
    failed_nodes = state.get("failed_nodes", [])

    if not node_errors and not failed_nodes:
        return

    console.print("\n[bold yellow]⚠ Pipeline completed with errors:[/bold yellow]")
    seen = set()
    for node in failed_nodes:
        if node in seen:
            continue
        seen.add(node)
        errs = node_errors.get(node, ["unknown error"])
        console.print(f"  [red]• {node}[/red]: {errs[-1]}")

    console.print(
        "\n[dim]To retry failed nodes only, rerun with the same --vault path.[/dim]"
        "\n[dim]Already-completed nodes will be skipped automatically.[/dim]"
    )