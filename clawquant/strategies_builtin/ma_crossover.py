"""Moving Average Crossover strategy.

Generates buy signals when a fast moving average crosses above a slow moving
average, and sell signals when it crosses below.  Supports both SMA and EMA.
"""

from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd

from clawquant.core.runtime.base_strategy import BaseStrategy
from clawquant.core.runtime.models import MarketState, PortfolioState, StrategyMetadata


class MACrossoverStrategy(BaseStrategy):
    """Classic dual moving-average crossover."""

    # ------------------------------------------------------------------
    # 1. Metadata
    # ------------------------------------------------------------------
    @classmethod
    def metadata(cls) -> StrategyMetadata:
        return StrategyMetadata(
            name="ma_crossover",
            version="1.0.0",
            description="Moving Average Crossover - buy when fast MA crosses above slow MA, sell on cross below.",
            params_schema={
                "type": "object",
                "properties": {
                    "fast_period": {
                        "type": "integer",
                        "description": "Period for the fast moving average.",
                        "default": 10,
                        "minimum": 2,
                    },
                    "slow_period": {
                        "type": "integer",
                        "description": "Period for the slow moving average.",
                        "default": 30,
                        "minimum": 2,
                    },
                    "ma_type": {
                        "type": "string",
                        "description": "Type of moving average: SMA or EMA.",
                        "default": "SMA",
                        "enum": ["SMA", "EMA"],
                    },
                    "position_pct": {
                        "type": "number",
                        "description": "Fraction of equity to allocate per trade.",
                        "default": 0.1,
                        "minimum": 0.01,
                        "maximum": 1.0,
                    },
                },
                "required": ["fast_period", "slow_period"],
            },
            tags=["trend-following", "momentum", "classic"],
        )

    # ------------------------------------------------------------------
    # 2. Indicators
    # ------------------------------------------------------------------
    def compute_indicators(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        df = df.copy()
        fast_period = params.get("fast_period", 10)
        slow_period = params.get("slow_period", 30)
        ma_type = params.get("ma_type", "SMA").upper()

        close = df["close"]
        if ma_type == "EMA":
            df["ma_crossover_fast_ma"] = close.ewm(span=fast_period, adjust=False).mean()
            df["ma_crossover_slow_ma"] = close.ewm(span=slow_period, adjust=False).mean()
        else:  # SMA
            df["ma_crossover_fast_ma"] = close.rolling(window=fast_period, min_periods=fast_period).mean()
            df["ma_crossover_slow_ma"] = close.rolling(window=slow_period, min_periods=slow_period).mean()

        return df

    # ------------------------------------------------------------------
    # 3. Signals
    # ------------------------------------------------------------------
    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.Series:
        # Ensure indicators exist
        if "ma_crossover_fast_ma" not in df.columns:
            df = self.compute_indicators(df, params)

        fast = df["ma_crossover_fast_ma"]
        slow = df["ma_crossover_slow_ma"]

        # Determine crossover: compare current relative position to previous
        # fast > slow = 1 (bullish), fast < slow = -1 (bearish)
        position = pd.Series(np.where(fast > slow, 1, np.where(fast < slow, -1, 0)),
                             index=df.index, dtype=int)

        # Signal only on the bar where position changes (the actual crossover)
        signals = position.diff().fillna(0).astype(int)

        # Clamp to {-1, 0, 1}
        signals = signals.clip(-1, 1)

        # NaN rows (where MAs are not yet computed) should be HOLD
        nan_mask = fast.isna() | slow.isna()
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
            # Buy: use position_pct of equity, limited by available cash
            amount = equity * position_pct
            return min(amount, portfolio_state.cash)
        elif signal == -1:
            # Sell: close entire position
            total_pos_value = sum(portfolio_state.position_values.values())
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

        # Check if position is too large relative to equity
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

        # Check drawdown: if unrealized PnL is very negative
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
        fast_ma = last_state.get("fast_ma", 0.0)
        slow_ma = last_state.get("slow_ma", 0.0)
        price = last_state.get("price", 0.0)

        reasons: list[str] = []
        if signal == 1:
            reasons.append(
                f"Fast MA ({fast_ma:.4f}) crossed above Slow MA ({slow_ma:.4f}) => BUY"
            )
        elif signal == -1:
            reasons.append(
                f"Fast MA ({fast_ma:.4f}) crossed below Slow MA ({slow_ma:.4f}) => SELL"
            )
        else:
            reasons.append("No crossover detected => HOLD")

        return {
            "reasons": reasons,
            "key_metrics": {
                "fast_ma": float(fast_ma),
                "slow_ma": float(slow_ma),
                "current_price": float(price),
                "spread": float(fast_ma - slow_ma),
            },
        }
