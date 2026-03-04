"""Main data-fetch logic: cache-aware OHLCV retrieval via CCXT."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict

import pandas as pd

from clawquant.core.data.cache import append_cache, read_cache
from clawquant.core.data.models import DataPullRequest
from clawquant.integrations.ccxt_fallback.client import CcxtClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Interval helpers
# ---------------------------------------------------------------------------

_INTERVAL_SECONDS: Dict[str, int] = {
    "1m": 60,
    "5m": 5 * 60,
    "15m": 15 * 60,
    "1h": 60 * 60,
    "4h": 4 * 60 * 60,
    "1d": 24 * 60 * 60,
}


def interval_to_seconds(interval: str) -> int:
    """Convert a human interval string to seconds."""
    if interval in _INTERVAL_SECONDS:
        return _INTERVAL_SECONDS[interval]
    raise ValueError(f"Unsupported interval: {interval!r}")


def interval_to_timedelta(interval: str) -> timedelta:
    return timedelta(seconds=interval_to_seconds(interval))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_data(request: DataPullRequest) -> Dict[str, pd.DataFrame]:
    """Fetch OHLCV data for every symbol in *request*.

    For each symbol the flow is:

    1. Check the local parquet cache.
    2. Determine which date range still needs fetching.
    3. Pull missing bars via CCXT.
    4. Append new bars to the cache.
    5. Return the trimmed DataFrame covering the requested window.

    Returns
    -------
    Dict[str, pd.DataFrame]
        Mapping of ``symbol -> DataFrame`` with columns
        ``[timestamp, open, high, low, close, volume]``.
    """
    now = datetime.now(timezone.utc)
    iv_td = interval_to_timedelta(request.interval)

    # Compute the request window.
    if request.start is not None:
        start_dt = request.start.replace(tzinfo=timezone.utc) if request.start.tzinfo is None else request.start
    else:
        start_dt = now - timedelta(days=request.days)

    if request.end is not None:
        end_dt = request.end.replace(tzinfo=timezone.utc) if request.end.tzinfo is None else request.end
    else:
        # Avoid pulling the currently-unclosed candle.
        end_dt = now - iv_td

    client = CcxtClient(exchange_id=request.exchange)
    results: Dict[str, pd.DataFrame] = {}

    for symbol in request.symbols:
        logger.info("Processing %s ...", symbol)

        # --- 1. Cache lookup ---
        cached_df = read_cache(symbol, request.interval)
        fetch_since = start_dt

        if cached_df is not None and not cached_df.empty:
            cached_max = cached_df["timestamp"].max()
            if cached_max.tzinfo is None:
                cached_max = cached_max.replace(tzinfo=timezone.utc)
            # Only fetch bars newer than what we already have.
            if cached_max >= start_dt:
                fetch_since = cached_max + iv_td

        # --- 2. Fetch missing bars ---
        if fetch_since < end_dt:
            try:
                since_ms = int(fetch_since.timestamp() * 1000)
                raw_bars = client.fetch_ohlcv(
                    symbol=symbol,
                    timeframe=request.interval,
                    since=since_ms,
                )
                if raw_bars:
                    new_df = _bars_to_dataframe(raw_bars)
                    # Filter out bars past the requested end.
                    new_df = new_df[new_df["timestamp"] <= end_dt]
                    if not new_df.empty:
                        append_cache(symbol, request.interval, new_df)
                        logger.info(
                            "Appended %d new bars for %s/%s",
                            len(new_df),
                            symbol,
                            request.interval,
                        )
            except Exception as e:
                # If fetch fails but we have cached data, log warning and continue
                if cached_df is not None and not cached_df.empty:
                    logger.warning("Fetch failed for %s, using cached data: %s", symbol, e)
                else:
                    raise
        else:
            logger.info("Cache is up-to-date for %s/%s", symbol, request.interval)

        # --- 3. Read the full cache and trim to window ---
        full_df = read_cache(symbol, request.interval)
        if full_df is not None and not full_df.empty:
            mask = (full_df["timestamp"] >= start_dt) & (full_df["timestamp"] <= end_dt)
            result_df = full_df.loc[mask].reset_index(drop=True)
        else:
            result_df = pd.DataFrame(
                columns=["timestamp", "open", "high", "low", "close", "volume"]
            )

        results[symbol] = result_df
        logger.info("Returning %d bars for %s", len(result_df), symbol)

    return results


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _bars_to_dataframe(bars: list) -> pd.DataFrame:
    """Convert raw CCXT OHLCV bars to a DataFrame."""
    df = pd.DataFrame(bars, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return df
