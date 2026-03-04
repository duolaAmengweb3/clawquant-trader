"""Chart generation using matplotlib."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd


def generate_charts(run_dir: Path, equity_curve: List[Dict[str, Any]], trades: List[dict]) -> List[Path]:
    """Generate all charts for a backtest run.

    Returns list of generated chart paths.
    """
    paths = []

    if not equity_curve:
        return paths

    eq_df = pd.DataFrame(equity_curve)
    eq_df["timestamp"] = pd.to_datetime(eq_df["timestamp"])

    # 1. Equity curve
    p = _plot_equity(run_dir, eq_df)
    if p:
        paths.append(p)

    # 2. Drawdown
    p = _plot_drawdown(run_dir, eq_df)
    if p:
        paths.append(p)

    # 3. Trades
    if trades:
        p = _plot_trades(run_dir, eq_df, trades)
        if p:
            paths.append(p)

    return paths


def _plot_equity(run_dir: Path, eq_df: pd.DataFrame) -> Path:
    """Plot equity curve."""
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(eq_df["timestamp"], eq_df["total_value"], linewidth=1.5, color="#2196F3", label="Equity")
    ax.fill_between(eq_df["timestamp"], eq_df["total_value"], alpha=0.1, color="#2196F3")

    initial = eq_df["total_value"].iloc[0]
    ax.axhline(y=initial, color="gray", linestyle="--", alpha=0.5, label=f"Initial: ${initial:,.0f}")

    ax.set_title("Equity Curve", fontsize=14, fontweight="bold")
    ax.set_xlabel("Time")
    ax.set_ylabel("Portfolio Value (USDT)")
    ax.legend(loc="upper left")
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    fig.autofmt_xdate()
    fig.tight_layout()

    path = run_dir / "equity.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def _plot_drawdown(run_dir: Path, eq_df: pd.DataFrame) -> Path:
    """Plot drawdown chart."""
    values = eq_df["total_value"].values
    peak = np.maximum.accumulate(values)
    drawdown_pct = (peak - values) / peak * 100

    fig, ax = plt.subplots(figsize=(12, 4))
    ax.fill_between(eq_df["timestamp"], 0, -drawdown_pct, color="#F44336", alpha=0.4)
    ax.plot(eq_df["timestamp"], -drawdown_pct, linewidth=1, color="#F44336")

    max_dd = np.max(drawdown_pct)
    ax.axhline(y=-max_dd, color="red", linestyle="--", alpha=0.5, label=f"Max DD: {max_dd:.1f}%")

    ax.set_title("Drawdown", fontsize=14, fontweight="bold")
    ax.set_xlabel("Time")
    ax.set_ylabel("Drawdown (%)")
    ax.legend(loc="lower left")
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    fig.autofmt_xdate()
    fig.tight_layout()

    path = run_dir / "drawdown.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def _plot_trades(run_dir: Path, eq_df: pd.DataFrame, trades: List[dict]) -> Path:
    """Plot trade entries and exits on price chart."""
    fig, ax = plt.subplots(figsize=(12, 5))

    # Price line
    ax.plot(eq_df["timestamp"], eq_df["price"], linewidth=1, color="gray", alpha=0.7, label="Price")

    # Trade markers
    for t in trades:
        entry_time = pd.to_datetime(t.get("entry_time"))
        exit_time = pd.to_datetime(t.get("exit_time")) if t.get("exit_time") else None
        entry_price = t.get("entry_price", 0)
        exit_price = t.get("exit_price", 0)
        pnl = t.get("pnl", 0)

        color = "#4CAF50" if pnl >= 0 else "#F44336"

        ax.scatter(entry_time, entry_price, marker="^", color=color, s=60, zorder=5)
        if exit_time and exit_price:
            ax.scatter(exit_time, exit_price, marker="v", color=color, s=60, zorder=5)
            ax.plot([entry_time, exit_time], [entry_price, exit_price], color=color, alpha=0.3, linewidth=0.8)

    ax.set_title("Trades", fontsize=14, fontweight="bold")
    ax.set_xlabel("Time")
    ax.set_ylabel("Price (USDT)")
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    fig.autofmt_xdate()
    fig.tight_layout()

    path = run_dir / "trades.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path
