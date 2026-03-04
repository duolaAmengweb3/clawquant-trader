"""Binance Skill adapter: wraps Binance-specific API calls for the skill layer."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BinanceSkillWrapper:
    """Adapter between ClawQuant skills and Binance exchange.

    Provides a simplified interface for skills to interact with Binance
    without directly using ccxt. Falls back to ccxt_fallback client internally.
    """

    def __init__(self, api_key: Optional[str] = None, secret: Optional[str] = None):
        from clawquant.integrations.ccxt_fallback.client import CcxtClient
        self._client = CcxtClient(exchange_id="binance", api_key=api_key, secret=secret)

    def get_ohlcv(
        self,
        symbol: str,
        interval: str = "1h",
        days: int = 10,
    ) -> List[Dict[str, Any]]:
        """Fetch OHLCV bars via the ccxt fallback client."""
        from datetime import datetime, timedelta, timezone
        since_ms = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)
        raw = self._client.fetch_ohlcv(symbol, interval, since=since_ms)
        bars = []
        for row in raw:
            bars.append({
                "timestamp": row[0],
                "open": row[1],
                "high": row[2],
                "low": row[3],
                "close": row[4],
                "volume": row[5],
            })
        return bars

    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """Get current ticker info."""
        try:
            ticker = self._client._exchange.fetch_ticker(symbol)
            return {
                "symbol": symbol,
                "last": ticker.get("last"),
                "bid": ticker.get("bid"),
                "ask": ticker.get("ask"),
                "volume_24h": ticker.get("quoteVolume"),
                "change_24h_pct": ticker.get("percentage"),
            }
        except Exception as e:
            logger.error(f"Failed to get ticker for {symbol}: {e}")
            return {"symbol": symbol, "error": str(e)}

    def get_top_symbols(self, quote: str = "USDT", top_n: int = 20) -> List[str]:
        """Get top N symbols by volume."""
        try:
            self._client._exchange.load_markets()
            markets = self._client._exchange.markets
            usdt_markets = [
                (sym, m)
                for sym, m in markets.items()
                if m.get("quote") == quote and m.get("active", True)
            ]
            # Sort by volume is not available without tickers, return alphabetically
            symbols = sorted([sym for sym, _ in usdt_markets])[:top_n]
            return symbols
        except Exception as e:
            logger.error(f"Failed to get top symbols: {e}")
            return []
