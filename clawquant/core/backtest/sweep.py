"""Parameter sweep: grid search and random search over strategy params."""

from __future__ import annotations

import itertools
import logging
import random
from typing import Any, Dict, List, Optional

from clawquant.core.backtest.config import BacktestConfig
from clawquant.core.backtest.result import BacktestResult

logger = logging.getLogger(__name__)


def _generate_grid_combos(param_grid: Dict[str, list]) -> List[dict]:
    """Generate all combinations from a parameter grid."""
    if not param_grid:
        return [{}]
    keys = list(param_grid.keys())
    values = list(param_grid.values())
    combos = []
    for combo in itertools.product(*values):
        combos.append(dict(zip(keys, combo)))
    return combos


def _generate_random_combos(param_grid: Dict[str, list], n: int) -> List[dict]:
    """Generate n random combinations from a parameter grid."""
    if not param_grid:
        return [{}]
    keys = list(param_grid.keys())
    values = list(param_grid.values())
    combos = []
    for _ in range(n):
        combo = {k: random.choice(v) for k, v in zip(keys, values)}
        combos.append(combo)
    return combos


def run_sweep(
    strategy_name: str,
    symbol: str = "BTC/USDT",
    interval: str = "1h",
    days: int = 30,
    param_grid: Optional[Dict[str, list]] = None,
    mode: str = "grid",
    n_random: int = 20,
    capital: float = 10000.0,
) -> List[BacktestResult]:
    """Run parameter sweep over a strategy.

    Args:
        strategy_name: Strategy to sweep.
        symbol: Trading pair.
        interval: Bar interval.
        days: Backtest window.
        param_grid: Dict of param_name -> list of values to try.
            Example: {"fast_period": [5, 10, 20], "slow_period": [20, 30, 50]}
        mode: "grid" for exhaustive, "random" for random sampling.
        n_random: Number of random samples (only used if mode="random").
        capital: Initial capital.

    Returns:
        List of BacktestResult sorted by stability_score descending.
    """
    from clawquant.core.backtest.engine import BacktestEngine
    from clawquant.core.data.fetcher import fetch_data
    from clawquant.core.data.models import DataPullRequest
    from clawquant.core.evaluate.metrics import compute_metrics
    from clawquant.core.evaluate.scorer import compute_stability_score
    from clawquant.core.runtime.loader import load_strategy

    if param_grid is None:
        param_grid = {}

    # Generate parameter combinations
    if mode == "random":
        combos = _generate_random_combos(param_grid, n_random)
    else:
        combos = _generate_grid_combos(param_grid)

    logger.info(f"Parameter sweep: {len(combos)} combinations for {strategy_name} on {symbol}")

    # Fetch data once
    strat = load_strategy(strategy_name)
    request = DataPullRequest(symbols=[symbol], interval=interval, days=days)
    dfs = fetch_data(request)
    df = dfs.get(symbol)

    if df is None or df.empty:
        return [BacktestResult(run_id="", success=False, error_type="DataError", message=f"No data for {symbol}")]

    results = []
    for i, params in enumerate(combos):
        logger.info(f"  [{i+1}/{len(combos)}] {params}")
        try:
            config = BacktestConfig(
                initial_capital=capital,
                strategy_name=strategy_name,
                strategy_params=params,
                symbol=symbol,
                interval=interval,
                days=days,
            )
            engine = BacktestEngine(config, strat, df.copy())
            result = engine.run()

            # Compute full metrics and score
            if result.success and result.equity_curve:
                metrics = compute_metrics(result.equity_curve, result.trades, capital)
                score = compute_stability_score(metrics, result.trades)
                result.sharpe_ratio = metrics.get("sharpe_ratio", 0)
                result.sortino_ratio = metrics.get("sortino_ratio", 0)
                result.calmar_ratio = metrics.get("calmar_ratio", 0)
                result.stability_score = score.get("total", 0)
                result.score_breakdown = score

            results.append(result)
        except Exception as e:
            results.append(BacktestResult(
                run_id="",
                success=False,
                error_type="ExecutionError",
                message=f"Params {params}: {e}",
            ))

    # Sort by stability score
    results.sort(key=lambda r: r.stability_score, reverse=True)
    return results
