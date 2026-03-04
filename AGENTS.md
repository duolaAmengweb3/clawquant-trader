# AGENTS.md - ClawQuant Trader Agent Guide

## Overview

ClawQuant Trader is a quantitative research infrastructure designed for AI Agent consumption. All commands output structured JSON when invoked with `--json` flag.

## Available Skills

### quant_data_pull
Pull OHLCV market data. Always run this first before backtesting.
```
clawquant --json data pull BTC/USDT,ETH/USDT --interval 1h --days 10
```

### quant_backtest_batch
Run batch backtests across multiple strategies and symbols.
```
clawquant --json backtest batch dca,ma_crossover,grid --symbols BTC/USDT,ETH/USDT --days 30
```

### quant_backtest_sweep
Find optimal parameters via grid/random search.
```
clawquant --json backtest sweep ma_crossover --grid '{"fast_period":[5,10,20],"slow_period":[20,30,50]}'
```

### quant_radar_scan
Scan for trading opportunities with confidence scoring.
```
clawquant --json radar scan --symbols BTC/USDT,ETH/USDT --strategies ma_crossover
```

### quant_report_get
Generate reports with metrics, charts, and stability scores.
```
clawquant --json report generate <run_id>
```

### quant_deploy
Deploy strategy for paper/live trading.
```
clawquant --json deploy paper ma_crossover --symbol BTC/USDT
```

## Typical Agent Workflow

1. **Data Pull**: `data pull` to fetch market data
2. **Batch Backtest**: `backtest batch` to compare strategies
3. **Parameter Sweep**: `backtest sweep` to optimize the best strategy
4. **Report**: `report generate` to create detailed analysis
5. **Radar**: `radar scan` for current opportunities
6. **Deploy**: `deploy paper` to start paper trading

## Output Format

All JSON outputs follow this structure:
```json
{
  "success": true|false,
  "error_type": "DataError|StrategyError|ConfigError|null",
  "message": "Human-readable message",
  "data": { ... }
}
```

## Key Metrics

- **stability_score** (0-100): Composite quality score
- **sharpe_ratio**: Risk-adjusted return
- **max_drawdown_pct**: Maximum peak-to-trough decline
- **win_rate**: Percentage of profitable trades
- **profit_factor**: Gross profit / gross loss

## Strategy Parameters

Use `clawquant --json strategy list` to get all strategies with their `params_schema` (JSON Schema format). Pass params via `--params '{"key": value}'`.

## File Locations

- **Data Cache**: `data_cache/` (Parquet files)
- **Run Results**: `runs/{run_id}/` (run_meta.json, trades.json, equity_curve.csv, result.json)
- **Reports**: `runs/{run_id}/` (report.json, report.md, equity.png, drawdown.png, trades.png)
