"""Pydantic models for the data layer."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class OHLCVBar(BaseModel):
    """A single OHLCV bar."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class DataPullRequest(BaseModel):
    """Request parameters for pulling market data."""

    symbols: List[str]  # e.g. ["BTC/USDT", "ETH/USDT"]
    interval: str = "1h"  # e.g. "1h", "4h", "1d"
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    days: int = 10
    exchange: str = "binance"


class DataSummary(BaseModel):
    """Summary metadata for a cached dataset."""

    symbol: str
    interval: str
    bar_count: int
    start: datetime
    end: datetime
    gaps: int = 0
    gap_pct: float = 0.0
    source: str = "binance"
    cache_path: Optional[str] = None


class DataQualityReport(BaseModel):
    """Quality report produced by data validation checks."""

    symbol: str
    interval: str
    total_bars: int
    expected_bars: int
    missing_bars: int
    gap_pct: float
    duplicate_count: int
    outlier_count: int
    issues: List[str] = Field(default_factory=list)
    passed: bool = True
