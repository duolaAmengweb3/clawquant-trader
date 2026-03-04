"""Radar CLI command implementations."""

from __future__ import annotations

from typing import Optional

from clawquant.core.utils.output import print_error, print_result, print_table


def scan(
    symbols: str = "BTC/USDT,ETH/USDT",
    strategies: str = "ma_crossover,dca",
    interval: str = "1h",
    days: int = 10,
    exchange: str = "binance",
    top_n: int = 10,
    json_mode: bool = False,
) -> None:
    """Scan for trading opportunities."""
    from clawquant.core.radar.scanner import scan_opportunities

    symbol_list = [s.strip() for s in symbols.split(",")]
    strategy_list = [s.strip() for s in strategies.split(",")]

    results = scan_opportunities(
        symbols=symbol_list,
        strategies=strategy_list,
        interval=interval,
        days=days,
        exchange=exchange,
        top_n=top_n,
    )

    if not results:
        print_result({"message": "No opportunities found"}, json_mode=json_mode)
        return

    if json_mode:
        print_result(results, json_mode=True)
    else:
        rows = []
        for r in results:
            rows.append([
                r["symbol"],
                r["strategy"],
                r["direction"],
                f"{r['confidence']:.0f}%",
                f"${r['last_price']:,.2f}",
                f"{r['price_change_24h']:+.2f}%",
                f"{r['historical_accuracy']:.0f}%",
            ])
        print_table(
            headers=["Symbol", "Strategy", "Signal", "Confidence", "Price", "24h Chg", "Accuracy"],
            rows=rows,
            title="Radar Scan Results",
        )


def explain(
    symbol: str,
    strategy: str,
    interval: str = "1h",
    days: int = 10,
    exchange: str = "binance",
    json_mode: bool = False,
) -> None:
    """Explain a specific opportunity."""
    from clawquant.core.radar.explainer import explain_opportunity
    from clawquant.core.radar.scanner import scan_opportunities

    results = scan_opportunities(
        symbols=[symbol],
        strategies=[strategy],
        interval=interval,
        days=days,
        exchange=exchange,
        top_n=1,
    )

    if not results:
        print_error("DataError", f"No signal found for {symbol} with {strategy}")
        return

    explanation = explain_opportunity(results[0])

    if json_mode:
        print_result(explanation, json_mode=True)
    else:
        from rich.console import Console
        from rich.panel import Panel
        console = Console()
        console.print(Panel(explanation["summary"], title="Opportunity", border_style="blue"))
        console.print("\n[bold]Reasons:[/bold]")
        for r in explanation["reasons"]:
            console.print(f"  • {r}")
        console.print("\n[bold]Risk Notes:[/bold]")
        for r in explanation["risk_notes"]:
            console.print(f"  ⚠ {r}")
