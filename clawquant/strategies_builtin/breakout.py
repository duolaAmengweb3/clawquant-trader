"""Breakout (Donchian Channel) strategy.

Buys when price breaks above the N-period high and sells when price breaks
below the N-period low.  Based on the Turtle Trading method.
"""

from __future__ import annotations

from typing import List

import pandas as pd

from clawquant.core.runtime.base_strategy import BaseStrategy
from clawquant.core.runtime.models import MarketState, PortfolioState, StrategyMetadata


class BreakoutStrategy(BaseStrategy):
    """Donchian channel breakout (Turtle Trading) strategy."""

    # ------------------------------------------------------------------
    # 1. Metadata
    # ------------------------------------------------------------------
    @classmethod
    def metadata(cls) -> StrategyMetadata:
        return StrategyMetadata(
            name="breakout",
            version="1.0.0",
            description="Breakout - buy on N-period high breakout, sell on N-period low breakdown (Turtle Trading).",
            params_schema={
                "type": "object",
                "properties": {
                    "lookback": {
                        "type": "integer",
                        "description": "Number of bars to look back for high/low channel.",
                        "default": 20,
                        "minimum": 2,
                    },
                    "position_pct": {
                        "type": "number",
                        "description": "Fraction of equity to allocate per trade.",
                        "default": 0.1,
                        "minimum": 0.01,
                        "maximum": 1.0,
                    },
                },
                "required": ["lookback"],
            },
            tags=["trend-following", "breakout"],
        )

    # ------------------------------------------------------------------
    # 2. Indicators
    # ------------------------------------------------------------------
    def compute_indicators(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        df = df.copy()
        lookback = params.get("lookback", 20)

        # Donchian channel: rolling high / low over lookback period
        # Use shift(1) so we compare current price against *previous* N bars
        df["breakout_upper"] = df["high"].rolling(window=lookback, min_periods=lookback).max().shift(1)
        df["breakout_lower"] = df["low"].rolling(window=lookback, min_periods=lookback).min().shift(1)

        return df

    # ------------------------------------------------------------------
    # 3. Signals
    # ------------------------------------------------------------------
    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.Series:
        if "breakout_upper" not in df.columns:
            df = self.compute_indicators(df, params)

        close = df["close"]
        upper = df["breakout_upper"]
        lower = df["breakout_lower"]

        signals = pd.Series(0, index=df.index, dtype=int)
        signals[close > upper] = 1   # Breakout above N-period high => BUY
        signals[close < lower] = -1  # Breakdown below N-period low => SELL

        # NaN rows should be HOLD
        nan_mask = upper.isna() | lower.isna()
        signals[nan_mask] = 0

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
        if signal == 0:
            return 0.0

        position_pct = params.get("position_pct", 0.1)
        equity = portfolio_state.equity

        if signal == 1:
            amount = equity * position_pct
            return min(amount, portfolio_state.cash)
        elif signal == -1:
            total_pos_value = sum(portfolio_state.position_values.values())
            return -min(total_pos_value * position_pct, total_pos_value)

        return 0.0

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

        total_pos_value = sum(portfolio_state.position_values.values())
        if portfolio_state.equity > 0 and total_pos_value / portfolio_state.equity > 0.9:
            actions.append({
                "action": "REDUCE",
                "reason": (
                    f"Position value ({total_pos_value:.2f}) exceeds 90% of "
                    f"equity ({portfolio_state.equity:.2f})"
                ),
            })
            return actions

        if portfolio_state.equity > 0:
            drawdown_pct = abs(min(0.0, portfolio_state.unrealized_pnl)) / portfolio_state.equity
            if drawdown_pct > 0.2:
                actions.append({
                    "action": "FLATTEN",
                    "reason": f"Unrealized drawdown ({drawdown_pct:.1%}) exceeds 20% of equity.",
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
        upper = last_state.get("upper_channel", 0.0)
        lower = last_state.get("lower_channel", 0.0)

        reasons: list[str] = []
        if signal == 1:
            reasons.append(
                f"Price ({price:.4f}) broke above {upper:.4f} (N-period high) => BUY"
            )
        elif signal == -1:
            reasons.append(
                f"Price ({price:.4f}) broke below {lower:.4f} (N-period low) => SELL"
            )
        else:
            reasons.append(f"Price ({price:.4f}) is within channel [{lower:.4f}, {upper:.4f}] => HOLD")

        return {
            "reasons": reasons,
            "key_metrics": {
                "current_price": float(price),
                "upper_channel": float(upper),
                "lower_channel": float(lower),
                "channel_width": float(upper - lower) if upper and lower else 0.0,
            },
        }
