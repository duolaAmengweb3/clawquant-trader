"""Data quality inspection for OHLCV DataFrames."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import List

import pandas as pd

from clawquant.core.data.models import DataQualityReport

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Interval helpers (mirrors fetcher but kept local to avoid circular imports)
# ---------------------------------------------------------------------------

_INTERVAL_SECONDS = {
    "1m": 60,
    "5m": 5 * 60,
    "15m": 15 * 60,
    "1h": 60 * 60,
    "4h": 4 * 60 * 60,
    "1d": 24 * 60 * 60,
}


def _interval_td(interval: str) -> timedelta:
    if interval in _INTERVAL_SECONDS:
        return timedelta(seconds=_INTERVAL_SECONDS[interval])
    raise ValueError(f"Unsupported interval: {interval!r}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def inspect_data(
    df: pd.DataFrame,
    symbol: str,
    interval: str,
) -> DataQualityReport:
    """Run quality checks on an OHLCV DataFrame.

    Checks performed:
    - Expected bar count vs actual.
    - Missing-timestamp (gap) detection.
    - Duplicate timestamps.
    - Price outliers (close price > 3 std devs from 20-bar rolling mean).

    Returns a :class:`DataQualityReport`.
    """
    issues: List[str] = []
    iv_td = _interval_td(interval)

    # Ensure sorted
    df = df.sort_values("timestamp").reset_index(drop=True)
    total_bars = len(df)

    # --- Expected bars ---
    if total_bars >= 2:
        ts_min = df["timestamp"].iloc[0]
        ts_max = df["timestamp"].iloc[-1]
        span = ts_max - ts_min
        expected_bars = int(span / iv_td) + 1
    else:
        expected_bars = total_bars

    # --- Gaps ---
    if total_bars >= 2:
        diffs = df["timestamp"].diff().dropna()
        gap_mask = diffs > iv_td
        gap_count = int(gap_mask.sum())
        # Each gap may represent multiple missing bars
        missing_bars = 0
        for d in diffs[gap_mask]:
            missing_bars += int(d / iv_td) - 1
    else:
        gap_count = 0
        missing_bars = 0

    if gap_count > 0:
        issues.append(f"Found {gap_count} gap(s) totalling {missing_bars} missing bar(s)")

    gap_pct = (missing_bars / expected_bars * 100) if expected_bars > 0 else 0.0

    # --- Duplicates ---
    duplicate_count = int(df.duplicated(subset=["timestamp"], keep="first").sum())
    if duplicate_count > 0:
        issues.append(f"Found {duplicate_count} duplicate timestamp(s)")

    # --- Outliers (close price) ---
    outlier_count = 0
    if total_bars >= 20 and "close" in df.columns:
        rolling_mean = df["close"].rolling(window=20, min_periods=20).mean()
        rolling_std = df["close"].rolling(window=20, min_periods=20).std()
        valid = rolling_std.notna()
        if valid.any():
            z_score = ((df["close"] - rolling_mean) / rolling_std).abs()
            outlier_count = int((z_score > 3).sum())
            if outlier_count > 0:
                issues.append(f"Found {outlier_count} price outlier(s) (>3 std devs)")

    # --- Verdict ---
    passed = gap_pct < 10.0 and not any("critical" in i.lower() for i in issues)

    return DataQualityReport(
        symbol=symbol,
        interval=interval,
        total_bars=total_bars,
        expected_bars=expected_bars,
        missing_bars=missing_bars,
        gap_pct=round(gap_pct, 2),
        duplicate_count=duplicate_count,
        outlier_count=outlier_count,
        issues=issues,
        passed=passed,
    )
