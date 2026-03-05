"""Bollinger Bands strategy.

Buys when price touches the lower band and sells when price touches the upper
band.  A volatility-based mean-reversion strategy.
"""

from __future__ import annotations

from typing import List

import pandas as pd

from clawquant.core.runtime.base_strategy import BaseStrategy
from clawquant.core.runtime.models import MarketState, PortfolioState, StrategyMetadata


class BollingerBandsStrategy(BaseStrategy):
    """Bollinger Bands mean-reversion strategy."""

    # ------------------------------------------------------------------
    # 1. Metadata
    # ------------------------------------------------------------------
    @classmethod
    def metadata(cls) -> StrategyMetadata:
        return StrategyMetadata(
            name="bollinger_bands",
            version="1.0.0",
            description="Bollinger Bands - buy at lower band, sell at upper band.",
            params_schema={
                "type": "object",
                "properties": {
                    "bb_period": {
                        "type": "integer",
                        "description": "Lookback period for the middle band (SMA).",
                        "default": 20,
                        "minimum": 2,
                    },
                    "bb_std": {
                        "type": "number",
                        "description": "Number of standard deviations for upper/lower bands.",
                        "default": 2.0,
                        "minimum": 0.1,
                    },
                    "position_pct": {
                        "type": "number",
                        "description": "Fraction of equity to allocate per trade.",
                        "default": 0.1,
                        "minimum": 0.01,
                        "maximum": 1.0,
                    },
                },
                "required": ["bb_period"],
            },
            tags=["mean-reversion", "volatility"],
        )

    # ------------------------------------------------------------------
    # 2. Indicators
    # ------------------------------------------------------------------
    def compute_indicators(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        df = df.copy()
        period = params.get("bb_period", 20)
        num_std = params.get("bb_std", 2.0)
        close = df["close"]

        sma = close.rolling(window=period, min_periods=period).mean()
        std = close.rolling(window=period, min_periods=period).std()

        df["bollinger_bands_middle"] = sma
        df["bollinger_bands_upper"] = sma + num_std * std
        df["bollinger_bands_lower"] = sma - num_std * std

        return df

    # ------------------------------------------------------------------
    # 3. Signals
    # ------------------------------------------------------------------
    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.Series:
        if "bollinger_bands_middle" not in df.columns:
            df = self.compute_indicators(df, params)

        close = df["close"]
        upper = df["bollinger_bands_upper"]
        lower = df["bollinger_bands_lower"]

        signals = pd.Series(0, index=df.index, dtype=int)
        signals[close <= lower] = 1   # Price at/below lower band => BUY
        signals[close >= upper] = -1  # Price at/above upper band => SELL

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
        upper = last_state.get("upper_band", 0.0)
        lower = last_state.get("lower_band", 0.0)
        middle = last_state.get("middle_band", 0.0)

        reasons: list[str] = []
        if signal == 1:
            reasons.append(f"Price ({price:.4f}) touched lower band ({lower:.4f}) => BUY")
        elif signal == -1:
            reasons.append(f"Price ({price:.4f}) touched upper band ({upper:.4f}) => SELL")
        else:
            reasons.append(f"Price ({price:.4f}) is between bands => HOLD")

        return {
            "reasons": reasons,
            "key_metrics": {
                "current_price": float(price),
                "upper_band": float(upper),
                "middle_band": float(middle),
                "lower_band": float(lower),
                "bandwidth": float(upper - lower) if upper and lower else 0.0,
            },
        }
