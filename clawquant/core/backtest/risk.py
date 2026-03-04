"""Risk manager: enforces position limits, drawdown stops, order frequency, cooldowns."""

from __future__ import annotations

import logging
from typing import List

from clawquant.core.backtest.config import RiskLimits
from clawquant.core.runtime.models import PortfolioState

logger = logging.getLogger(__name__)


class RiskManager:
    """Applies risk controls before order submission."""

    def __init__(self, risk_limits: RiskLimits, initial_capital: float):
        self.limits = risk_limits
        self.initial_capital = initial_capital
        self._last_trade_bar: int = -999
        self._stopped: bool = False

    def check(
        self,
        portfolio: PortfolioState,
        proposed_amount_usdt: float,
        current_bar: int,
        orders_today: int,
    ) -> List[dict]:
        """Run all risk checks. Returns list of risk actions.

        Each action: {"action": "REDUCE"|"FLATTEN"|"SKIP"|"NONE", "reason": str}
        Empty list = all clear.
        """
        actions: List[dict] = []

        if self._stopped:
            actions.append({"action": "SKIP", "reason": "Trading stopped due to max drawdown breach"})
            return actions

        # 1. Max drawdown stop
        drawdown_pct = 1 - (portfolio.total_value / self.initial_capital) if self.initial_capital > 0 else 0
        if drawdown_pct >= self.limits.max_drawdown_stop:
            self._stopped = True
            actions.append({
                "action": "FLATTEN",
                "reason": f"Max drawdown {drawdown_pct:.1%} >= limit {self.limits.max_drawdown_stop:.1%}",
            })
            return actions

        # 2. Max position size
        total_position_value = sum(portfolio.position_values.values())
        position_pct = total_position_value / portfolio.total_value if portfolio.total_value > 0 else 0
        if proposed_amount_usdt > 0:  # Only check for buys
            new_position_pct = (total_position_value + proposed_amount_usdt) / portfolio.total_value if portfolio.total_value > 0 else 0
            if new_position_pct > self.limits.max_position_pct:
                actions.append({
                    "action": "REDUCE",
                    "reason": f"Position would be {new_position_pct:.1%} > limit {self.limits.max_position_pct:.1%}",
                })

        # 3. Max orders per day
        if orders_today >= self.limits.max_orders_per_day:
            actions.append({
                "action": "SKIP",
                "reason": f"Daily order limit reached ({orders_today}/{self.limits.max_orders_per_day})",
            })

        # 4. Cooldown period
        bars_since_last = current_bar - self._last_trade_bar
        if bars_since_last < self.limits.cooldown_bars:
            actions.append({
                "action": "SKIP",
                "reason": f"Cooldown: {bars_since_last}/{self.limits.cooldown_bars} bars since last trade",
            })

        return actions

    def record_trade(self, bar_index: int) -> None:
        """Record that a trade occurred at this bar."""
        self._last_trade_bar = bar_index

    @property
    def is_stopped(self) -> bool:
        return self._stopped
