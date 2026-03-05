"""CLI commands for the ``data`` sub-app.

These functions are wired into the main Typer application in
:pymod:`clawquant.clawquant_cli`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import typer

from clawquant.core.utils.output import print_error, print_result, print_table


def _parse_date(s: str) -> datetime:
    """Parse a date string to a timezone-aware datetime."""
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise typer.BadParameter(
        f"Invalid date format: {s!r}. Use YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS"
    )


def pull(
    symbols: str,
    interval: str,
    days: int,
    start: Optional[str],
    end: Optional[str],
    exchange: str,
    json_mode: bool,
) -> None:
    """Pull OHLCV data for one or more symbols."""
    from clawquant.core.data.fetcher import fetch_data
    from clawquant.core.data.models import DataPullRequest

    symbol_list = [s.strip() for s in symbols.split(",")]

    start_dt = _parse_date(start) if start else None
    end_dt = _parse_date(end) if end else None

    # Build description for user feedback
    if start_dt:
        time_desc = f"from {start_dt.strftime('%Y-%m-%d')}"
        if end_dt:
            time_desc += f" to {end_dt.strftime('%Y-%m-%d')}"
        else:
            time_desc += " to now"
    else:
        time_desc = f"last {days} days"

    typer.echo(
        f"[data pull] Fetching {symbol_list} | interval={interval} "
        f"| {time_desc} | exchange={exchange}"
    )

    request = DataPullRequest(
        symbols=symbol_list,
        interval=interval,
        days=days,
        start=start_dt,
        end=end_dt,
        exchange=exchange,
    )

    try:
        result = fetch_data(request)
    except Exception as exc:
        print_error("FetchError", str(exc), suggestion="Check your network or API keys.")
        raise typer.Exit(code=1)

    rows = []
    for sym, df in result.items():
        bar_count = len(df)
        start_str = str(df["timestamp"].min()) if bar_count else "-"
        end_str = str(df["timestamp"].max()) if bar_count else "-"
        rows.append((sym, interval, bar_count, start_str, end_str))

    print_table(
        headers=["Symbol", "Interval", "Bars", "Start", "End"],
        rows=rows,
        title="Data Pull Results",
        json_mode=json_mode,
    )


def inspect(
    symbol: str,
    interval: str,
    json_mode: bool,
) -> None:
    """Run data quality checks on cached data for a single symbol."""
    from clawquant.core.data.cache import read_cache
    from clawquant.core.data.inspector import inspect_data

    typer.echo(f"[data inspect] Checking {symbol} @ {interval} ...")

    df = read_cache(symbol, interval)
    if df is None or df.empty:
        print_error(
            "DataNotFound",
            f"No cached data for {symbol}/{interval}.",
            suggestion="Run 'clawquant data pull' first.",
        )
        raise typer.Exit(code=1)

    report = inspect_data(df, symbol, interval)
    print_result(report, json_mode=json_mode)


def cache_status(json_mode: bool) -> None:
    """Show information about all cached data files."""
    from clawquant.core.data.cache import cache_status as _cache_status

    entries = _cache_status()
    if not entries:
        typer.echo("[data cache-status] Cache is empty.")
        return

    rows = [
        (e["file"], e["rows"], e["start"], e["end"], e["size_kb"])
        for e in entries
    ]
    print_table(
        headers=["File", "Rows", "Start", "End", "Size (KB)"],
        rows=rows,
        title="Cached Datasets",
        json_mode=json_mode,
    )
