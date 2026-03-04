"""Grid Trading strategy (stateful).

Maintains a grid of price levels around an initial reference price. Buys when
price drops to a grid level (not yet filled) and sells when price rises to a
grid level (already filled).
"""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from clawquant.core.runtime.base_strategy import BaseStrategy
from clawquant.core.runtime.models import MarketState, PortfolioState, StrategyMetadata


class GridStrategy(BaseStrategy):
    """Stateful grid trading strategy."""

    def __init__(self) -> None:
        super().__init__()
        # State: tracks which grid levels have been filled (bought into).
        # Key = grid level index (int), Value = price of that grid level.
        self._filled_levels: Dict[int, float] = {}
        self._grid_prices: List[float] = []
        self._initial_price: Optional[float] = None
        self._initialized: bool = False

    # ------------------------------------------------------------------
    # Internal: lazily build the grid around first observed price
    # ------------------------------------------------------------------
    def _ensure_grid(self, price: float, params: dict) -> None:
        if self._initialized:
            return
        grid_levels = params.get("grid_levels", 5)
        grid_spacing_pct = params.get("grid_spacing_pct", 2.0) / 100.0

        self._initial_price = price
        self._grid_prices = []
        # Build symmetric grid: levels below and above the initial price
        for i in range(-grid_levels, grid_levels + 1):
            level_price = price * (1 + i * grid_spacing_pct)
            if level_price > 0:
                self._grid_prices.append(level_price)
        self._grid_prices.sort()
        self._filled_levels = {}
        self._initialized = True

    def _find_nearest_level_index(self, price: float) -> int:
        """Return index of the grid level closest to *price*."""
        if not self._grid_prices:
            return -1
        diffs = [abs(p - price) for p in self._grid_prices]
        return int(np.argmin(diffs))

    # ------------------------------------------------------------------
    # 1. Metadata
    # ------------------------------------------------------------------
    @classmethod
    def metadata(cls) -> StrategyMetadata:
        return StrategyMetadata(
            name="grid",
            version="1.0.0",
            description="Grid Trading - places buy/sell orders at fixed price intervals around a reference price.",
            params_schema={
                "type": "object",
                "properties": {
                    "grid_levels": {
                        "type": "integer",
                        "description": "Number of grid levels above and below the reference price.",
                        "default": 5,
                        "minimum": 1,
                    },
                    "grid_spacing_pct": {
                        "type": "number",
                        "description": "Spacing between grid levels as a percentage of the reference price.",
                        "default": 2.0,
                        "minimum": 0.1,
                    },
                    "amount_per_grid": {
                        "type": "number",
                        "description": "USDT amount to buy/sell at each grid level.",
                        "default": 200.0,
                        "minimum": 1.0,
                    },
                    "max_open_grids": {
                        "type": "integer",
                        "description": "Maximum number of simultaneously filled grid levels.",
                        "default": 10,
                        "minimum": 1,
                    },
                },
                "required": ["grid_levels", "grid_spacing_pct", "amount_per_grid"],
            },
            tags=["mean-reversion", "range-bound", "stateful"],
        )

    # ------------------------------------------------------------------
    # 2. Indicators
    # ------------------------------------------------------------------
    def compute_indicators(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        df = df.copy()
        # Ensure the grid is initialized from the first close price
        self._ensure_grid(float(df["close"].iloc[0]), params)

        # Add grid reference columns for observability
        df["grid_initial_price"] = self._initial_price
        df["grid_num_levels"] = len(self._grid_prices)
        return df

    # ------------------------------------------------------------------
    # 3. Signals
    # ------------------------------------------------------------------
    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.Series:
        self._ensure_grid(float(df["close"].iloc[0]), params)

        grid_spacing_pct = params.get("grid_spacing_pct", 2.0) / 100.0
        signals = pd.Series(0, index=df.index, dtype=int)

        # Reset state for clean signal generation over the full DataFrame
        filled: Dict[int, float] = {}

        for i in range(len(df)):
            price = float(df["close"].iloc[i])
            level_idx = self._find_nearest_level_index(price)
            if level_idx < 0:
                continue

            level_price = self._grid_prices[level_idx]
            # Price must be within half a grid spacing of the level to trigger
            threshold = level_price * grid_spacing_pct * 0.5

            if abs(price - level_price) > threshold:
                continue

            # Determine center index (the level closest to initial price)
            center_idx = self._find_nearest_level_index(self._initial_price or price)

            if level_idx < center_idx and level_idx not in filled:
                # Price is at a lower grid level and it's not filled => BUY
                signals.iloc[i] = 1
                filled[level_idx] = level_price
            elif level_idx > center_idx and level_idx in filled:
                # Price is at a higher grid level and it IS filled => SELL
                signals.iloc[i] = -1
                del filled[level_idx]
            elif level_idx <= center_idx and level_idx not in filled:
                # At or below center, not filled => BUY
                signals.iloc[i] = 1
                filled[level_idx] = level_price
            elif level_idx > center_idx and level_idx not in filled:
                # Above center and not filled => no action
                pass

        # Store the final state for later use
        self._filled_levels = filled
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

        amount = params.get("amount_per_grid", 200.0)

        if signal == 1:
            return min(amount, portfolio_state.cash)
        elif signal == -1:
            total_pos_value = sum(portfolio_state.position_values.values())
            return -min(amount, total_pos_value)

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
        max_open = params.get("max_open_grids", 10)

        if len(self._filled_levels) >= max_open:
            actions.append({
                "action": "SKIP",
                "reason": (
                    f"Maximum open grid levels ({max_open}) reached. "
                    f"Currently filled: {len(self._filled_levels)}"
                ),
            })
            return actions

        # If price has moved far outside the grid range, flatten
        if self._grid_prices:
            lowest = self._grid_prices[0]
            highest = self._grid_prices[-1]
            price = market_state.current_price
            if price < lowest * 0.9 or price > highest * 1.1:
                actions.append({
                    "action": "FLATTEN",
                    "reason": (
                        f"Price ({price:.2f}) has moved >10% outside grid range "
                        f"[{lowest:.2f}, {highest:.2f}]. Flattening positions."
                    ),
                })
                return actions

        actions.append({"action": "NONE", "reason": "All grid risk checks passed."})
        return actions

    # ------------------------------------------------------------------
    # 6. Explain
    # ------------------------------------------------------------------
    def explain(self, last_state: dict) -> dict:
        signal = last_state.get("signal", 0)
        price = last_state.get("price", 0.0)

        reasons: list[str] = []
        if signal == 1:
            reasons.append(f"Price ({price:.2f}) hit a lower grid level => BUY")
        elif signal == -1:
            reasons.append(f"Price ({price:.2f}) hit an upper filled grid level => SELL")
        else:
            reasons.append("Price is between grid levels => HOLD")

        reasons.append(f"Filled grid levels: {len(self._filled_levels)}")
        reasons.append(f"Total grid levels: {len(self._grid_prices)}")

        return {
            "reasons": reasons,
            "key_metrics": {
                "current_price": float(price),
                "filled_levels": float(len(self._filled_levels)),
                "total_levels": float(len(self._grid_prices)),
                "initial_price": float(self._initial_price or 0.0),
            },
        }
