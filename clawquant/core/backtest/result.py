"""Backtest result and trade models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Trade(BaseModel):
    """A single round-trip trade record."""

    entry_time: datetime
    exit_time: Optional[datetime] = None
    symbol: str
    side: str  # "LONG" or "SHORT"
    entry_price: float
    exit_price: Optional[float] = None
    quantity: float
    pnl: float = 0.0
    pnl_pct: float = 0.0
    fee_total: float = 0.0
    bars_held: int = 0


class RunMeta(BaseModel):
    """Metadata attached to every backtest run for reproducibility."""

    run_id: str
    timestamp: str
    engine_version: str = "0.1.0"
    strategy: dict
    data: dict
    config: dict
    environment: dict


class BacktestResult(BaseModel):
    """Complete result of a backtest run."""

    run_id: str
    success: bool = True
    error_type: Optional[str] = None
    message: Optional[str] = None

    # Performance metrics
    total_return: float = 0.0
    total_return_pct: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    total_trades: int = 0
    avg_trade_pnl: float = 0.0
    avg_bars_held: float = 0.0

    # Score
    stability_score: float = 0.0
    score_breakdown: Dict[str, float] = Field(default_factory=dict)

    # References
    trades: List[Trade] = Field(default_factory=list)
    equity_curve: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    run_meta: Optional[RunMeta] = None
