"""DCA (Dollar Cost Averaging) strategy.

Buys a fixed USDT amount at regular bar intervals regardless of price.
This is one of the simplest possible strategies and is useful as a baseline.
"""

from __future__ import annotations

from typing import List

import pandas as pd

from clawquant.core.runtime.base_strategy import BaseStrategy
from clawquant.core.runtime.models import MarketState, PortfolioState, StrategyMetadata


class DCAStrategy(BaseStrategy):
    """Dollar Cost Averaging - buy a fixed amount every N bars."""

    # ------------------------------------------------------------------
    # 1. Metadata
    # ------------------------------------------------------------------
    @classmethod
    def metadata(cls) -> StrategyMetadata:
        return StrategyMetadata(
            name="dca",
            version="1.0.0",
            description="Dollar Cost Averaging - buys a fixed USDT amount at regular intervals.",
            params_schema={
                "type": "object",
                "properties": {
                    "buy_interval": {
                        "type": "integer",
                        "description": "Number of bars between each buy order.",
                        "default": 24,
                        "minimum": 1,
                    },
                    "buy_amount_usdt": {
                        "type": "number",
                        "description": "Amount in USDT to buy each time.",
                        "default": 100.0,
                        "minimum": 0.01,
                    },
                    "max_position_usdt": {
                        "type": "number",
                        "description": "Maximum total position value in USDT before stopping buys.",
                        "default": 50000.0,
                        "minimum": 0.0,
                    },
                },
                "required": ["buy_interval", "buy_amount_usdt"],
            },
            tags=["passive", "accumulation", "beginner"],
        )

    # ------------------------------------------------------------------
    # 2. Indicators
    # ------------------------------------------------------------------
    def compute_indicators(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        """DCA needs no technical indicators. Return df unchanged."""
        # Add a bar-counter column for transparency.
        df = df.copy()
        df["dca_bar_index"] = range(len(df))
        return df

    # ------------------------------------------------------------------
    # 3. Signals
    # ------------------------------------------------------------------
    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.Series:
        buy_interval = params.get("buy_interval", 24)

        signals = pd.Series(0, index=df.index, dtype=int)
        # Buy at bar 0, then every buy_interval bars
        for i in range(0, len(df), buy_interval):
            signals.iloc[i] = 1
        return signals

    # ------------------------------------------------------------------
    # 4. Position sizing
    # ------------------------------------------------------------------
    def position_sizing(
        self,
        signal: int,
        portfolio_state: PortfolioState,
        params: dict,
    ) -> float:
        if signal != 1:
            return 0.0
        buy_amount = params.get("buy_amount_usdt", 100.0)
        # Don't buy more than available cash
        return min(buy_amount, portfolio_state.cash)

    # ------------------------------------------------------------------
    # 5. Risk controls
    # ------------------------------------------------------------------
    def risk_controls(
        self,
        portfolio_state: PortfolioState,
        market_state: MarketState,
        params: dict,
    ) -> List[dict]:
        actions: List[dict] = []
        max_position = params.get("max_position_usdt", 50000.0)

        total_position_value = sum(portfolio_state.position_values.values())
        if total_position_value >= max_position:
            actions.append({
                "action": "SKIP",
                "reason": (
                    f"Total position value ({total_position_value:.2f} USDT) "
                    f"exceeds max_position_usdt ({max_position:.2f})"
                ),
            })
            return actions

        if portfolio_state.cash < params.get("buy_amount_usdt", 100.0):
            actions.append({
                "action": "SKIP",
                "reason": (
                    f"Insufficient cash ({portfolio_state.cash:.2f} USDT) "
                    f"for buy_amount_usdt ({params.get('buy_amount_usdt', 100.0):.2f})"
                ),
            })
            return actions

        actions.append({"action": "NONE", "reason": "All risk checks passed."})
        return actions

    # ------------------------------------------------------------------
    # 6. Explain
    # ------------------------------------------------------------------
    def explain(self, last_state: dict) -> dict:
        signal = last_state.get("signal", 0)
        price = last_state.get("price", 0.0)
        bar_index = last_state.get("bar_index", 0)

        reasons: list[str] = []
        if signal == 1:
            reasons.append(f"Scheduled DCA buy at bar {bar_index}, price={price:.2f}")
        else:
            reasons.append(f"No buy scheduled at bar {bar_index}")

        return {
            "reasons": reasons,
            "key_metrics": {
                "current_price": float(price),
                "bar_index": float(bar_index),
            },
        }
