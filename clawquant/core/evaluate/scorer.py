"""Stability scorer: composite 0-100 score with 5-dimension breakdown."""

from __future__ import annotations

import math
from typing import Any, Dict, List


def compute_stability_score(metrics: Dict[str, float], trades: list) -> Dict[str, float]:
    """Compute a 0-100 stability score with 5-dimension breakdown.

    Dimensions:
        - quality (30%): Sharpe, Sortino, Calmar
        - risk (30%): Max drawdown, volatility
        - robustness (20%): Win rate, profit factor consistency
        - cost_sensitivity (10%): Fee impact relative to gross profit
        - overtrade (10%): Trade frequency reasonableness

    Returns:
        Dict with 'total', 'quality', 'risk', 'robustness', 'cost_sensitivity', 'overtrade'.
    """
    quality = _score_quality(metrics)
    risk = _score_risk(metrics)
    robustness = _score_robustness(metrics, trades)
    cost_sensitivity = _score_cost_sensitivity(metrics)
    overtrade = _score_overtrade(metrics)

    total = (
        quality * 0.30
        + risk * 0.30
        + robustness * 0.20
        + cost_sensitivity * 0.10
        + overtrade * 0.10
    )

    return {
        "total": round(total, 1),
        "quality": round(quality, 1),
        "risk": round(risk, 1),
        "robustness": round(robustness, 1),
        "cost_sensitivity": round(cost_sensitivity, 1),
        "overtrade": round(overtrade, 1),
    }


def _clamp(value: float, lo: float = 0, hi: float = 100) -> float:
    return max(lo, min(hi, value))


def _score_quality(m: Dict[str, float]) -> float:
    """Score based on risk-adjusted returns."""
    # Sharpe: 0 -> 0, 1 -> 50, 2 -> 80, 3+ -> 100
    sharpe = m.get("sharpe_ratio", 0)
    sharpe_score = _clamp(sharpe * 33.3)

    # Sortino: similar scaling
    sortino = m.get("sortino_ratio", 0)
    sortino_score = _clamp(sortino * 25)

    # Calmar: 0 -> 0, 1 -> 40, 3 -> 80, 5+ -> 100
    calmar = m.get("calmar_ratio", 0)
    calmar_score = _clamp(calmar * 20)

    return (sharpe_score * 0.4 + sortino_score * 0.3 + calmar_score * 0.3)


def _score_risk(m: Dict[str, float]) -> float:
    """Score based on risk metrics (lower is better)."""
    # Max DD: 0% -> 100, 5% -> 80, 10% -> 60, 20% -> 30, 50%+ -> 0
    max_dd_pct = m.get("max_drawdown_pct", 0)
    dd_score = _clamp(100 - max_dd_pct * 2)

    # Volatility: lower is better
    ann_vol = m.get("annualized_volatility", 0)
    vol_score = _clamp(100 - ann_vol * 0.5)

    return dd_score * 0.6 + vol_score * 0.4


def _score_robustness(m: Dict[str, float], trades: list) -> float:
    """Score based on consistency."""
    # Win rate: 30% -> 20, 50% -> 50, 60% -> 70, 70%+ -> 90
    win_rate = m.get("win_rate", 0)
    wr_score = _clamp(win_rate * 1.3)

    # Profit factor: 0 -> 0, 1 -> 30, 1.5 -> 60, 2 -> 80, 3+ -> 100
    pf = m.get("profit_factor", 0)
    if pf == float("inf"):
        pf_score = 100
    else:
        pf_score = _clamp(pf * 33.3)

    # Trade count: too few = unreliable
    n_trades = m.get("total_trades", 0)
    if n_trades < 5:
        count_penalty = 0.5
    elif n_trades < 10:
        count_penalty = 0.8
    else:
        count_penalty = 1.0

    return (wr_score * 0.4 + pf_score * 0.6) * count_penalty


def _score_cost_sensitivity(m: Dict[str, float]) -> float:
    """Score based on how much fees eat into profits."""
    gross_profit = m.get("gross_profit", 0)
    gross_loss = m.get("gross_loss", 0)
    total_return = m.get("total_return", 0)

    if gross_profit <= 0:
        return 50.0  # Neutral if no profits

    # Estimate fee impact (approximate from total return vs gross profit)
    if gross_profit > 0:
        net_efficiency = total_return / gross_profit if gross_profit > 0 else 0
        return _clamp(net_efficiency * 100)

    return 50.0


def _score_overtrade(m: Dict[str, float]) -> float:
    """Score based on trade frequency (penalize extreme overtrading)."""
    total_trades = m.get("total_trades", 0)
    avg_bars = m.get("avg_bars_held", 0)

    # Very short holding period = likely overtrading
    if avg_bars < 2:
        return 20.0
    elif avg_bars < 5:
        return 50.0
    elif avg_bars < 10:
        return 70.0
    elif avg_bars < 50:
        return 90.0
    else:
        return 100.0
