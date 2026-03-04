"""Base strategy abstract class for ClawQuant Trader.

All strategies must inherit from BaseStrategy and implement all six abstract
methods with real logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List

import pandas as pd

from clawquant.core.runtime.models import MarketState, PortfolioState, StrategyMetadata


class BaseStrategy(ABC):
    """Abstract base class that every ClawQuant strategy must implement."""

    # ------------------------------------------------------------------
    # 1. Metadata
    # ------------------------------------------------------------------
    @classmethod
    @abstractmethod
    def metadata(cls) -> StrategyMetadata:
        """Return strategy metadata including params JSON Schema.

        The returned ``StrategyMetadata.params_schema`` must be a valid
        JSON Schema object whose ``properties`` each carry a ``default``
        value so that the strategy can be executed without explicit user
        configuration.
        """
        ...

    # ------------------------------------------------------------------
    # 2. Indicator computation
    # ------------------------------------------------------------------
    @abstractmethod
    def compute_indicators(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        """Compute technical indicators on *df*.

        Rules
        -----
        * Must **not** modify the original OHLCV columns
          (``open``, ``high``, ``low``, ``close``, ``volume``).
        * All new column names must be prefixed with the strategy name
          (e.g. ``ma_crossover_fast_ma``).
        * Must return the augmented DataFrame.
        """
        ...

    # ------------------------------------------------------------------
    # 3. Signal generation
    # ------------------------------------------------------------------
    @abstractmethod
    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.Series:
        """Return a signal ``pd.Series`` aligned with *df*.

        Allowed values: ``{1, 0, -1}`` where:
        * **1** = BUY
        * **0** = HOLD
        * **-1** = SELL

        The series length **must** equal ``len(df)``.
        Implementations must only use current and past data (no look-ahead).
        """
        ...

    # ------------------------------------------------------------------
    # 4. Position sizing
    # ------------------------------------------------------------------
    @abstractmethod
    def position_sizing(
        self,
        signal: int,
        portfolio_state: PortfolioState,
        params: dict,
    ) -> float:
        """Return target position change in USDT.

        * Positive = buy
        * Negative = sell
        * Zero     = hold / no action
        """
        ...

    # ------------------------------------------------------------------
    # 5. Risk controls
    # ------------------------------------------------------------------
    @abstractmethod
    def risk_controls(
        self,
        portfolio_state: PortfolioState,
        market_state: MarketState,
        params: dict,
    ) -> List[dict]:
        """Return a list of risk-control actions.

        Each action is a dict with:
        * ``"action"``: one of ``"REDUCE"``, ``"FLATTEN"``, ``"SKIP"``, ``"NONE"``
        * ``"reason"``: human-readable explanation string
        """
        ...

    # ------------------------------------------------------------------
    # 6. Explainability
    # ------------------------------------------------------------------
    @abstractmethod
    def explain(self, last_state: dict) -> dict:
        """Return an explainable output dictionary.

        Must contain at least:
        * ``"reasons"``: ``List[str]`` - human-readable reasons for the last action.
        * ``"key_metrics"``: ``Dict[str, float]`` - important numeric metrics.
        """
        ...
