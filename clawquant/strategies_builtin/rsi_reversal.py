"""RSI Reversal strategy.

Buys when RSI drops below the oversold threshold and sells when RSI rises
above the overbought threshold.  A classic mean-reversion oscillator strategy.
"""

from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd

from clawquant.core.runtime.base_strategy import BaseStrategy
from clawquant.core.runtime.models import MarketState, PortfolioState, StrategyMetadata


class RSIReversalStrategy(BaseStrategy):
    """RSI-based mean-reversion strategy."""

    # ------------------------------------------------------------------
    # 1. Metadata
    # ------------------------------------------------------------------
    @classmethod
    def metadata(cls) -> StrategyMetadata:
        return StrategyMetadata(
            name="rsi_reversal",
            version="1.0.0",
            description="RSI Reversal - buy when RSI < oversold, sell when RSI > overbought.",
            params_schema={
                "type": "object",
                "properties": {
                    "rsi_period": {
                        "type": "integer",
                        "description": "Lookback period for RSI calculation.",
                        "default": 14,
                        "minimum": 2,
                    },
                    "oversold": {
                        "type": "number",
                        "description": "RSI level below which the asset is considered oversold (buy signal).",
                        "default": 30,
                        "minimum": 0,
                        "maximum": 100,
                    },
                    "overbought": {
                        "type": "number",
                        "description": "RSI level above which the asset is considered overbought (sell signal).",
                        "default": 70,
                        "minimum": 0,
                        "maximum": 100,
                    },
                    "position_pct": {
                        "type": "number",
                        "description": "Fraction of equity to allocate per trade.",
                        "default": 0.1,
                        "minimum": 0.01,
                        "maximum": 1.0,
                    },
                },
                "required": ["rsi_period"],
            },
            tags=["mean-reversion", "oscillator"],
        )

    # ------------------------------------------------------------------
    # 2. Indicators
    # ------------------------------------------------------------------
    def compute_indicators(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        df = df.copy()
        period = params.get("rsi_period", 14)
        close = df["close"]

        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

        rs = avg_gain / avg_loss.replace(0, np.nan)
        df["rsi_reversal_rsi"] = 100 - (100 / (1 + rs))

        return df

    # ------------------------------------------------------------------
    # 3. Signals
    # ------------------------------------------------------------------
    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.Series:
        if "rsi_reversal_rsi" not in df.columns:
            df = self.compute_indicators(df, params)

        rsi = df["rsi_reversal_rsi"]
        oversold = params.get("oversold", 30)
        overbought = params.get("overbought", 70)

        signals = pd.Series(0, index=df.index, dtype=int)
        signals[rsi < oversold] = 1
        signals[rsi > overbought] = -1

        # NaN rows should be HOLD
        signals[rsi.isna()] = 0

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
        rsi = last_state.get("rsi", 0.0)
        price = last_state.get("price", 0.0)

        reasons: list[str] = []
        if signal == 1:
            reasons.append(f"RSI ({rsi:.2f}) is below oversold threshold => BUY")
        elif signal == -1:
            reasons.append(f"RSI ({rsi:.2f}) is above overbought threshold => SELL")
        else:
            reasons.append(f"RSI ({rsi:.2f}) is in neutral zone => HOLD")

        return {
            "reasons": reasons,
            "key_metrics": {
                "rsi": float(rsi),
                "current_price": float(price),
            },
        }
