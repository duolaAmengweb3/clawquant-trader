"""Walk-forward validation: rolling train/test window optimization."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from clawquant.core.backtest.result import BacktestResult

logger = logging.getLogger(__name__)


def run_walkforward(
    strategy_name: str,
    symbol: str = "BTC/USDT",
    interval: str = "1h",
    days: int = 90,
    train_pct: float = 0.7,
    n_splits: int = 3,
    param_grid: Optional[Dict[str, list]] = None,
    capital: float = 10000.0,
) -> Dict[str, Any]:
    """Run walk-forward validation.

    Splits data into n_splits windows. For each window:
    1. Train: sweep params on train portion, pick best by stability score.
    2. Test: run best params on test portion (no look-back).

    Args:
        strategy_name: Strategy name.
        symbol: Trading pair.
        interval: Bar interval.
        days: Total data window.
        train_pct: Fraction of each split for training.
        n_splits: Number of rolling splits.
        param_grid: Parameter grid for optimization.
        capital: Initial capital.

    Returns:
        Dict with split results, aggregate metrics, and best params per split.
    """
    from clawquant.core.backtest.config import BacktestConfig
    from clawquant.core.backtest.engine import BacktestEngine
    from clawquant.core.backtest.sweep import run_sweep
    from clawquant.core.data.fetcher import fetch_data
    from clawquant.core.data.models import DataPullRequest
    from clawquant.core.evaluate.metrics import compute_metrics
    from clawquant.core.evaluate.scorer import compute_stability_score
    from clawquant.core.runtime.loader import load_strategy

    # Fetch full data window
    request = DataPullRequest(symbols=[symbol], interval=interval, days=days)
    dfs = fetch_data(request)
    df = dfs.get(symbol)

    if df is None or df.empty:
        return {"success": False, "error_type": "DataError", "message": f"No data for {symbol}"}

    total_bars = len(df)
    split_size = total_bars // n_splits
    if split_size < 20:
        return {"success": False, "error_type": "ConfigError", "message": f"Not enough data: {total_bars} bars for {n_splits} splits"}

    strat = load_strategy(strategy_name)
    splits = []

    for i in range(n_splits):
        start_idx = i * split_size
        end_idx = min(start_idx + split_size, total_bars)
        split_df = df.iloc[start_idx:end_idx].reset_index(drop=True)

        train_size = int(len(split_df) * train_pct)
        train_df = split_df.iloc[:train_size].reset_index(drop=True)
        test_df = split_df.iloc[train_size:].reset_index(drop=True)

        logger.info(f"Split {i+1}/{n_splits}: train={len(train_df)} bars, test={len(test_df)} bars")

        # Train phase: find best params
        best_params = {}
        best_score = -1

        if param_grid:
            import itertools
            keys = list(param_grid.keys())
            values = list(param_grid.values())
            for combo in itertools.product(*values):
                params = dict(zip(keys, combo))
                try:
                    config = BacktestConfig(
                        initial_capital=capital,
                        strategy_name=strategy_name,
                        strategy_params=params,
                        symbol=symbol,
                        interval=interval,
                    )
                    engine = BacktestEngine(config, strat, train_df.copy())
                    result = engine.run()
                    if result.success and result.equity_curve:
                        metrics = compute_metrics(result.equity_curve, result.trades, capital)
                        score = compute_stability_score(metrics, result.trades)
                        if score["total"] > best_score:
                            best_score = score["total"]
                            best_params = params
                except Exception:
                    continue
        else:
            # Use default params
            meta = strat.metadata()
            for k, v in meta.params_schema.get("properties", {}).items():
                if "default" in v:
                    best_params[k] = v["default"]

        # Test phase: run best params on unseen data
        try:
            config = BacktestConfig(
                initial_capital=capital,
                strategy_name=strategy_name,
                strategy_params=best_params,
                symbol=symbol,
                interval=interval,
            )
            engine = BacktestEngine(config, strat, test_df.copy())
            test_result = engine.run()

            test_metrics = {}
            test_score = {}
            if test_result.success and test_result.equity_curve:
                test_metrics = compute_metrics(test_result.equity_curve, test_result.trades, capital)
                test_score = compute_stability_score(test_metrics, test_result.trades)
        except Exception as e:
            test_result = BacktestResult(run_id="", success=False, error_type="ExecutionError", message=str(e))
            test_metrics = {}
            test_score = {}

        splits.append({
            "split": i + 1,
            "train_bars": len(train_df),
            "test_bars": len(test_df),
            "best_params": best_params,
            "train_score": best_score,
            "test_return_pct": test_metrics.get("total_return_pct", 0),
            "test_sharpe": test_metrics.get("sharpe_ratio", 0),
            "test_max_dd_pct": test_metrics.get("max_drawdown_pct", 0),
            "test_score": test_score.get("total", 0),
            "test_trades": test_metrics.get("total_trades", 0),
        })

    # Aggregate
    test_returns = [s["test_return_pct"] for s in splits]
    test_scores = [s["test_score"] for s in splits]
    avg_return = sum(test_returns) / len(test_returns) if test_returns else 0
    avg_score = sum(test_scores) / len(test_scores) if test_scores else 0

    return {
        "success": True,
        "strategy": strategy_name,
        "symbol": symbol,
        "n_splits": n_splits,
        "train_pct": train_pct,
        "splits": splits,
        "aggregate": {
            "avg_test_return_pct": round(avg_return, 2),
            "avg_test_score": round(avg_score, 1),
            "return_std": round(pd.Series(test_returns).std(), 2) if len(test_returns) > 1 else 0,
            "score_std": round(pd.Series(test_scores).std(), 1) if len(test_scores) > 1 else 0,
        },
    }
