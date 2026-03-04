"""Simulated broker for order execution with fees and slippage."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from clawquant.core.backtest.config import BacktestConfig
from clawquant.core.backtest.events import FillEvent, OrderEvent


class SimulatedBroker:
    """Simulates order execution with configurable fees and slippage."""

    def __init__(self, config: BacktestConfig):
        self.fee_rate = config.fee_bps / 10000.0  # bps to decimal
        self.slippage_rate = config.slippage_bps / 10000.0
        self.fill_model = config.fill_model

    def fill_order(
        self,
        order: OrderEvent,
        fill_price: float,
        fill_timestamp: datetime,
        fill_bar_index: int,
    ) -> Optional[FillEvent]:
        """Execute an order at the given price with fees and slippage.

        Args:
            order: The order to fill.
            fill_price: The price at which to fill (next bar open or current close).
            fill_timestamp: Timestamp of the fill bar.
            fill_bar_index: Index of the fill bar.

        Returns:
            FillEvent if the order can be filled, None otherwise.
        """
        if order.amount_usdt <= 0:
            return None

        # Apply slippage
        if order.side == "BUY":
            slippage_price = fill_price * (1 + self.slippage_rate)
        else:
            slippage_price = fill_price * (1 - self.slippage_rate)

        # Calculate quantity
        quantity = order.amount_usdt / slippage_price

        # Calculate fee
        fee_usdt = order.amount_usdt * self.fee_rate

        # Calculate slippage cost in USDT
        slippage_usdt = abs(slippage_price - fill_price) * quantity

        return FillEvent(
            bar_index=fill_bar_index,
            timestamp=fill_timestamp,
            symbol=order.symbol,
            side=order.side,
            fill_price=slippage_price,
            quantity=quantity,
            amount_usdt=order.amount_usdt,
            fee_usdt=fee_usdt,
            slippage_usdt=slippage_usdt,
            strategy_name=order.strategy_name,
        )
