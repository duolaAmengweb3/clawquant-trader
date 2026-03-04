"""Batch backtest: run multiple strategy/symbol combinations in parallel."""

from __future__ import annotations

import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import List, Optional

from clawquant.core.backtest.config import BacktestConfig
from clawquant.core.backtest.result import BacktestResult

logger = logging.getLogger(__name__)


def _run_single(args: dict) -> dict:
    """Run a single backtest (designed to be called in a subprocess)."""
    from clawquant.core.backtest.config import BacktestConfig
    from clawquant.core.backtest.engine import BacktestEngine
    from clawquant.core.data.fetcher import fetch_data
    from clawquant.core.data.models import DataPullRequest
    from clawquant.core.runtime.loader import load_strategy

    strategy_name = args["strategy"]
    symbol = args["symbol"]
    interval = args.get("interval", "1h")
    days = args.get("days", 30)
    capital = args.get("capital", 10000.0)
    params = args.get("params", {})

    try:
        strat = load_strategy(strategy_name)
        request = DataPullRequest(symbols=[symbol], interval=interval, days=days)
        dfs = fetch_data(request)
        df = dfs.get(symbol)

        if df is None or df.empty:
            return {"success": False, "error_type": "DataError", "message": f"No data for {symbol}", "run_id": ""}

        config = BacktestConfig(
            initial_capital=capital,
            strategy_name=strategy_name,
            strategy_params=params,
            symbol=symbol,
            interval=interval,
            days=days,
        )
        engine = BacktestEngine(config, strat, df)
        result = engine.run()
        return result.model_dump(mode="json")
    except Exception as e:
        return {"success": False, "error_type": "ExecutionError", "message": str(e), "run_id": ""}


def run_batch(
    strategies: List[str],
    symbols: List[str],
    interval: str = "1h",
    days: int = 30,
    capital: float = 10000.0,
    max_workers: Optional[int] = None,
    params_override: Optional[dict] = None,
) -> List[BacktestResult]:
    """Run backtests for all strategy x symbol combinations.

    Args:
        strategies: List of strategy names.
        symbols: List of trading symbols.
        interval: Bar interval.
        days: Backtest window.
        capital: Initial capital per test.
        max_workers: Max parallel workers (default: min(cpu_count, len(jobs))).
        params_override: Optional dict of {strategy_name: params_dict}.

    Returns:
        List of BacktestResult (one per combination).
    """
    jobs = []
    for strat_name in strategies:
        for symbol in symbols:
            params = {}
            if params_override and strat_name in params_override:
                params = params_override[strat_name]
            jobs.append({
                "strategy": strat_name,
                "symbol": symbol,
                "interval": interval,
                "days": days,
                "capital": capital,
                "params": params,
            })

    logger.info(f"Batch backtest: {len(jobs)} jobs ({len(strategies)} strategies x {len(symbols)} symbols)")

    results = []
    n_workers = min(max_workers or 4, len(jobs))

    if n_workers <= 1 or len(jobs) == 1:
        # Sequential for single job or debugging
        for job in jobs:
            r = _run_single(job)
            results.append(BacktestResult(**r))
    else:
        with ProcessPoolExecutor(max_workers=n_workers) as executor:
            futures = {executor.submit(_run_single, job): job for job in jobs}
            for future in as_completed(futures):
                try:
                    r = future.result()
                    results.append(BacktestResult(**r))
                except Exception as e:
                    job = futures[future]
                    results.append(BacktestResult(
                        run_id="",
                        success=False,
                        error_type="ExecutionError",
                        message=f"{job['strategy']}@{job['symbol']}: {e}",
                    ))

    logger.info(f"Batch complete: {sum(1 for r in results if r.success)}/{len(results)} succeeded")
    return results
