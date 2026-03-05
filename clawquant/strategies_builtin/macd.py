"""MACD strategy.

Generates buy signals when the MACD line crosses above the signal line, and
sell signals when it crosses below.  A trend-following momentum strategy.
"""

from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd

from clawquant.core.runtime.base_strategy import BaseStrategy
from clawquant.core.runtime.models import MarketState, PortfolioState, StrategyMetadata


class MACDStrategy(BaseStrategy):
    """MACD crossover strategy."""

    # ------------------------------------------------------------------
    # 1. Metadata
    # ------------------------------------------------------------------
    @classmethod
    def metadata(cls) -> StrategyMetadata:
        return StrategyMetadata(
            name="macd",
            version="1.0.0",
            description="MACD - buy when MACD line crosses above signal line, sell on cross below.",
            params_schema={
                "type": "object",
                "properties": {
                    "fast_period": {
                        "type": "integer",
                        "description": "Period for the fast EMA.",
                        "default": 12,
                        "minimum": 2,
                    },
                    "slow_period": {
                        "type": "integer",
                        "description": "Period for the slow EMA.",
                        "default": 26,
                        "minimum": 2,
                    },
                    "signal_period": {
                        "type": "integer",
                        "description": "Period for the signal line EMA.",
                        "default": 9,
                        "minimum": 2,
                    },
                    "position_pct": {
                        "type": "number",
                        "description": "Fraction of equity to allocate per trade.",
                        "default": 0.95,
                        "minimum": 0.01,
                        "maximum": 1.0,
                    },
                },
                "required": ["fast_period", "slow_period", "signal_period"],
            },
            tags=["trend-following", "momentum"],
        )

    # ------------------------------------------------------------------
    # 2. Indicators
    # ------------------------------------------------------------------
    def compute_indicators(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        df = df.copy()
        fast_period = params.get("fast_period", 12)
        slow_period = params.get("slow_period", 26)
        signal_period = params.get("signal_period", 9)
        close = df["close"]

        fast_ema = close.ewm(span=fast_period, adjust=False).mean()
        slow_ema = close.ewm(span=slow_period, adjust=False).mean()

        df["macd_line"] = fast_ema - slow_ema
        df["macd_signal"] = df["macd_line"].ewm(span=signal_period, adjust=False).mean()
        df["macd_histogram"] = df["macd_line"] - df["macd_signal"]

        return df

    # ------------------------------------------------------------------
    # 3. Signals
    # ------------------------------------------------------------------
    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.Series:
        if "macd_line" not in df.columns:
            df = self.compute_indicators(df, params)

        macd_line = df["macd_line"]
        signal_line = df["macd_signal"]

        # Determine crossover: MACD above signal = bullish
        position = pd.Series(
            np.where(macd_line > signal_line, 1, np.where(macd_line < signal_line, -1, 0)),
            index=df.index,
            dtype=int,
        )

        # Signal only on the bar where position changes (the actual crossover)
        signals = position.diff().fillna(0).astype(int)
        signals = signals.clip(-1, 1)

        # Need enough data for slow EMA to warm up
        slow_period = params.get("slow_period", 26)
        signals.iloc[:slow_period] = 0

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

        position_pct = params.get("position_pct", 0.95)
        total_pos_value = sum(portfolio_state.position_values.values())

        if signal == 1:
            if total_pos_value > 0:
                return 0.0  # Already holding, skip
            amount = portfolio_state.equity * position_pct
            return min(amount, portfolio_state.cash)
        elif signal == -1:
            if total_pos_value == 0:
                return 0.0  # Nothing to sell
            return -total_pos_value

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
        macd = last_state.get("macd_line", 0.0)
        signal_val = last_state.get("signal_line", 0.0)
        histogram = last_state.get("histogram", 0.0)
        price = last_state.get("price", 0.0)

        reasons: list[str] = []
        if signal == 1:
            reasons.append(
                f"MACD ({macd:.4f}) crossed above signal ({signal_val:.4f}) => BUY"
            )
        elif signal == -1:
            reasons.append(
                f"MACD ({macd:.4f}) crossed below signal ({signal_val:.4f}) => SELL"
            )
        else:
            reasons.append("No MACD crossover detected => HOLD")

        return {
            "reasons": reasons,
            "key_metrics": {
                "macd_line": float(macd),
                "signal_line": float(signal_val),
                "histogram": float(histogram),
                "current_price": float(price),
            },
        }
