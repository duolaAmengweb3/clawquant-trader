"""JSON report generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def generate_json_report(
    run_dir: Path,
    metrics: Dict[str, float],
    score: Dict[str, float],
    run_meta: dict,
) -> Path:
    """Generate a comprehensive JSON report.

    Args:
        run_dir: Directory to write the report to.
        metrics: Performance metrics dict.
        score: Stability score breakdown.
        run_meta: Run metadata dict.

    Returns:
        Path to the generated JSON report.
    """
    report = {
        "run_id": run_meta.get("run_id", "unknown"),
        "timestamp": run_meta.get("timestamp", ""),
        "strategy": run_meta.get("strategy", {}),
        "data": run_meta.get("data", {}),
        "config": run_meta.get("config", {}),
        "metrics": metrics,
        "stability_score": score,
        "environment": run_meta.get("environment", {}),
    }

    report_path = run_dir / "report.json"
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return report_path
