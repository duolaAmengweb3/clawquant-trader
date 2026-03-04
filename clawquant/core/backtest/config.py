"""Backtest configuration models."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class RiskLimits(BaseModel):
    """Risk management limits applied during backtesting."""

    max_position_pct: float = 0.5
    max_orders_per_day: int = 10
    max_drawdown_stop: float = 0.15
    cooldown_bars: int = 3


class BacktestConfig(BaseModel):
    """Full configuration for a backtest run."""

    initial_capital: float = 10000.0
    fee_bps: int = 10  # basis points
    slippage_bps: int = 5
    fill_model: Literal["next_open", "current_close"] = "next_open"
    position_model: Literal["fixed_pct", "fixed_amount", "kelly"] = "fixed_pct"
    position_pct: float = 0.1  # fraction of equity per trade
    risk_limits: RiskLimits = Field(default_factory=RiskLimits)
    strategy_name: str = ""
    strategy_params: dict = Field(default_factory=dict)
    symbol: str = ""
    interval: str = "1h"
    start: Optional[str] = None
    end: Optional[str] = None
    days: int = 30
    exchange: str = "binance"
