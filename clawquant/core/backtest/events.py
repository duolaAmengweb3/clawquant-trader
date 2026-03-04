"""Event types used by the backtest engine."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel


class BarEvent(BaseModel):
    """Emitted for every OHLCV bar during a backtest."""

    bar_index: int
    timestamp: datetime
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class SignalEvent(BaseModel):
    """Emitted by a strategy in response to a BarEvent."""

    bar_index: int
    timestamp: datetime
    symbol: str
    signal: Literal[1, 0, -1]  # 1=BUY, 0=HOLD, -1=SELL
    strategy_name: str


class OrderEvent(BaseModel):
    """Emitted when a signal is translated into an order."""

    bar_index: int
    timestamp: datetime
    symbol: str
    side: Literal["BUY", "SELL"]
    amount_usdt: float  # USDT amount to trade
    order_type: str = "MARKET"
    strategy_name: str


class FillEvent(BaseModel):
    """Emitted after an order is filled (simulated or live)."""

    bar_index: int
    timestamp: datetime
    symbol: str
    side: Literal["BUY", "SELL"]
    fill_price: float
    quantity: float  # asset quantity filled
    amount_usdt: float
    fee_usdt: float
    slippage_usdt: float
    strategy_name: str
