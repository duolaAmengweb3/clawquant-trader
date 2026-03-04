"""Report CLI command implementations."""

from __future__ import annotations

from typing import List, Optional

from clawquant.core.utils.output import print_error, print_result, print_table


def generate(
    run_id: str,
    formats: Optional[str] = None,
    json_mode: bool = False,
) -> None:
    """Generate reports for a backtest run."""
    from clawquant.core.report.generator import generate_report

    fmt_list = None
    if formats:
        fmt_list = [f.strip() for f in formats.split(",")]

    result = generate_report(run_id, formats=fmt_list)

    if not result.get("success"):
        print_error(
            result.get("error_type", "Error"),
            result.get("message", "Unknown error"),
        )
        return

    if json_mode:
        print_result(result, json_mode=True)
    else:
        print_table(
            headers=["Metric", "Value"],
            rows=[
                ["Run ID", result["run_id"]],
                ["Total Return", f"{result['metrics'].get('total_return_pct', 0):.2f}%"],
                ["Sharpe Ratio", f"{result['metrics'].get('sharpe_ratio', 0):.4f}"],
                ["Max Drawdown", f"{result['metrics'].get('max_drawdown_pct', 0):.2f}%"],
                ["Win Rate", f"{result['metrics'].get('win_rate', 0):.2f}%"],
                ["Stability Score", f"{result['score'].get('total', 0):.1f}/100"],
                ["Files Generated", str(len(result.get('files', [])))],
            ],
            title=f"Report: {run_id}",
        )
        from rich.console import Console
        console = Console()
        for f in result.get("files", []):
            console.print(f"  [green]✓[/green] {f}")


def batch_generate(
    run_ids: str,
    json_mode: bool = False,
) -> None:
    """Generate reports for multiple runs."""
    from clawquant.core.report.generator import generate_batch_report

    ids = [r.strip() for r in run_ids.split(",")]
    result = generate_batch_report(ids)

    if json_mode:
        print_result(result, json_mode=True)
    else:
        rows = []
        for s in result.get("summaries", []):
            rows.append([
                s["run_id"][:40],
                f"{s['total_return_pct']:.2f}%",
                f"{s['sharpe_ratio']:.4f}",
                f"{s['max_drawdown_pct']:.2f}%",
                f"{s['win_rate']:.2f}%",
                f"{s['stability_score']:.1f}",
            ])
        print_table(
            headers=["Run ID", "Return", "Sharpe", "MaxDD", "WinRate", "Score"],
            rows=rows,
            title="Batch Report Summary",
        )
