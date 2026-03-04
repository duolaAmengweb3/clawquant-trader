"""ClawQuant Trader - CLI entry point.

Usage:
    python -m clawquant.clawquant_cli --help
"""

from typing import Optional

import typer

from clawquant import __version__

# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------
app = typer.Typer(
    name="clawquant",
    help="ClawQuant Trader - Quantitative Research Infrastructure",
    add_completion=False,
    no_args_is_help=True,
)

# ---------------------------------------------------------------------------
# Global state (stored in shared module to survive python -m re-import)
# ---------------------------------------------------------------------------
from clawquant.core.utils.state import get_json_mode as _get_json_mode, set_json_mode


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"ClawQuant Trader v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None, "--version", "-V", help="Show version and exit.",
        callback=_version_callback, is_eager=True,
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Output results as JSON instead of Rich tables.",
    ),
) -> None:
    """ClawQuant Trader - Quantitative Research Infrastructure."""
    set_json_mode(json_output)


# ---------------------------------------------------------------------------
# Sub-app: data
# ---------------------------------------------------------------------------
data_app = typer.Typer(help="Data management commands", no_args_is_help=True)


@data_app.command("pull")
def data_pull(
    symbols: str = typer.Argument(..., help="Comma-separated symbols, e.g. BTC/USDT,ETH/USDT"),
    interval: str = typer.Option("1h", "--interval", "-i", help="Bar interval"),
    days: int = typer.Option(10, "--days", "-d", help="Number of days to fetch"),
    exchange: str = typer.Option("binance", "--exchange", "-e", help="Exchange name"),
) -> None:
    """Pull OHLCV data for one or more symbols."""
    from clawquant.cli.data_cli import pull
    pull(symbols=symbols, interval=interval, days=days, exchange=exchange, json_mode=_get_json_mode())


@data_app.command("inspect")
def data_inspect(
    symbol: str = typer.Argument(..., help="Symbol to check, e.g. BTC/USDT"),
    interval: str = typer.Option("1h", "--interval", "-i", help="Bar interval"),
) -> None:
    """Run data quality checks on a cached dataset."""
    from clawquant.cli.data_cli import inspect
    inspect(symbol=symbol, interval=interval, json_mode=_get_json_mode())


@data_app.command("cache-status")
def data_cache_status() -> None:
    """Show all cached data files."""
    from clawquant.cli.data_cli import cache_status
    cache_status(json_mode=_get_json_mode())


app.add_typer(data_app, name="data")

# ---------------------------------------------------------------------------
# Sub-app: strategy (delegated)
# ---------------------------------------------------------------------------
from clawquant.cli.strategy_cli import strategy_app  # noqa: E402

app.add_typer(strategy_app, name="strategy")

# ---------------------------------------------------------------------------
# Sub-app: backtest
# ---------------------------------------------------------------------------
backtest_app = typer.Typer(help="Backtesting commands", no_args_is_help=True)


@backtest_app.command("run")
def backtest_run(
    strategy: str = typer.Argument(..., help="Strategy name"),
    symbol: str = typer.Option("BTC/USDT", "--symbol", "-s", help="Trading pair"),
    interval: str = typer.Option("1h", "--interval", "-i", help="Bar interval"),
    days: int = typer.Option(30, "--days", "-d", help="Backtest window in days"),
    capital: float = typer.Option(10000.0, "--capital", "-c", help="Initial capital in USDT"),
    fee_bps: int = typer.Option(10, "--fee-bps", help="Fee in basis points"),
    slippage_bps: int = typer.Option(5, "--slippage-bps", help="Slippage in basis points"),
    params: Optional[str] = typer.Option(None, "--params", "-p", help='Strategy params JSON, e.g. \'{"fast_period": 10}\''),
    dry_run: bool = typer.Option(False, "--dry-run", help="Check readiness without running"),
) -> None:
    """Run a single backtest."""
    from clawquant.cli.backtest_cli import run
    run(strategy=strategy, symbol=symbol, interval=interval, days=days,
        capital=capital, fee_bps=fee_bps, slippage_bps=slippage_bps,
        params=params, dry_run=dry_run, json_mode=_get_json_mode())


@backtest_app.command("batch")
def backtest_batch(
    strategies: str = typer.Argument(..., help="Comma-separated strategy names"),
    symbols: str = typer.Option("BTC/USDT", "--symbols", "-s", help="Comma-separated symbols"),
    interval: str = typer.Option("1h", "--interval", "-i", help="Bar interval"),
    days: int = typer.Option(30, "--days", "-d", help="Backtest window in days"),
    capital: float = typer.Option(10000.0, "--capital", "-c", help="Initial capital"),
) -> None:
    """Run batch backtests across strategies and symbols."""
    from clawquant.cli.backtest_cli import batch
    batch(strategies=strategies, symbols=symbols, interval=interval, days=days,
          capital=capital, json_mode=_get_json_mode())


@backtest_app.command("sweep")
def backtest_sweep(
    strategy: str = typer.Argument(..., help="Strategy name"),
    symbol: str = typer.Option("BTC/USDT", "--symbol", "-s", help="Trading pair"),
    interval: str = typer.Option("1h", "--interval", "-i", help="Bar interval"),
    days: int = typer.Option(30, "--days", "-d", help="Backtest window"),
    param_grid: Optional[str] = typer.Option(None, "--grid", "-g", help='Param grid JSON, e.g. \'{"fast_period": [5,10,20]}\''),
    mode: str = typer.Option("grid", "--mode", "-m", help="Sweep mode: grid or random"),
    n_random: int = typer.Option(20, "--n-random", help="Number of random samples"),
) -> None:
    """Run parameter sweep over a strategy."""
    from clawquant.cli.backtest_cli import sweep
    sweep(strategy=strategy, symbol=symbol, interval=interval, days=days,
          param_grid=param_grid, mode=mode, n_random=n_random, json_mode=_get_json_mode())


@backtest_app.command("walkforward")
def backtest_walkforward(
    strategy: str = typer.Argument(..., help="Strategy name"),
    symbol: str = typer.Option("BTC/USDT", "--symbol", "-s", help="Trading pair"),
    interval: str = typer.Option("1h", "--interval", "-i", help="Bar interval"),
    days: int = typer.Option(90, "--days", "-d", help="Total data window"),
    train_pct: float = typer.Option(0.7, "--train-pct", help="Training fraction"),
    n_splits: int = typer.Option(3, "--splits", "-n", help="Number of rolling splits"),
    param_grid: Optional[str] = typer.Option(None, "--grid", "-g", help="Param grid JSON"),
) -> None:
    """Run walk-forward validation."""
    from clawquant.cli.backtest_cli import walkforward
    walkforward(strategy=strategy, symbol=symbol, interval=interval, days=days,
                train_pct=train_pct, n_splits=n_splits, param_grid=param_grid,
                json_mode=_get_json_mode())


app.add_typer(backtest_app, name="backtest")

# ---------------------------------------------------------------------------
# Sub-app: radar
# ---------------------------------------------------------------------------
radar_app = typer.Typer(help="Opportunity scanning commands", no_args_is_help=True)


@radar_app.command("scan")
def radar_scan(
    symbols: str = typer.Option("BTC/USDT,ETH/USDT", "--symbols", "-s", help="Comma-separated symbols"),
    strategies: str = typer.Option("ma_crossover,dca", "--strategies", help="Comma-separated strategies"),
    interval: str = typer.Option("1h", "--interval", "-i", help="Bar interval"),
    days: int = typer.Option(10, "--days", "-d", help="Data window"),
    exchange: str = typer.Option("binance", "--exchange", "-e", help="Exchange"),
    top_n: int = typer.Option(10, "--top", "-n", help="Top N results"),
) -> None:
    """Scan for trading opportunities."""
    from clawquant.cli.radar_cli import scan
    scan(symbols=symbols, strategies=strategies, interval=interval, days=days,
         exchange=exchange, top_n=top_n, json_mode=_get_json_mode())


@radar_app.command("explain")
def radar_explain(
    symbol: str = typer.Argument(..., help="Symbol to explain"),
    strategy: str = typer.Argument(..., help="Strategy name"),
    interval: str = typer.Option("1h", "--interval", "-i", help="Bar interval"),
    days: int = typer.Option(10, "--days", "-d", help="Data window"),
) -> None:
    """Explain a specific opportunity."""
    from clawquant.cli.radar_cli import explain
    explain(symbol=symbol, strategy=strategy, interval=interval, days=days,
            json_mode=_get_json_mode())


app.add_typer(radar_app, name="radar")

# ---------------------------------------------------------------------------
# Sub-app: report
# ---------------------------------------------------------------------------
report_app = typer.Typer(help="Report generation commands", no_args_is_help=True)


@report_app.command("generate")
def report_generate(
    run_id: str = typer.Argument(..., help="Run ID to generate report for"),
    formats: Optional[str] = typer.Option(None, "--formats", "-f", help="Comma-separated: json,md,charts"),
) -> None:
    """Generate reports for a backtest run."""
    from clawquant.cli.report_cli import generate
    generate(run_id=run_id, formats=formats, json_mode=_get_json_mode())


@report_app.command("batch")
def report_batch(
    run_ids: str = typer.Argument(..., help="Comma-separated run IDs"),
) -> None:
    """Generate and compare reports for multiple runs."""
    from clawquant.cli.report_cli import batch_generate
    batch_generate(run_ids=run_ids, json_mode=_get_json_mode())


app.add_typer(report_app, name="report")

# ---------------------------------------------------------------------------
# Sub-app: deploy
# ---------------------------------------------------------------------------
deploy_app = typer.Typer(help="Deployment commands", no_args_is_help=True)


@deploy_app.command("paper")
def deploy_paper(
    strategy: str = typer.Argument(..., help="Strategy name"),
    symbol: str = typer.Option("BTC/USDT", "--symbol", "-s", help="Trading pair"),
    interval: str = typer.Option("1h", "--interval", "-i", help="Bar interval"),
    capital: float = typer.Option(10000.0, "--capital", "-c", help="Initial capital"),
    params: Optional[str] = typer.Option(None, "--params", "-p", help="Strategy params JSON"),
    exchange: str = typer.Option("binance", "--exchange", "-e", help="Exchange"),
) -> None:
    """Start paper trading."""
    from clawquant.cli.deploy_cli import paper
    paper(strategy=strategy, symbol=symbol, interval=interval, capital=capital,
          params=params, exchange=exchange, json_mode=_get_json_mode())


@deploy_app.command("live")
def deploy_live(
    strategy: str = typer.Argument(..., help="Strategy name"),
    symbol: str = typer.Option("BTC/USDT", "--symbol", "-s", help="Trading pair"),
    interval: str = typer.Option("1h", "--interval", "-i", help="Bar interval"),
    capital: float = typer.Option(10000.0, "--capital", "-c", help="Initial capital"),
    params: Optional[str] = typer.Option(None, "--params", "-p", help="Strategy params JSON"),
    exchange: str = typer.Option("binance", "--exchange", "-e", help="Exchange"),
    i_know_what_im_doing: bool = typer.Option(False, "--i-know-what-im-doing", help="Confirm live trading risks"),
) -> None:
    """Start live trading (requires --i-know-what-im-doing)."""
    from clawquant.cli.deploy_cli import live
    live(strategy=strategy, symbol=symbol, interval=interval, capital=capital,
         params=params, exchange=exchange, confirm=i_know_what_im_doing,
         json_mode=_get_json_mode())


@deploy_app.command("status")
def deploy_status() -> None:
    """Show deployment statuses."""
    from clawquant.cli.deploy_cli import status
    status(json_mode=_get_json_mode())


@deploy_app.command("stop")
def deploy_stop(
    strategy: str = typer.Argument(..., help="Strategy name"),
    symbol: str = typer.Option("BTC/USDT", "--symbol", "-s", help="Trading pair"),
    mode: str = typer.Option("paper", "--mode", "-m", help="paper or live"),
) -> None:
    """Stop a deployment."""
    from clawquant.cli.deploy_cli import stop
    stop(strategy=strategy, symbol=symbol, mode=mode, json_mode=_get_json_mode())


@deploy_app.command("flatten")
def deploy_flatten(
    strategy: str = typer.Argument(..., help="Strategy name"),
    symbol: str = typer.Option("BTC/USDT", "--symbol", "-s", help="Trading pair"),
    mode: str = typer.Option("paper", "--mode", "-m", help="paper or live"),
) -> None:
    """Flatten positions and stop a deployment."""
    from clawquant.cli.deploy_cli import flatten
    flatten(strategy=strategy, symbol=symbol, mode=mode, json_mode=_get_json_mode())


app.add_typer(deploy_app, name="deploy")

# ---------------------------------------------------------------------------
# Module entry-point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app()
