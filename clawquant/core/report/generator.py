"""Report generation entry point."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from clawquant.core.evaluate.metrics import compute_metrics
from clawquant.core.evaluate.scorer import compute_stability_score
from clawquant.core.report.charts import generate_charts
from clawquant.core.report.json_report import generate_json_report
from clawquant.core.report.markdown_report import generate_markdown_report

logger = logging.getLogger(__name__)

RUNS_DIR = Path("runs")


def generate_report(
    run_id: str,
    formats: Optional[List[str]] = None,
    periods_per_year: int = 8760,
) -> Dict[str, Any]:
    """Generate reports for a completed backtest run.

    Args:
        run_id: The run ID to generate reports for.
        formats: List of formats to generate: "json", "md", "charts". Default: all.
        periods_per_year: Bars per year for annualization (8760 for 1h).

    Returns:
        Dict with 'success', 'files', 'metrics', 'score' keys.
    """
    if formats is None:
        formats = ["json", "md", "charts"]

    run_dir = RUNS_DIR / run_id
    if not run_dir.exists():
        return {"success": False, "error_type": "ConfigError", "message": f"Run directory not found: {run_dir}"}

    # Load run artifacts
    try:
        run_meta = _load_json(run_dir / "run_meta.json")
        trades_data = _load_json(run_dir / "trades.json")
        result_data = _load_json(run_dir / "result.json")
    except Exception as e:
        return {"success": False, "error_type": "DataError", "message": f"Failed to load run data: {e}"}

    # Load equity curve
    eq_path = run_dir / "equity_curve.csv"
    if eq_path.exists():
        eq_df = pd.read_csv(eq_path)
        equity_curve = eq_df.to_dict("records")
    else:
        equity_curve = result_data.get("equity_curve", [])

    # Compute metrics
    initial_capital = run_meta.get("config", {}).get("initial_capital", 10000)
    metrics = compute_metrics(equity_curve, trades_data, initial_capital, periods_per_year=periods_per_year)

    # Compute stability score
    score = compute_stability_score(metrics, trades_data)

    # Generate reports
    generated_files = []

    if "json" in formats:
        p = generate_json_report(run_dir, metrics, score, run_meta)
        generated_files.append(str(p))
        logger.info(f"JSON report: {p}")

    if "md" in formats:
        p = generate_markdown_report(run_dir, metrics, score, run_meta, trades_data)
        generated_files.append(str(p))
        logger.info(f"Markdown report: {p}")

    if "charts" in formats:
        chart_paths = generate_charts(run_dir, equity_curve, trades_data)
        for cp in chart_paths:
            generated_files.append(str(cp))
        logger.info(f"Charts: {len(chart_paths)} generated")

    # Cross-validate JSON and MD reports
    if "json" in formats and "md" in formats:
        _cross_validate(run_dir, metrics)

    return {
        "success": True,
        "run_id": run_id,
        "files": generated_files,
        "metrics": metrics,
        "score": score,
    }


def generate_batch_report(run_ids: List[str]) -> Dict[str, Any]:
    """Generate reports for multiple runs and create a summary."""
    results = []
    for run_id in run_ids:
        r = generate_report(run_id)
        results.append(r)

    # Create comparison summary
    summaries = []
    for r in results:
        if r.get("success"):
            m = r.get("metrics", {})
            s = r.get("score", {})
            summaries.append({
                "run_id": r["run_id"],
                "total_return_pct": m.get("total_return_pct", 0),
                "sharpe_ratio": m.get("sharpe_ratio", 0),
                "max_drawdown_pct": m.get("max_drawdown_pct", 0),
                "win_rate": m.get("win_rate", 0),
                "stability_score": s.get("total", 0),
            })

    # Sort by stability score
    summaries.sort(key=lambda x: x["stability_score"], reverse=True)

    return {
        "success": True,
        "count": len(results),
        "summaries": summaries,
        "details": results,
    }


def _load_json(path: Path) -> Any:
    """Load and parse a JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _cross_validate(run_dir: Path, metrics: Dict[str, float]) -> None:
    """Cross-validate key numbers between JSON report and metrics."""
    json_path = run_dir / "report.json"
    if not json_path.exists():
        return

    try:
        report = json.loads(json_path.read_text(encoding="utf-8"))
        report_metrics = report.get("metrics", {})

        for key in ["total_return", "sharpe_ratio", "max_drawdown_pct", "win_rate"]:
            expected = metrics.get(key, 0)
            actual = report_metrics.get(key, 0)
            if abs(expected - actual) > 0.01:
                logger.warning(f"Cross-validation mismatch: {key} expected={expected} actual={actual}")
    except Exception as e:
        logger.warning(f"Cross-validation failed: {e}")
