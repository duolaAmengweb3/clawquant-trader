"""BacktestEngine: event-driven main loop (Bar -> Signal -> Order -> Fill -> Portfolio)."""

from __future__ import annotations

import hashlib
import json
import logging
import platform
import sys
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from clawquant import __version__
from clawquant.core.backtest.config import BacktestConfig
from clawquant.core.backtest.events import BarEvent, FillEvent, OrderEvent, SignalEvent
from clawquant.core.backtest.execution import SimulatedBroker
from clawquant.core.backtest.portfolio import Portfolio
from clawquant.core.backtest.result import BacktestResult, RunMeta
from clawquant.core.backtest.risk import RiskManager
from clawquant.core.runtime.base_strategy import BaseStrategy
from clawquant.core.runtime.models import MarketState, PortfolioState
from clawquant.core.utils.run_id import ensure_run_dir, generate_run_id

logger = logging.getLogger(__name__)


class BacktestEngine:
    """Event-driven backtest engine.

    Flow per bar:
        1. Emit BarEvent
        2. Check for pending orders from previous bar (fill at current open for next_open model)
        3. Read pre-computed signal for current bar
        4. If signal != 0, run position sizing + risk checks -> create OrderEvent
        5. Queue order for next bar fill (next_open model) or fill now (current_close)
        6. Update portfolio equity
    """

    def __init__(self, config: BacktestConfig, strategy: BaseStrategy, df: pd.DataFrame):
        self.config = config
        self.strategy = strategy
        self.df = df.reset_index(drop=True)
        self.broker = SimulatedBroker(config)
        self.portfolio = Portfolio(config.initial_capital, config.symbol)
        self.risk_mgr = RiskManager(config.risk_limits, config.initial_capital)

        # Event queue
        self._pending_orders: deque[OrderEvent] = deque()
        self._warnings: List[str] = []

        # Pre-compute strategy params (use defaults from schema merged with overrides)
        meta = strategy.metadata()
        self.params = self._resolve_params(meta.params_schema, config.strategy_params)

    def _resolve_params(self, schema: dict, overrides: dict) -> dict:
        """Merge defaults from JSON Schema with user overrides."""
        params = {}
        props = schema.get("properties", {})
        for key, prop in props.items():
            if key in overrides:
                params[key] = overrides[key]
            elif "default" in prop:
                params[key] = prop["default"]
        # Include any override keys not in schema (forward compatibility)
        for key, val in overrides.items():
            if key not in params:
                params[key] = val
        return params

    def run(self) -> BacktestResult:
        """Execute the backtest and return results."""
        run_id = generate_run_id(self.config.strategy_name, self.config.symbol)
        logger.info(f"Starting backtest: {run_id}")

        # Pre-compute indicators and signals
        try:
            df_with_indicators = self.strategy.compute_indicators(self.df.copy(), self.params)
            signals = self.strategy.generate_signals(df_with_indicators, self.params)
        except Exception as e:
            return BacktestResult(
                run_id=run_id,
                success=False,
                error_type="StrategyError",
                message=f"Strategy computation failed: {e}",
            )

        # Validate signals
        if len(signals) != len(self.df):
            return BacktestResult(
                run_id=run_id,
                success=False,
                error_type="StrategyError",
                message=f"Signal length {len(signals)} != data length {len(self.df)}",
            )

        valid_values = {-1, 0, 1}
        unique_vals = set(signals.unique())
        if not unique_vals.issubset(valid_values):
            return BacktestResult(
                run_id=run_id,
                success=False,
                error_type="StrategyError",
                message=f"Invalid signal values: {unique_vals - valid_values}",
            )

        # Main loop
        n_bars = len(self.df)
        no_trade_streak = 0

        for i in range(n_bars):
            row = self.df.iloc[i]
            ts = pd.Timestamp(row["timestamp"]).to_pydatetime()
            price = float(row["close"])
            open_price = float(row["open"])

            # 1. Fill pending orders at current bar's open
            while self._pending_orders:
                order = self._pending_orders.popleft()
                fill = self.broker.fill_order(order, open_price, ts, i)
                if fill:
                    self.portfolio.process_fill(fill)
                    self.risk_mgr.record_trade(i)
                    no_trade_streak = 0

            # 2. Read signal
            signal = int(signals.iloc[i])

            # 3. Process signal
            if signal != 0 and not self.risk_mgr.is_stopped:
                portfolio_state = self.portfolio.get_state(price, ts)
                market_state = MarketState(
                    symbol=self.config.symbol,
                    current_price=price,
                    bar_index=i,
                    timestamp=ts,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=price,
                    volume=float(row["volume"]),
                )

                # Position sizing
                amount_usdt = self.strategy.position_sizing(signal, portfolio_state, self.params)

                # Risk checks (strategy-level)
                risk_actions = self.strategy.risk_controls(portfolio_state, market_state, self.params)
                skip = False
                for action in risk_actions:
                    if action.get("action") in ("SKIP", "FLATTEN"):
                        skip = True
                        if action.get("action") == "FLATTEN" and self.portfolio.position_qty > 0:
                            # Force sell everything
                            flatten_amount = self.portfolio.position_qty * price
                            self._create_order(i, ts, "SELL", flatten_amount)
                        break

                if skip:
                    signal = 0

                # Engine-level risk checks
                if signal != 0 and amount_usdt != 0:
                    engine_risks = self.risk_mgr.check(
                        portfolio_state, amount_usdt, i, self.portfolio.orders_today
                    )
                    for action in engine_risks:
                        if action["action"] == "SKIP":
                            skip = True
                            break
                        elif action["action"] == "FLATTEN":
                            if self.portfolio.position_qty > 0:
                                flatten_amount = self.portfolio.position_qty * price
                                self._create_order(i, ts, "SELL", flatten_amount)
                            skip = True
                            break
                        elif action["action"] == "REDUCE":
                            amount_usdt = amount_usdt * 0.5  # Reduce by half
                            self._warnings.append(f"Bar {i}: Position reduced due to risk limit")

                    if not skip and abs(amount_usdt) > 0:
                        side = "BUY" if amount_usdt > 0 else "SELL"
                        self._create_order(i, ts, side, abs(amount_usdt))
            else:
                no_trade_streak += 1

            # 4. Record equity
            self.portfolio.record_equity(ts, price, i)

        # Warn if long no-trade streak
        if no_trade_streak > n_bars * 0.5:
            self._warnings.append(
                f"No trades for {no_trade_streak}/{n_bars} bars ({no_trade_streak/n_bars:.0%})"
            )

        # Close open positions at last price
        if n_bars > 0:
            last_row = self.df.iloc[-1]
            last_price = float(last_row["close"])
            last_ts = pd.Timestamp(last_row["timestamp"]).to_pydatetime()
            self.portfolio.close_open_position(last_price, last_ts, n_bars - 1)

        # Build result
        result = self._build_result(run_id)

        # Save to disk
        self._save_run(run_id, result)

        logger.info(f"Backtest complete: {run_id} | Return: {result.total_return_pct:.2f}% | Trades: {result.total_trades}")
        return result

    def _create_order(self, bar_index: int, timestamp: datetime, side: str, amount_usdt: float) -> None:
        """Create and queue an order."""
        order = OrderEvent(
            bar_index=bar_index,
            timestamp=timestamp,
            symbol=self.config.symbol,
            side=side,
            amount_usdt=amount_usdt,
            strategy_name=self.config.strategy_name,
        )
        if self.config.fill_model == "current_close":
            # Fill immediately at current close
            row = self.df.iloc[bar_index]
            fill = self.broker.fill_order(
                order, float(row["close"]), timestamp, bar_index
            )
            if fill:
                self.portfolio.process_fill(fill)
                self.risk_mgr.record_trade(bar_index)
        else:
            # Queue for next bar open
            self._pending_orders.append(order)

    def _build_result(self, run_id: str) -> BacktestResult:
        """Build the final BacktestResult."""
        trades = self.portfolio.trades
        equity_curve = self.portfolio.equity_curve

        total_return = self.portfolio.cash - self.config.initial_capital + (
            self.portfolio.position_qty * float(self.df.iloc[-1]["close"]) if len(self.df) > 0 else 0
        )
        total_return_pct = (total_return / self.config.initial_capital * 100) if self.config.initial_capital > 0 else 0

        # Win rate
        winning = [t for t in trades if t.pnl > 0]
        win_rate = len(winning) / len(trades) * 100 if trades else 0

        # Profit factor
        gross_profit = sum(t.pnl for t in trades if t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in trades if t.pnl < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf") if gross_profit > 0 else 0

        avg_pnl = sum(t.pnl for t in trades) / len(trades) if trades else 0
        avg_bars = sum(t.bars_held for t in trades) / len(trades) if trades else 0

        # Build run meta
        meta = self.strategy.metadata()
        data_csv_bytes = self.df.to_csv(index=False).encode()
        data_hash = hashlib.sha256(data_csv_bytes).hexdigest()
        params_hash = hashlib.sha256(json.dumps(self.params, sort_keys=True).encode()).hexdigest()

        req_path = Path("requirements.txt")
        if req_path.exists():
            deps_hash = hashlib.sha256(req_path.read_bytes()).hexdigest()
        else:
            deps_hash = "unknown"

        run_meta = RunMeta(
            run_id=run_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            engine_version=__version__,
            strategy={
                "name": meta.name,
                "version": meta.version,
                "params": self.params,
                "params_hash": f"sha256:{params_hash[:12]}",
            },
            data={
                "symbol": self.config.symbol,
                "interval": self.config.interval,
                "start": self.df.iloc[0]["timestamp"].isoformat() if len(self.df) > 0 else "",
                "end": self.df.iloc[-1]["timestamp"].isoformat() if len(self.df) > 0 else "",
                "bar_count": len(self.df),
                "data_hash": f"sha256:{data_hash[:12]}",
                "source": self.config.exchange,
            },
            config=self.config.model_dump(),
            environment={
                "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                "platform": platform.system().lower(),
                "dependencies_hash": f"sha256:{deps_hash[:12]}",
            },
        )

        return BacktestResult(
            run_id=run_id,
            success=True,
            total_return=round(total_return, 2),
            total_return_pct=round(total_return_pct, 2),
            max_drawdown=round(self.portfolio.max_drawdown, 2),
            max_drawdown_pct=round(self.portfolio.max_drawdown_pct * 100, 2),
            win_rate=round(win_rate, 2),
            profit_factor=round(profit_factor, 4),
            total_trades=len(trades),
            avg_trade_pnl=round(avg_pnl, 2),
            avg_bars_held=round(avg_bars, 1),
            trades=trades,
            equity_curve=equity_curve,
            warnings=self._warnings,
            run_meta=run_meta,
        )

    def _save_run(self, run_id: str, result: BacktestResult) -> None:
        """Save all run artifacts to disk."""
        run_dir = ensure_run_dir(run_id)

        # run_meta.json
        if result.run_meta:
            (run_dir / "run_meta.json").write_text(
                result.run_meta.model_dump_json(indent=2), encoding="utf-8"
            )

        # trades.json
        trades_data = [t.model_dump(mode="json") for t in result.trades]
        (run_dir / "trades.json").write_text(
            json.dumps(trades_data, indent=2, default=str), encoding="utf-8"
        )

        # equity_curve.csv
        if result.equity_curve:
            eq_df = pd.DataFrame(result.equity_curve)
            eq_df.to_csv(run_dir / "equity_curve.csv", index=False)

        # result.json
        result_dict = result.model_dump(mode="json")
        result_dict.pop("trades", None)  # Already saved separately
        result_dict.pop("equity_curve", None)
        (run_dir / "result.json").write_text(
            json.dumps(result_dict, indent=2, default=str), encoding="utf-8"
        )

        logger.info(f"Run saved to {run_dir}")
