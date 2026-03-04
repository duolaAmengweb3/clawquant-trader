"""CCXT exchange client wrapper with retry logic and rate limiting."""

from __future__ import annotations

import logging
import os
import time
from typing import List, Optional

import ccxt

logger = logging.getLogger(__name__)


class ExchangeError(Exception):
    """Raised when an exchange operation fails after all retries."""


class CcxtClient:
    """Thin wrapper around a *ccxt* exchange instance.

    Provides:
    - Automatic API-key loading from environment variables.
    - Retry with exponential back-off (3 attempts by default).
    - Rate-limit-friendly sleep between paginated requests.
    """

    MAX_RETRIES: int = 3
    BACKOFF_BASE: float = 1.0  # seconds; doubles each retry
    RATE_LIMIT_SLEEP: float = 0.5  # seconds between paginated calls

    def __init__(
        self,
        exchange_id: str = "binance",
        api_key: Optional[str] = None,
        secret: Optional[str] = None,
    ) -> None:
        self.exchange_id = exchange_id
        api_key = api_key or os.getenv("CCXT_API_KEY", "")
        secret = secret or os.getenv("CCXT_SECRET", "")

        exchange_class = getattr(ccxt, exchange_id, None)
        if exchange_class is None:
            raise ExchangeError(f"Unknown exchange: {exchange_id}")

        config: dict = {"enableRateLimit": True}
        if api_key:
            config["apiKey"] = api_key
        if secret:
            config["secret"] = secret

        # Proxy support: reads from HTTPS_PROXY / HTTP_PROXY / CCXT_PROXY
        proxy = os.getenv("CCXT_PROXY") or os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY") or os.getenv("https_proxy") or os.getenv("http_proxy")
        if proxy:
            config["proxies"] = {"http": proxy, "https": proxy}
            logger.info("Using proxy: %s", proxy)

        self.exchange: ccxt.Exchange = exchange_class(config)
        logger.info("CcxtClient initialised for %s", exchange_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _retry(self, fn, *args, **kwargs):
        """Call *fn* with retry + exponential back-off."""
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                return fn(*args, **kwargs)
            except (
                ccxt.NetworkError,
                ccxt.ExchangeNotAvailable,
                ccxt.RequestTimeout,
                ccxt.DDoSProtection,
            ) as exc:
                last_exc = exc
                wait = self.BACKOFF_BASE * (2 ** (attempt - 1))
                logger.warning(
                    "Attempt %d/%d failed (%s). Retrying in %.1fs ...",
                    attempt,
                    self.MAX_RETRIES,
                    exc,
                    wait,
                )
                time.sleep(wait)
            except ccxt.BaseError as exc:
                raise ExchangeError(str(exc)) from exc

        raise ExchangeError(
            f"Failed after {self.MAX_RETRIES} retries: {last_exc}"
        ) from last_exc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        since: Optional[int] = None,
        limit: int = 1000,
    ) -> List[list]:
        """Fetch OHLCV bars with automatic pagination.

        Parameters
        ----------
        symbol:
            Trading pair, e.g. ``"BTC/USDT"``.
        timeframe:
            Candle interval recognised by the exchange (``"1m"``, ``"1h"``, …).
        since:
            Start timestamp in **milliseconds** (UTC).  If ``None`` the
            exchange default is used.
        limit:
            Maximum number of bars per single API request.  The method
            will paginate automatically until no new bars are returned.

        Returns
        -------
        List[list]
            Each inner list is ``[timestamp_ms, open, high, low, close, volume]``.
        """
        all_bars: List[list] = []
        current_since = since

        while True:
            batch: List[list] = self._retry(
                self.exchange.fetch_ohlcv,
                symbol,
                timeframe,
                since=current_since,
                limit=limit,
            )

            if not batch:
                break

            all_bars.extend(batch)
            logger.debug(
                "Fetched %d bars for %s (total so far: %d)",
                len(batch),
                symbol,
                len(all_bars),
            )

            # If we got fewer than *limit* bars the exchange has no more data.
            if len(batch) < limit:
                break

            # Move the cursor past the last bar we received.
            current_since = batch[-1][0] + 1
            time.sleep(self.RATE_LIMIT_SLEEP)

        return all_bars
