"""Parquet-based cache for OHLCV data."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

logger = logging.getLogger(__name__)

CACHE_DIR: Path = Path(os.getenv("CLAWQUANT_CACHE_DIR", "data_cache"))


def _ensure_cache_dir() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def cache_key(symbol: str, interval: str) -> str:
    """Return a filesystem-safe filename (without extension) for *symbol*/*interval*."""
    safe = re.sub(r"[^A-Za-z0-9_\-]", "_", f"{symbol}__{interval}")
    return safe


def _parquet_path(symbol: str, interval: str) -> Path:
    return CACHE_DIR / f"{cache_key(symbol, interval)}.parquet"


# ---------------------------------------------------------------------------
# Read / Write
# ---------------------------------------------------------------------------

def read_cache(symbol: str, interval: str) -> Optional[pd.DataFrame]:
    """Read cached parquet for *symbol*/*interval*.  Returns ``None`` if absent."""
    path = _parquet_path(symbol, interval)
    if not path.exists():
        return None
    try:
        table = pq.read_table(path)
        df = table.to_pandas()
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        logger.debug("Cache hit: %s (%d rows)", path, len(df))
        return df
    except Exception:
        logger.warning("Corrupted cache file %s — removing and will re-fetch", path)
        path.unlink(missing_ok=True)
        return None


def write_cache(symbol: str, interval: str, df: pd.DataFrame) -> None:
    """Write *df* to the parquet cache, deduplicating by timestamp."""
    _ensure_cache_dir()
    df = df.copy()
    # Ensure timestamp is timezone-aware (UTC)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = _dedup(df)
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, _parquet_path(symbol, interval))
    logger.debug("Wrote %d rows to cache for %s/%s", len(df), symbol, interval)


def append_cache(symbol: str, interval: str, new_df: pd.DataFrame) -> None:
    """Append *new_df* to existing cache, deduplicating by timestamp."""
    existing = read_cache(symbol, interval)
    if existing is not None:
        combined = pd.concat([existing, new_df], ignore_index=True)
    else:
        combined = new_df
    write_cache(symbol, interval, combined)


# ---------------------------------------------------------------------------
# Status / helpers
# ---------------------------------------------------------------------------

def cache_status() -> List[Dict]:
    """Return a list of dicts describing every cached parquet file."""
    _ensure_cache_dir()
    entries: List[Dict] = []
    for path in sorted(CACHE_DIR.glob("*.parquet")):
        try:
            table = pq.read_table(path)
            df = table.to_pandas()
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
                ts_min = df["timestamp"].min()
                ts_max = df["timestamp"].max()
            else:
                ts_min = ts_max = None
            entries.append(
                {
                    "file": path.name,
                    "rows": len(df),
                    "start": str(ts_min) if ts_min is not None else "",
                    "end": str(ts_max) if ts_max is not None else "",
                    "size_kb": round(path.stat().st_size / 1024, 1),
                }
            )
        except Exception:
            logger.warning("Corrupted cache file %s — removing", path)
            path.unlink(missing_ok=True)
    return entries


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _dedup(df: pd.DataFrame) -> pd.DataFrame:
    """Drop duplicate timestamps, keeping the last occurrence, and sort."""
    if "timestamp" not in df.columns:
        return df
    df = df.drop_duplicates(subset=["timestamp"], keep="last")
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df
