"""Deploy CLI command implementations."""

from __future__ import annotations

from typing import Optional

from clawquant.core.utils.output import print_error, print_result, print_table


def paper(
    strategy: str,
    symbol: str = "BTC/USDT",
    interval: str = "1h",
    capital: float = 10000.0,
    params: Optional[str] = None,
    exchange: str = "binance",
    json_mode: bool = False,
) -> None:
    """Start paper trading deployment."""
    import json as json_lib

    from clawquant.core.deploy.runner import DeployRunner

    strategy_params = {}
    if params:
        try:
            strategy_params = json_lib.loads(params)
        except Exception as e:
            print_error("ConfigError", f"Invalid params JSON: {e}")
            return

    runner = DeployRunner(
        strategy_name=strategy,
        symbol=symbol,
        interval=interval,
        mode="paper",
        capital=capital,
        params=strategy_params,
        exchange=exchange,
    )

    if not json_mode:
        from rich.console import Console
        console = Console()
        console.print(f"[bold green]Starting paper trading[/bold green]: {strategy} on {symbol} @ {interval}")
        console.print("Press Ctrl+C to stop")

    runner.start()


def live(
    strategy: str,
    symbol: str = "BTC/USDT",
    interval: str = "1h",
    capital: float = 10000.0,
    params: Optional[str] = None,
    exchange: str = "binance",
    confirm: bool = False,
    json_mode: bool = False,
) -> None:
    """Start live trading deployment (requires confirmation flag)."""
    if not confirm:
        print_error(
            "ConfigError",
            "Live trading requires --i-know-what-im-doing flag",
            "Add --i-know-what-im-doing to confirm you understand the risks of live trading",
        )
        return

    import json as json_lib
    from clawquant.core.deploy.runner import DeployRunner

    strategy_params = {}
    if params:
        try:
            strategy_params = json_lib.loads(params)
        except Exception as e:
            print_error("ConfigError", f"Invalid params JSON: {e}")
            return

    runner = DeployRunner(
        strategy_name=strategy,
        symbol=symbol,
        interval=interval,
        mode="live",
        capital=capital,
        params=strategy_params,
        exchange=exchange,
    )

    if not json_mode:
        from rich.console import Console
        console = Console()
        console.print(f"[bold red]Starting LIVE trading[/bold red]: {strategy} on {symbol} @ {interval}")
        console.print("[yellow]WARNING: Real orders will be placed![/yellow]")
        console.print("Press Ctrl+C to stop")

    runner.start()


def status(json_mode: bool = False) -> None:
    """Show all deployment statuses."""
    from clawquant.core.deploy.manager import list_deployments

    deployments = list_deployments()

    if not deployments:
        print_result({"message": "No active deployments"}, json_mode=json_mode)
        return

    if json_mode:
        print_result(deployments, json_mode=True)
    else:
        rows = []
        for d in deployments:
            rows.append([
                d.get("strategy", "?"),
                d.get("symbol", "?"),
                d.get("mode", "?"),
                d.get("status", "?"),
                f"${d.get('equity', 0):,.2f}" if d.get("equity") else "N/A",
                d.get("last_update", "N/A"),
            ])
        print_table(
            headers=["Strategy", "Symbol", "Mode", "Status", "Equity", "Last Update"],
            rows=rows,
            title="Deployments",
        )


def stop(
    strategy: str,
    symbol: str = "BTC/USDT",
    mode: str = "paper",
    json_mode: bool = False,
) -> None:
    """Stop a deployment."""
    from clawquant.core.deploy.manager import stop_deployment

    result = stop_deployment(strategy, symbol, mode)
    print_result(result, json_mode=json_mode)


def flatten(
    strategy: str,
    symbol: str = "BTC/USDT",
    mode: str = "paper",
    json_mode: bool = False,
) -> None:
    """Flatten positions and stop a deployment."""
    from clawquant.core.deploy.manager import flatten_deployment

    result = flatten_deployment(strategy, symbol, mode)
    print_result(result, json_mode=json_mode)
