"""Radar scanner: detect trading opportunities across multiple symbols."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


def scan_opportunities(
    symbols: List[str],
    strategies: List[str],
    interval: str = "1h",
    days: int = 10,
    exchange: str = "binance",
    top_n: int = 10,
) -> List[Dict[str, Any]]:
    """Scan for current trading opportunities.

    For each symbol x strategy combination:
    1. Pull recent data
    2. Compute indicators and signals
    3. Check if there's a fresh signal (last N bars)
    4. Score the opportunity by historical backtest

    Args:
        symbols: List of symbols to scan.
        strategies: List of strategy names to apply.
        interval: Bar interval.
        days: Data window.
        exchange: Exchange to pull from.
        top_n: Return top N opportunities.

    Returns:
        Sorted list of opportunity dicts.
    """
    from clawquant.core.data.fetcher import fetch_data
    from clawquant.core.data.models import DataPullRequest
    from clawquant.core.runtime.loader import load_strategy

    opportunities = []

    # Fetch data for all symbols at once
    try:
        request = DataPullRequest(symbols=symbols, interval=interval, days=days, exchange=exchange)
        dfs = fetch_data(request)
    except Exception as e:
        logger.error(f"Failed to fetch data: {e}")
        return []

    for strategy_name in strategies:
        try:
            strat = load_strategy(strategy_name)
            meta = strat.metadata()
            # Get default params
            params = {}
            for k, v in meta.params_schema.get("properties", {}).items():
                if "default" in v:
                    params[k] = v["default"]
        except Exception as e:
            logger.warning(f"Failed to load strategy {strategy_name}: {e}")
            continue

        for symbol in symbols:
            df = dfs.get(symbol)
            if df is None or df.empty:
                continue

            try:
                # Compute indicators and signals
                df_ind = strat.compute_indicators(df.copy(), params)
                signals = strat.generate_signals(df_ind, params)

                # Check last 3 bars for fresh signals
                recent_signals = signals.iloc[-3:]
                last_signal = int(signals.iloc[-1])
                has_fresh_signal = any(s != 0 for s in recent_signals)

                if not has_fresh_signal:
                    continue

                # Signal direction
                direction = "BUY" if last_signal == 1 else "SELL" if last_signal == -1 else "HOLD"
                if direction == "HOLD":
                    # Check if any of last 3 bars had a signal
                    for s in reversed(recent_signals.values):
                        if s != 0:
                            direction = "BUY" if s == 1 else "SELL"
                            break

                # Compute signal statistics
                total_signals = (signals != 0).sum()
                buy_signals = (signals == 1).sum()
                sell_signals = (signals == -1).sum()
                signal_rate = total_signals / len(signals) * 100 if len(signals) > 0 else 0

                # Price context
                last_price = float(df.iloc[-1]["close"])
                price_change_24h = 0.0
                if len(df) >= 24:
                    price_24h_ago = float(df.iloc[-24]["close"])
                    price_change_24h = (last_price / price_24h_ago - 1) * 100

                # Quick historical signal success rate
                win_count = 0
                total_count = 0
                for j in range(len(signals) - 1):
                    sig = int(signals.iloc[j])
                    if sig == 1 and j + 5 < len(df):
                        future_price = float(df.iloc[j + 5]["close"])
                        current_price = float(df.iloc[j]["close"])
                        if future_price > current_price:
                            win_count += 1
                        total_count += 1
                    elif sig == -1 and j + 5 < len(df):
                        future_price = float(df.iloc[j + 5]["close"])
                        current_price = float(df.iloc[j]["close"])
                        if future_price < current_price:
                            win_count += 1
                        total_count += 1

                historical_accuracy = (win_count / total_count * 100) if total_count > 0 else 0

                # Confidence score (simple heuristic)
                confidence = min(100, historical_accuracy * 0.5 + (100 - signal_rate) * 0.3 + min(total_count, 20) * 1.0)

                opportunities.append({
                    "symbol": symbol,
                    "strategy": strategy_name,
                    "direction": direction,
                    "confidence": round(confidence, 1),
                    "last_price": last_price,
                    "price_change_24h": round(price_change_24h, 2),
                    "signal_rate": round(signal_rate, 1),
                    "historical_accuracy": round(historical_accuracy, 1),
                    "total_signals": int(total_signals),
                    "buy_signals": int(buy_signals),
                    "sell_signals": int(sell_signals),
                })

            except Exception as e:
                logger.warning(f"Error scanning {symbol} with {strategy_name}: {e}")
                continue

    # Sort by confidence
    opportunities.sort(key=lambda x: x["confidence"], reverse=True)
    return opportunities[:top_n]
