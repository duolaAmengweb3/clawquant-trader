"""Runtime Pydantic models for strategy and portfolio state."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class StrategyMetadata(BaseModel):
    """Metadata describing a strategy."""

    name: str
    version: str  # semver
    description: str
    params_schema: dict  # JSON Schema format
    tags: List[str] = Field(default_factory=list)


class PortfolioState(BaseModel):
    """Snapshot of the portfolio at a point in time."""

    cash: float
    equity: float
    positions: Dict[str, float] = Field(default_factory=dict)  # symbol -> quantity
    position_values: Dict[str, float] = Field(default_factory=dict)  # symbol -> USDT value
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    total_value: float = 0.0  # cash + position_values sum
    timestamp: Optional[datetime] = None


class MarketState(BaseModel):
    """Current market state for a single symbol at a given bar."""

    symbol: str
    current_price: float
    bar_index: int
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
