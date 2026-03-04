"""CLI commands for the ``data`` sub-app.

These functions are wired into the main Typer application in
:pymod:`clawquant.clawquant_cli`.
"""

from __future__ import annotations

import typer

from clawquant.core.utils.output import print_error, print_result, print_table


def pull(
    symbols: str,
    interval: str,
    days: int,
    exchange: str,
    json_mode: bool,
) -> None:
    """Pull OHLCV data for one or more symbols."""
    from clawquant.core.data.fetcher import fetch_data
    from clawquant.core.data.models import DataPullRequest

    symbol_list = [s.strip() for s in symbols.split(",")]
    typer.echo(
        f"[data pull] Fetching {symbol_list} | interval={interval} "
        f"| days={days} | exchange={exchange}"
    )

    request = DataPullRequest(
        symbols=symbol_list,
        interval=interval,
        days=days,
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
        start = str(df["timestamp"].min()) if bar_count else "-"
        end = str(df["timestamp"].max()) if bar_count else "-"
        rows.append((sym, interval, bar_count, start, end))

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
