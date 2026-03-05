---
name: clawquant-trader
description: Use this skill for quantitative research/trading tasks (data pull, backtest, sweep, radar, report, deploy) via clawquant CLI.
user-invocable: true
metadata:
  { "openclaw": { "emoji": "📈", "requires": { "bins": ["python3"] } } }
---

# ClawQuant Trader

Use this skill when the user asks for strategy research, backtesting, signal scan, or trading deployment actions.

## Command Path

Always prefer the virtual-env executable path first:

`<VENV_PATH>/bin/clawquant`

If it does not exist, fallback to:

`clawquant`

> **Note:** Replace `<VENV_PATH>` with your actual clawquant virtual environment path when deploying.

## Output Rule

- Prefer machine-readable output first: add global `--json`.
- If a command fails, return the exact error briefly, then propose the smallest retry.
- Keep answers concise and include key metrics or top results only unless user asks for full raw output.

## Safe Execution Rule

- Never run `deploy live` unless user explicitly says they accept live trading risk.
- For data/backtest/report/radar, execute directly.
- Before `deploy live`, require explicit confirmation in the same turn.

## Intent Mapping (6 Skills)

Map natural language intents to these command families:

1. `quant_data_pull` -> `data pull`
2. `quant_backtest_batch` -> `backtest batch`
3. `quant_backtest_sweep` -> `backtest sweep`
4. `quant_report_get` -> `report generate`
5. `quant_radar_scan` -> `radar scan`
6. `quant_deploy` -> `deploy paper|live`

Default arguments if user does not specify:

- `interval=1h`
- `days=10` for data/radar
- `days=30` for backtest
- `exchange=binance` for data pull
- `capital=10000` for backtest/deploy
- `symbols=BTC/USDT,ETH/USDT` for radar
- `strategies=ma_crossover,dca` for radar

When users ask to compare strategies and did not specify list, use:

`dca,ma_crossover,grid,rsi_reversal,bollinger_bands,macd,breakout`

## Common Commands

### Show strategy list

```bash
clawquant --json strategy list
```

### Pull market data

```bash
clawquant --json data pull BTC/USDT,ETH/USDT --interval 1h --days 30
```

### Single backtest

```bash
clawquant --json backtest run ma_crossover --symbol BTC/USDT --interval 1h --days 30
```

### Batch backtest

```bash
clawquant --json backtest batch dca,ma_crossover,grid --symbols BTC/USDT,ETH/USDT --days 30
```

### Parameter sweep

```bash
clawquant --json backtest sweep ma_crossover --grid '{"fast_period":[5,10,20],"slow_period":[20,30,50]}'
```

### Radar scan

```bash
clawquant --json radar scan --symbols BTC/USDT,ETH/USDT --strategies ma_crossover,dca
```

### Generate report

```bash
clawquant --json report generate <run_id>
```

### Deploy paper

```bash
clawquant --json deploy paper ma_crossover --symbol BTC/USDT --interval 1h --capital 10000
```

### Deploy live (confirm first)

```bash
clawquant --json deploy live ma_crossover --symbol BTC/USDT --interval 1h --capital 10000 --i-know-what-im-doing
```

## Decision Workflow

When the user asks to find, compare, or optimize strategies, follow this workflow strictly:

### Step 1: Batch Compare

Run `backtest batch` with all relevant strategies **and all requested symbols**. If user asks for BTC and ETH, include both in `--symbols`. Parse the JSON output carefully — each entry in the result array has a `run_id` field containing the strategy name and symbol (e.g. `ma_crossover_btc_usdt_...`). Report results for EVERY symbol separately. Do NOT say "no trades" unless the JSON output actually shows `total_trades: 0` for that entry.

Rank results by `total_return_pct` (primary) and `sharpe_ratio` (secondary).

### Step 2: Pick the Winner

Always select the **top-performing strategy from batch results** for further optimization. Never pick a different strategy without explicit user instruction. State clearly which strategy was selected and why.

### Step 3: Parameter Sweep (optional)

Run `backtest sweep` on the winner. Compare sweep results against the batch baseline:

- If the best sweep result **improves** on the baseline -> recommend the optimized params.
- If the best sweep result is **worse** than the baseline -> recommend the **original default params** and explain that optimization did not help.

### Step 4: Report

Always include a before/after comparison table when presenting optimized results. Key columns: total_return_pct, max_drawdown_pct, win_rate, sharpe_ratio, total_trades.

### Common Mistakes to Avoid

- Do NOT pick a strategy for sweep that was not the best in batch comparison.
- Do NOT recommend parameters that perform worse than defaults.
- Do NOT present a single result without comparing it to the baseline.
- If total_trades < 10, warn that the sample size is too small for reliable conclusions.

## Parameter Notes

- `backtest sweep` expects JSON grid in `--grid`.
- `report generate` requires valid `run_id`.
- `radar scan` top count may use `--top` in current CLI.
- Custom strategy files may be referenced as `file:./path/to/strategy.py` when supported by the command.
