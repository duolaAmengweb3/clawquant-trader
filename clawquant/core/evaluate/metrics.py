"""Performance metrics: Sharpe, Sortino, Calmar, MaxDD, etc."""

from __future__ import annotations

import math
from typing import Any, Dict, List

import numpy as np
import pandas as pd


def compute_metrics(
    equity_curve: List[Dict[str, Any]],
    trades: list,
    initial_capital: float,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 8760,  # hourly bars
) -> Dict[str, float]:
    """Compute all performance metrics from equity curve and trades.

    Args:
        equity_curve: List of dicts with at least 'total_value' and 'timestamp'.
        trades: List of Trade objects (or dicts with 'pnl', 'bars_held', 'pnl_pct').
        initial_capital: Starting capital.
        risk_free_rate: Annual risk-free rate (decimal).
        periods_per_year: Number of bars per year for annualization.

    Returns:
        Dict of metric name -> value.
    """
    if not equity_curve:
        return _empty_metrics()

    values = [e["total_value"] for e in equity_curve]
    values_arr = np.array(values, dtype=float)

    # Returns series
    returns = np.diff(values_arr) / values_arr[:-1]
    returns = returns[np.isfinite(returns)]

    # Total return
    final_value = values_arr[-1]
    total_return = final_value - initial_capital
    total_return_pct = (total_return / initial_capital) * 100 if initial_capital > 0 else 0

    # Annualized return
    n_periods = len(values_arr)
    years = n_periods / periods_per_year if periods_per_year > 0 else 1
    ann_return = ((final_value / initial_capital) ** (1 / years) - 1) if years > 0 and initial_capital > 0 else 0

    # Volatility
    if len(returns) > 1:
        vol = float(np.std(returns, ddof=1))
        ann_vol = vol * math.sqrt(periods_per_year)
    else:
        vol = 0.0
        ann_vol = 0.0

    # Sharpe ratio
    if ann_vol > 0:
        sharpe = (ann_return - risk_free_rate) / ann_vol
    else:
        sharpe = 0.0

    # Sortino ratio (downside deviation)
    downside = returns[returns < 0]
    if len(downside) > 1:
        downside_vol = float(np.std(downside, ddof=1)) * math.sqrt(periods_per_year)
        sortino = (ann_return - risk_free_rate) / downside_vol if downside_vol > 0 else 0.0
    else:
        sortino = 0.0

    # Max drawdown
    peak = np.maximum.accumulate(values_arr)
    drawdown = (peak - values_arr)
    drawdown_pct = drawdown / peak
    max_dd = float(np.max(drawdown)) if len(drawdown) > 0 else 0.0
    max_dd_pct = float(np.max(drawdown_pct)) if len(drawdown_pct) > 0 else 0.0

    # Calmar ratio
    calmar = ann_return / max_dd_pct if max_dd_pct > 0 else 0.0

    # Trade stats
    trade_pnls = []
    trade_bars = []
    for t in trades:
        pnl = t.pnl if hasattr(t, "pnl") else t.get("pnl", 0)
        bars = t.bars_held if hasattr(t, "bars_held") else t.get("bars_held", 0)
        trade_pnls.append(pnl)
        trade_bars.append(bars)

    total_trades = len(trade_pnls)
    winning = [p for p in trade_pnls if p > 0]
    losing = [p for p in trade_pnls if p < 0]
    win_rate = len(winning) / total_trades * 100 if total_trades > 0 else 0

    gross_profit = sum(winning)
    gross_loss = abs(sum(losing))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0)

    avg_trade_pnl = sum(trade_pnls) / total_trades if total_trades > 0 else 0
    avg_win = sum(winning) / len(winning) if winning else 0
    avg_loss = sum(losing) / len(losing) if losing else 0
    avg_bars_held = sum(trade_bars) / total_trades if total_trades > 0 else 0

    # Expectancy
    expectancy = (win_rate / 100 * avg_win + (1 - win_rate / 100) * avg_loss) if total_trades > 0 else 0

    return {
        "total_return": round(total_return, 2),
        "total_return_pct": round(total_return_pct, 2),
        "annualized_return": round(ann_return * 100, 2),
        "annualized_volatility": round(ann_vol * 100, 2),
        "sharpe_ratio": round(sharpe, 4),
        "sortino_ratio": round(sortino, 4),
        "calmar_ratio": round(calmar, 4),
        "max_drawdown": round(max_dd, 2),
        "max_drawdown_pct": round(max_dd_pct * 100, 2),
        "win_rate": round(win_rate, 2),
        "profit_factor": round(profit_factor, 4),
        "total_trades": total_trades,
        "avg_trade_pnl": round(avg_trade_pnl, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "avg_bars_held": round(avg_bars_held, 1),
        "expectancy": round(expectancy, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
    }


def _empty_metrics() -> Dict[str, float]:
    """Return a metrics dict with all zeros."""
    return {
        "total_return": 0.0,
        "total_return_pct": 0.0,
        "annualized_return": 0.0,
        "annualized_volatility": 0.0,
        "sharpe_ratio": 0.0,
        "sortino_ratio": 0.0,
        "calmar_ratio": 0.0,
        "max_drawdown": 0.0,
        "max_drawdown_pct": 0.0,
        "win_rate": 0.0,
        "profit_factor": 0.0,
        "total_trades": 0,
        "avg_trade_pnl": 0.0,
        "avg_win": 0.0,
        "avg_loss": 0.0,
        "avg_bars_held": 0.0,
        "expectancy": 0.0,
        "gross_profit": 0.0,
        "gross_loss": 0.0,
    }
