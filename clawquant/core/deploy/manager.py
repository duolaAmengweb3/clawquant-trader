"""Deployment manager: status, stop, flatten operations."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

RUNS_DIR = Path("runs")


def list_deployments() -> List[Dict[str, Any]]:
    """List all deployment state files."""
    deployments = []
    if not RUNS_DIR.exists():
        return deployments

    for f in RUNS_DIR.glob("deploy_*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            deployments.append(data)
        except Exception:
            continue

    return deployments


def get_deployment_status(strategy_name: str, symbol: str, mode: str = "paper") -> Dict[str, Any]:
    """Get status of a specific deployment."""
    state_file = RUNS_DIR / f"deploy_{strategy_name}_{symbol.replace('/', '_')}_{mode}.json"
    if not state_file.exists():
        return {"status": "not_found", "message": f"No deployment found for {strategy_name} on {symbol} ({mode})"}

    try:
        return json.loads(state_file.read_text(encoding="utf-8"))
    except Exception as e:
        return {"status": "error", "message": str(e)}


def stop_deployment(strategy_name: str, symbol: str, mode: str = "paper") -> Dict[str, Any]:
    """Mark a deployment as stopped."""
    state_file = RUNS_DIR / f"deploy_{strategy_name}_{symbol.replace('/', '_')}_{mode}.json"
    if not state_file.exists():
        return {"success": False, "message": "Deployment not found"}

    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
        data["status"] = "stopped"
        state_file.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        return {"success": True, "message": f"Deployment stopped: {strategy_name} on {symbol}"}
    except Exception as e:
        return {"success": False, "message": str(e)}


def flatten_deployment(strategy_name: str, symbol: str, mode: str = "paper") -> Dict[str, Any]:
    """Flatten all positions and stop a deployment."""
    state_file = RUNS_DIR / f"deploy_{strategy_name}_{symbol.replace('/', '_')}_{mode}.json"
    if not state_file.exists():
        return {"success": False, "message": "Deployment not found"}

    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
        data["status"] = "flattened"
        data["position_qty"] = 0
        state_file.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        logger.info(f"Flattened deployment: {strategy_name} on {symbol}")
        return {"success": True, "message": f"Positions flattened and deployment stopped: {strategy_name} on {symbol}"}
    except Exception as e:
        return {"success": False, "message": str(e)}
