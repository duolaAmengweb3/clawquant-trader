"""Unified output helpers supporting Rich tables and JSON output."""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, List, Sequence

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

_console = Console()
_err_console = Console(stderr=True)


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def print_result(data: Any, json_mode: bool = False) -> None:
    """Print *data* as either a Rich-rendered structure or raw JSON.

    Parameters
    ----------
    data:
        Any JSON-serialisable Python object (dict, list, Pydantic model, ...).
    json_mode:
        If ``True``, emit compact JSON to stdout (useful for piping).
    """
    # Normalise Pydantic models to dicts
    if hasattr(data, "model_dump"):
        data = data.model_dump(mode="json")

    if json_mode:
        sys.stdout.write(json.dumps(data, default=str, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    else:
        _console.print_json(json.dumps(data, default=str, ensure_ascii=False))


def print_error(
    error_type: str,
    message: str,
    suggestion: str = "",
) -> None:
    """Print a structured error message.

    Parameters
    ----------
    error_type:
        Short error category, e.g. ``"DataNotFound"``.
    message:
        Human-readable description of what went wrong.
    suggestion:
        Optional suggestion on how to fix the issue.
    """
    body = Text()
    body.append(f"{error_type}: ", style="bold red")
    body.append(message)
    if suggestion:
        body.append(f"\n\nSuggestion: ", style="bold yellow")
        body.append(suggestion)

    _err_console.print(Panel(body, title="Error", border_style="red", expand=False))


def print_table(
    headers: Sequence[str],
    rows: Sequence[Sequence[Any]],
    title: str = "",
    json_mode: bool = False,
) -> None:
    """Print tabular data as a Rich table or JSON array of objects.

    Parameters
    ----------
    headers:
        Column names.
    rows:
        List of row tuples/lists, each matching *headers* length.
    title:
        Optional table title.
    json_mode:
        If ``True``, emit a JSON array of dicts to stdout.
    """
    if json_mode:
        records = [dict(zip(headers, row)) for row in rows]
        sys.stdout.write(json.dumps(records, default=str, ensure_ascii=False) + "\n")
        sys.stdout.flush()
        return

    table = Table(title=title or None, show_lines=False)
    for h in headers:
        table.add_column(h, style="cyan")

    for row in rows:
        table.add_row(*(str(v) for v in row))

    if not rows:
        _console.print(f"[dim]{title or 'Table'}: (no data)[/dim]")
    else:
        _console.print(table)
