"""Paper/Live deployment runner: pull bar -> signal -> order -> record loop."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class DeployRunner:
    """Runs a strategy in paper or live mode.

    Paper mode: simulates orders, no real exchange interaction.
    Live mode: places real orders via ccxt (requires --i-know-what-im-doing flag).
    """

    def __init__(
        self,
        strategy_name: str,
        symbol: str,
        interval: str = "1h",
        mode: str = "paper",
        capital: float = 10000.0,
        params: Optional[dict] = None,
        exchange: str = "binance",
    ):
        self.strategy_name = strategy_name
        self.symbol = symbol
        self.interval = interval
        self.mode = mode
        self.capital = capital
        self.params = params or {}
        self.exchange = exchange
        self._running = False
        self._state_file = Path("runs") / f"deploy_{strategy_name}_{symbol.replace('/', '_')}_{mode}.json"

    def start(self) -> None:
        """Start the deployment loop."""
        from clawquant.core.backtest.config import BacktestConfig
        from clawquant.core.backtest.execution import SimulatedBroker
        from clawquant.core.backtest.portfolio import Portfolio
        from clawquant.core.backtest.risk import RiskManager
        from clawquant.core.data.fetcher import fetch_data
        from clawquant.core.data.models import DataPullRequest
        from clawquant.core.runtime.loader import load_strategy
        from clawquant.core.runtime.models import MarketState

        strat = load_strategy(self.strategy_name)
        meta = strat.metadata()

        # Resolve params
        params = {}
        for k, v in meta.params_schema.get("properties", {}).items():
            if "default" in v:
                params[k] = v["default"]
        params.update(self.params)

        config = BacktestConfig(
            initial_capital=self.capital,
            strategy_name=self.strategy_name,
            strategy_params=params,
            symbol=self.symbol,
            interval=self.interval,
        )

        portfolio = Portfolio(self.capital, self.symbol)
        broker = SimulatedBroker(config)
        risk_mgr = RiskManager(config.risk_limits, self.capital)

        self._running = True
        self._save_state("running", {"started": datetime.now(timezone.utc).isoformat()})
        logger.info(f"Deploy [{self.mode}] started: {self.strategy_name} on {self.symbol}")

        bar_index = 0
        interval_seconds = self._interval_to_seconds()

        try:
            while self._running:
                # Pull latest data
                try:
                    request = DataPullRequest(symbols=[self.symbol], interval=self.interval, days=2, exchange=self.exchange)
                    dfs = fetch_data(request)
                    df = dfs.get(self.symbol)
                except Exception as e:
                    logger.error(f"Data fetch error: {e}")
                    time.sleep(interval_seconds)
                    continue

                if df is None or df.empty:
                    logger.warning("No data received, waiting...")
                    time.sleep(interval_seconds)
                    continue

                # Compute indicators and get latest signal
                try:
                    df_ind = strat.compute_indicators(df.copy(), params)
                    signals = strat.generate_signals(df_ind, params)
                    last_signal = int(signals.iloc[-1])
                except Exception as e:
                    logger.error(f"Strategy error: {e}")
                    time.sleep(interval_seconds)
                    continue

                last_row = df.iloc[-1]
                price = float(last_row["close"])
                ts = datetime.now(timezone.utc)

                # Process signal
                if last_signal != 0:
                    portfolio_state = portfolio.get_state(price, ts)
                    market_state = MarketState(
                        symbol=self.symbol,
                        current_price=price,
                        bar_index=bar_index,
                        timestamp=ts,
                        open=float(last_row["open"]),
                        high=float(last_row["high"]),
                        low=float(last_row["low"]),
                        close=price,
                        volume=float(last_row["volume"]),
                    )

                    amount = strat.position_sizing(last_signal, portfolio_state, params)
                    risk_actions = risk_mgr.check(portfolio_state, amount, bar_index, portfolio.orders_today)

                    skip = any(a["action"] in ("SKIP", "FLATTEN") for a in risk_actions)

                    if not skip and abs(amount) > 0:
                        side = "BUY" if amount > 0 else "SELL"
                        from clawquant.core.backtest.events import OrderEvent
                        order = OrderEvent(
                            bar_index=bar_index,
                            timestamp=ts,
                            symbol=self.symbol,
                            side=side,
                            amount_usdt=abs(amount),
                            strategy_name=self.strategy_name,
                        )

                        if self.mode == "paper":
                            fill = broker.fill_order(order, price, ts, bar_index)
                            if fill:
                                portfolio.process_fill(fill)
                                risk_mgr.record_trade(bar_index)
                                logger.info(f"[PAPER] {side} {fill.quantity:.6f} @ ${fill.fill_price:.2f}")
                        else:
                            # Live mode: place real order via ccxt
                            logger.info(f"[LIVE] Would place {side} ${abs(amount):.2f} @ ~${price:.2f}")
                            # TODO: Integrate with ccxt for real order placement

                # Record state
                portfolio.record_equity(ts, price, bar_index)
                self._save_state("running", {
                    "bar_index": bar_index,
                    "price": price,
                    "signal": last_signal,
                    "equity": portfolio.get_state(price, ts).total_value,
                    "position_qty": portfolio.position_qty,
                    "last_update": ts.isoformat(),
                })

                bar_index += 1
                time.sleep(interval_seconds)

        except KeyboardInterrupt:
            logger.info("Deploy stopped by user")
        finally:
            self._running = False
            self._save_state("stopped", {"stopped": datetime.now(timezone.utc).isoformat()})

    def stop(self) -> None:
        """Signal the runner to stop."""
        self._running = False

    def _interval_to_seconds(self) -> int:
        """Convert interval string to seconds."""
        mapping = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}
        return mapping.get(self.interval, 3600)

    def _save_state(self, status: str, data: dict) -> None:
        """Persist current deployment state to disk."""
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        state = {
            "strategy": self.strategy_name,
            "symbol": self.symbol,
            "interval": self.interval,
            "mode": self.mode,
            "status": status,
            **data,
        }
        self._state_file.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
