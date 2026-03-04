"""Portfolio tracker: cash, positions, equity curve."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from clawquant.core.backtest.events import FillEvent
from clawquant.core.backtest.result import Trade
from clawquant.core.runtime.models import PortfolioState


class Portfolio:
    """Tracks cash, positions, equity, and trade history."""

    def __init__(self, initial_capital: float, symbol: str):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.symbol = symbol
        self.position_qty: float = 0.0  # asset quantity held
        self.avg_entry_price: float = 0.0
        self.realized_pnl: float = 0.0
        self.total_fees: float = 0.0

        # Tracking
        self.equity_curve: List[Dict[str, Any]] = []
        self.trades: List[Trade] = []
        self._open_trade: Optional[Dict[str, Any]] = None
        self._peak_equity: float = initial_capital
        self.max_drawdown: float = 0.0
        self.max_drawdown_pct: float = 0.0
        self.orders_today: int = 0
        self._current_day: Optional[str] = None

    def get_state(self, current_price: float, timestamp: Optional[datetime] = None) -> PortfolioState:
        """Return current portfolio snapshot."""
        position_value = self.position_qty * current_price
        unrealized_pnl = (current_price - self.avg_entry_price) * self.position_qty if self.position_qty > 0 else 0.0
        total_value = self.cash + position_value

        return PortfolioState(
            cash=self.cash,
            equity=total_value,
            positions={self.symbol: self.position_qty} if self.position_qty > 0 else {},
            position_values={self.symbol: position_value} if self.position_qty > 0 else {},
            unrealized_pnl=unrealized_pnl,
            realized_pnl=self.realized_pnl,
            total_value=total_value,
            timestamp=timestamp,
        )

    def process_fill(self, fill: FillEvent) -> None:
        """Update portfolio state after a fill event."""
        day_str = fill.timestamp.strftime("%Y-%m-%d")
        if day_str != self._current_day:
            self._current_day = day_str
            self.orders_today = 0
        self.orders_today += 1

        self.total_fees += fill.fee_usdt

        if fill.side == "BUY":
            self._process_buy(fill)
        else:
            self._process_sell(fill)

    def _process_buy(self, fill: FillEvent) -> None:
        """Process a buy fill."""
        cost = fill.amount_usdt + fill.fee_usdt + fill.slippage_usdt
        self.cash -= cost

        if self.position_qty == 0:
            self.avg_entry_price = fill.fill_price
            self._open_trade = {
                "entry_time": fill.timestamp,
                "entry_price": fill.fill_price,
                "entry_bar": fill.bar_index,
                "total_fee": fill.fee_usdt,
                "total_qty": fill.quantity,
            }
        else:
            # Update average entry price
            total_cost = self.avg_entry_price * self.position_qty + fill.fill_price * fill.quantity
            self.avg_entry_price = total_cost / (self.position_qty + fill.quantity)
            if self._open_trade:
                self._open_trade["total_fee"] += fill.fee_usdt
                self._open_trade["total_qty"] += fill.quantity

        self.position_qty += fill.quantity

    def _process_sell(self, fill: FillEvent) -> None:
        """Process a sell fill."""
        proceeds = fill.amount_usdt - fill.fee_usdt - fill.slippage_usdt
        self.cash += proceeds

        # Calculate PnL for the sold portion
        sell_qty = min(fill.quantity, self.position_qty)
        trade_pnl = (fill.fill_price - self.avg_entry_price) * sell_qty - fill.fee_usdt - fill.slippage_usdt
        self.realized_pnl += trade_pnl

        self.position_qty -= sell_qty
        if self.position_qty < 1e-10:
            self.position_qty = 0.0
            # Close the trade
            if self._open_trade:
                entry_fee = self._open_trade["total_fee"]
                total_qty = self._open_trade["total_qty"]
                pnl_pct = (fill.fill_price / self._open_trade["entry_price"] - 1) * 100 if self._open_trade["entry_price"] > 0 else 0
                trade = Trade(
                    entry_time=self._open_trade["entry_time"],
                    exit_time=fill.timestamp,
                    symbol=fill.symbol,
                    side="LONG",
                    entry_price=self._open_trade["entry_price"],
                    exit_price=fill.fill_price,
                    quantity=total_qty,
                    pnl=trade_pnl,
                    pnl_pct=pnl_pct,
                    fee_total=entry_fee + fill.fee_usdt,
                    bars_held=fill.bar_index - self._open_trade["entry_bar"],
                )
                self.trades.append(trade)
                self._open_trade = None

    def record_equity(self, timestamp: datetime, current_price: float, bar_index: int) -> None:
        """Record equity point and update drawdown tracking."""
        position_value = self.position_qty * current_price
        total_value = self.cash + position_value

        self.equity_curve.append({
            "bar_index": bar_index,
            "timestamp": timestamp.isoformat(),
            "cash": round(self.cash, 2),
            "position_value": round(position_value, 2),
            "total_value": round(total_value, 2),
            "price": current_price,
        })

        # Update drawdown
        if total_value > self._peak_equity:
            self._peak_equity = total_value
        drawdown = self._peak_equity - total_value
        drawdown_pct = drawdown / self._peak_equity if self._peak_equity > 0 else 0
        if drawdown > self.max_drawdown:
            self.max_drawdown = drawdown
            self.max_drawdown_pct = drawdown_pct

    def close_open_position(self, current_price: float, timestamp: datetime, bar_index: int) -> None:
        """Force-close any open position at current price (for end of backtest)."""
        if self.position_qty > 0 and self._open_trade:
            pnl = (current_price - self.avg_entry_price) * self.position_qty
            pnl_pct = (current_price / self._open_trade["entry_price"] - 1) * 100 if self._open_trade["entry_price"] > 0 else 0
            trade = Trade(
                entry_time=self._open_trade["entry_time"],
                exit_time=timestamp,
                symbol=self.symbol,
                side="LONG",
                entry_price=self._open_trade["entry_price"],
                exit_price=current_price,
                quantity=self._open_trade["total_qty"],
                pnl=pnl,
                pnl_pct=pnl_pct,
                fee_total=self._open_trade["total_fee"],
                bars_held=bar_index - self._open_trade["entry_bar"],
            )
            self.trades.append(trade)
            self.realized_pnl += pnl
            self.cash += self.position_qty * current_price
            self.position_qty = 0.0
            self._open_trade = None
