"""Backtest CLI command implementations."""

from __future__ import annotations

import json
from typing import Optional

from clawquant.core.utils.output import print_error, print_result, print_table


def run(
    strategy: str,
    symbol: str = "BTC/USDT",
    interval: str = "1h",
    days: int = 30,
    capital: float = 10000.0,
    fee_bps: int = 10,
    slippage_bps: int = 5,
    params: Optional[str] = None,
    dry_run: bool = False,
    json_mode: bool = False,
) -> None:
    """Run a single backtest."""
    from clawquant.core.backtest.config import BacktestConfig
    from clawquant.core.backtest.engine import BacktestEngine
    from clawquant.core.data.fetcher import fetch_data
    from clawquant.core.data.models import DataPullRequest
    from clawquant.core.runtime.loader import load_strategy

    # Parse strategy params
    strategy_params = {}
    if params:
        try:
            strategy_params = json.loads(params)
        except json.JSONDecodeError as e:
            print_error("ConfigError", f"Invalid params JSON: {e}", "Use valid JSON, e.g. '{\"fast_period\": 10}'")
            return

    # Load strategy
    try:
        strat = load_strategy(strategy)
    except Exception as e:
        print_error("StrategyError", f"Failed to load strategy '{strategy}': {e}", "Check strategy name with 'clawquant strategy list'")
        return

    # Build config
    config = BacktestConfig(
        initial_capital=capital,
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
        strategy_name=strategy,
        strategy_params=strategy_params,
        symbol=symbol,
        interval=interval,
        days=days,
    )

    # Fetch data
    try:
        request = DataPullRequest(symbols=[symbol], interval=interval, days=days)
        dfs = fetch_data(request)
        df = dfs.get(symbol)
        if df is None or df.empty:
            print_error("DataError", f"No data for {symbol}", "Try 'clawquant data pull' first")
            return
    except Exception as e:
        print_error("DataError", f"Failed to fetch data: {e}", "Check network or try 'clawquant data pull' first")
        return

    # Dry run check
    if dry_run:
        from clawquant.core.data.inspector import inspect_data
        report = inspect_data(df, symbol, interval)
        meta = strat.metadata()
        result_data = {
            "ready": report.passed,
            "strategy": meta.name,
            "data_bars": report.total_bars,
            "data_quality": "PASS" if report.passed else "FAIL",
            "issues": report.issues,
        }
        print_result(result_data, json_mode=json_mode)
        return

    # Run backtest
    engine = BacktestEngine(config, strat, df)
    result = engine.run()

    if not result.success:
        print_error(result.error_type or "Error", result.message or "Unknown error")
        return

    # Display results
    summary = {
        "run_id": result.run_id,
        "strategy": strategy,
        "symbol": symbol,
        "total_return": f"{result.total_return_pct:.2f}%",
        "max_drawdown": f"{result.max_drawdown_pct:.2f}%",
        "sharpe_ratio": f"{result.sharpe_ratio:.4f}",
        "win_rate": f"{result.win_rate:.1f}%",
        "total_trades": result.total_trades,
        "profit_factor": f"{result.profit_factor:.4f}",
        "avg_trade_pnl": f"${result.avg_trade_pnl:.2f}",
        "warnings": result.warnings,
    }

    if json_mode:
        print_result(result.model_dump(mode="json"), json_mode=True)
    else:
        print_table(
            headers=["Metric", "Value"],
            rows=[[k, str(v)] for k, v in summary.items() if k != "warnings"],
            title=f"Backtest Result: {result.run_id}",
            json_mode=False,
        )
        if result.warnings:
            from rich.console import Console
            console = Console()
            for w in result.warnings:
                console.print(f"  [yellow]⚠ {w}[/yellow]")


def batch(
    strategies: str,
    symbols: str,
    interval: str = "1h",
    days: int = 30,
    capital: float = 10000.0,
    json_mode: bool = False,
) -> None:
    """Run batch backtest (delegates to batch module)."""
    from clawquant.core.backtest.batch import run_batch

    strategy_list = [s.strip() for s in strategies.split(",")]
    symbol_list = [s.strip() for s in symbols.split(",")]

    results = run_batch(strategy_list, symbol_list, interval, days, capital)

    if json_mode:
        print_result([r.model_dump(mode="json") for r in results], json_mode=True)
    else:
        rows = []
        for r in results:
            rows.append([
                r.run_id[:40],
                r.run_meta.strategy["name"] if r.run_meta else "?",
                r.run_meta.data["symbol"] if r.run_meta else "?",
                f"{r.total_return_pct:.2f}%",
                f"{r.max_drawdown_pct:.2f}%",
                str(r.total_trades),
                f"{r.win_rate:.1f}%",
            ])
        print_table(
            headers=["Run ID", "Strategy", "Symbol", "Return", "MaxDD", "Trades", "WinRate"],
            rows=rows,
            title="Batch Backtest Results",
            json_mode=False,
        )


def sweep(
    strategy: str,
    symbol: str = "BTC/USDT",
    interval: str = "1h",
    days: int = 30,
    param_grid: Optional[str] = None,
    mode: str = "grid",
    n_random: int = 20,
    json_mode: bool = False,
) -> None:
    """Run parameter sweep (delegates to sweep module)."""
    from clawquant.core.backtest.sweep import run_sweep

    grid = {}
    if param_grid:
        try:
            grid = json.loads(param_grid)
        except json.JSONDecodeError as e:
            print_error("ConfigError", f"Invalid param_grid JSON: {e}")
            return

    results = run_sweep(strategy, symbol, interval, days, grid, mode, n_random)

    if json_mode:
        print_result([r.model_dump(mode="json") for r in results], json_mode=True)
    else:
        rows = []
        for r in results:
            params_str = json.dumps(r.run_meta.strategy["params"]) if r.run_meta else "?"
            rows.append([
                params_str[:50],
                f"{r.total_return_pct:.2f}%",
                f"{r.max_drawdown_pct:.2f}%",
                str(r.total_trades),
                f"{r.win_rate:.1f}%",
                f"{r.stability_score:.1f}",
            ])
        print_table(
            headers=["Params", "Return", "MaxDD", "Trades", "WinRate", "Score"],
            rows=rows,
            title=f"Parameter Sweep: {strategy} on {symbol}",
            json_mode=False,
        )


def walkforward(
    strategy: str,
    symbol: str = "BTC/USDT",
    interval: str = "1h",
    days: int = 90,
    train_pct: float = 0.7,
    n_splits: int = 3,
    param_grid: Optional[str] = None,
    json_mode: bool = False,
) -> None:
    """Run walk-forward validation (delegates to walkforward module)."""
    from clawquant.core.backtest.walkforward import run_walkforward

    grid = {}
    if param_grid:
        try:
            grid = json.loads(param_grid)
        except json.JSONDecodeError as e:
            print_error("ConfigError", f"Invalid param_grid JSON: {e}")
            return

    results = run_walkforward(strategy, symbol, interval, days, train_pct, n_splits, grid)

    if json_mode:
        print_result(results, json_mode=True)
    else:
        print_result(results, json_mode=False)
