# ClawQuant Trader

[![PyPI version](https://img.shields.io/pypi/v/clawquant.svg)](https://pypi.org/project/clawquant/)
[![Python](https://img.shields.io/pypi/pyversions/clawquant.svg)](https://pypi.org/project/clawquant/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> Quantitative trading research infrastructure for AI Agents.

量化研究基建工具链，供 AI Agent（龙虾）通过自然语言调用，实现 **批量回测、策略评分、机会扫描、报告生成** 等研究能力。

---

## Features

- **Data Pipeline** — 通过 ccxt 从交易所拉取 OHLCV 数据，自动 Parquet 缓存、增量更新、质量检查
- **Strategy Framework** — BaseStrategy ABC，6 个抽象方法，内置 3 个策略（DCA / MA Crossover / Grid）
- **Backtest Engine** — 事件驱动引擎，下一根 K 线开盘价成交，避免未来函数
- **Batch & Sweep** — 多策略 × 多标的批量回测，参数网格/随机扫描，Walk-forward 验证
- **Evaluation** — Sharpe / Sortino / Calmar / MaxDD 等指标 + 5 维稳定性评分（0-100）
- **Reports** — JSON + Markdown + 图表（权益曲线 / 回撤 / 交易标记）
- **Radar** — 多标的实时信号扫描 + 机会解释
- **Deploy** — Paper Trading 模拟 / Live Trading 实盘（带安全确认）
- **Agent-First** — 所有命令支持 `--json` 输出，附带 6 个 Skill YAML 供 AI Agent 调用

---

## Installation

### From PyPI (Recommended)

```bash
pip install clawquant
```

### From Source

```bash
git clone https://github.com/duolaAmengweb3/clawquant-trader.git
cd clawquant-trader
pip install -e .
```

安装后即可使用 `clawquant` 命令：

```bash
clawquant --help
```

---

## Quick Start

```bash
# 1. 配置环境变量（可选，用于实盘数据拉取）
cp .env.example .env
# 编辑 .env 填入 Binance API Key 和代理（如需要）

# 2. 拉取数据
clawquant data pull BTC/USDT,ETH/USDT --interval 1h --days 10

# 3. 运行回测
clawquant backtest run ma_crossover --symbol BTC/USDT --interval 1h --days 10

# 4. 生成报告
clawquant report generate <run_id>

# 5. 批量对比
clawquant backtest batch dca,ma_crossover,grid --symbols BTC/USDT,ETH/USDT --days 10
```

---

## Commands

ClawQuant 提供 6 个命令组，共 17 个子命令：

### `data` — 数据管理

```bash
# 拉取 OHLCV 数据（自动缓存为 Parquet）
clawquant data pull BTC/USDT,ETH/USDT --interval 1h --days 10

# 数据质量检查（缺口、重复、异常值）
clawquant data inspect BTC/USDT --interval 1h

# 查看本地缓存状态
clawquant data cache-status
```

### `strategy` — 策略管理

```bash
# 列出所有可用策略（内置 + 用户）
clawquant strategy list

# 验证策略完整性（用合成数据跑全部 6 个方法）
clawquant strategy validate --name ma_crossover

# 生成自定义策略模板
clawquant strategy scaffold --name my_strategy --output ./strategies_user/
```

### `backtest` — 回测引擎

```bash
# 单次回测
clawquant backtest run ma_crossover --symbol BTC/USDT --interval 1h --days 30

# 批量回测（多策略 × 多标的，ProcessPoolExecutor 并行）
clawquant backtest batch dca,ma_crossover,grid --symbols BTC/USDT,ETH/USDT

# 参数网格扫描
clawquant backtest sweep ma_crossover \
  --grid '{"fast_period": [5,10,20], "slow_period": [20,30,50]}'

# Walk-forward 滚动验证
clawquant backtest walkforward ma_crossover --days 90 --splits 3
```

### `radar` — 机会扫描

```bash
# 扫描当前交易信号
clawquant radar scan --symbols BTC/USDT,ETH/USDT --strategies ma_crossover,dca

# 解释特定机会
clawquant radar explain BTC/USDT ma_crossover
```

### `report` — 报告生成

```bash
# 生成完整报告（JSON + Markdown + 图表）
clawquant report generate <run_id>

# 批量报告对比
clawquant report batch <run_id1>,<run_id2>,<run_id3>
```

报告输出到 `runs/<run_id>/` 目录，包含：
- `report.json` — 结构化数据
- `report.md` — Markdown 可读报告
- `equity.png` — 权益曲线图
- `drawdown.png` — 回撤图
- `trades.png` — 交易标记图

### `deploy` — 部署管理

```bash
# Paper Trading（模拟交易）
clawquant deploy paper ma_crossover --symbol BTC/USDT

# Live Trading（需显式确认 + 风控必填）
clawquant deploy live ma_crossover --symbol BTC/USDT --i-know-what-im-doing

# 查看运行中的部署
clawquant deploy status

# 停止 / 紧急平仓
clawquant deploy stop ma_crossover
clawquant deploy flatten ma_crossover
```

---

## JSON Output

所有命令支持 `--json` 全局标志，输出结构化 JSON，供 AI Agent 程序化消费：

```bash
clawquant --json strategy list
clawquant --json backtest run ma_crossover --symbol BTC/USDT --days 10
clawquant --json radar scan --symbols BTC/USDT
```

---

## Built-in Strategies

| Strategy | Description | Type | Key Params |
|----------|-------------|------|------------|
| `dca` | Dollar Cost Averaging 定投 | Passive | `invest_amount`, `invest_interval` |
| `ma_crossover` | Moving Average Crossover 均线交叉 | Trend Following | `fast_period`, `slow_period`, `ma_type` |
| `grid` | Grid Trading 网格交易 | Mean Reversion | `grid_count`, `grid_spacing_pct`, `order_amount` |

---

## Custom Strategies

继承 `BaseStrategy`，实现 6 个抽象方法：

```python
from clawquant.core.runtime.base_strategy import BaseStrategy, StrategyMetadata

class MyStrategy(BaseStrategy):
    @classmethod
    def metadata(cls) -> StrategyMetadata:
        """策略元信息 + 参数 JSON Schema"""
        ...

    def compute_indicators(self, df, params) -> pd.DataFrame:
        """计算技术指标，返回带新列的 DataFrame"""
        ...

    def generate_signals(self, df, params) -> pd.Series:
        """生成信号序列: 1=BUY, 0=HOLD, -1=SELL"""
        ...

    def position_sizing(self, signal, portfolio_state, params) -> float:
        """返回目标仓位变化量（USDT 计价）"""
        ...

    def risk_controls(self, portfolio_state, market_state, params) -> list:
        """返回风控动作列表"""
        ...

    def explain(self, last_state) -> dict:
        """返回可解释输出"""
        ...
```

将 `.py` 文件放入 `strategies_user/` 目录即可自动发现，或通过 `file:` 路径指定：

```bash
clawquant backtest run file:./my_strategy.py --symbol BTC/USDT
```

使用 `clawquant strategy scaffold` 生成完整模板。

---

## Backtest Engine Design

### 事件驱动架构

```
Bar Event → Signal Event → Order Event → Fill Event → Portfolio Update
```

### 关键设计决策

| 决策 | 选择 | 原因 |
|------|------|------|
| 成交模型 | 下一根 K 线开盘价 | 避免未来函数偏差 |
| 数据存储 | Parquet | 列式读取快，pandas 原生支持 |
| 并行回测 | ProcessPoolExecutor | CPU 密集型任务需真正并行 |
| 策略状态 | 类实例属性 | Grid 等有状态策略最清晰 |
| Run ID | `{strategy}_{symbol}_{ts}_{uuid[:8]}` | 人类可读 + 唯一 |

### 评分体系

5 维稳定性评分（0-100）：

| 维度 | 权重 | 评估内容 |
|------|------|----------|
| Quality | 30% | Sharpe, Sortino, Win Rate |
| Risk | 30% | Max Drawdown, Calmar Ratio |
| Robustness | 20% | 年化波动率、连续亏损 |
| Cost Sensitivity | 10% | 手续费占比 |
| Overtrade | 10% | 日均交易频率 |

### 可复现性保证

每次回测输出 `run_meta.json`，记录：
- 策略名称 + 版本 + 参数哈希
- 数据源 + 时间范围 + 数据哈希
- 引擎配置（初始资金、手续费、滑点）
- Python 版本 + 依赖哈希

相同输入 → 确定性结果。

---

## Project Structure

```
clawquant/
├── clawquant_cli.py          # Typer CLI 主入口
├── cli/                      # 6 个命令组实现
│   ├── data_cli.py           # data pull/inspect/cache-status
│   ├── strategy_cli.py       # strategy list/validate/scaffold
│   ├── backtest_cli.py       # backtest run/batch/sweep/walkforward
│   ├── radar_cli.py          # radar scan/explain
│   ├── report_cli.py         # report generate/batch
│   └── deploy_cli.py         # deploy paper/live/status/stop/flatten
├── core/
│   ├── data/                 # 数据拉取 / Parquet 缓存 / 质量检查 / 时间对齐
│   ├── runtime/              # BaseStrategy ABC / 策略加载器 / 沙箱
│   ├── backtest/             # 事件引擎 / 组合管理 / 撮合 / 风控 / 批量 / 扫描
│   ├── evaluate/             # 指标计算 / 5维评分
│   ├── radar/                # 信号扫描 / 机会解释
│   ├── report/               # JSON + Markdown + 图表报告
│   ├── deploy/               # Paper / Live 执行循环
│   └── utils/                # Run ID / 日志 / 输出格式
├── strategies_builtin/       # DCA / MA Crossover / Grid
├── strategies_user/          # 用户自定义策略目录
├── integrations/             # ccxt 封装 / Binance Skill 适配
└── skills/                   # 6 个 Agent Skill YAML 定义
```

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BINANCE_API_KEY` | Binance API Key | — |
| `BINANCE_SECRET` | Binance API Secret | — |
| `DEFAULT_EXCHANGE` | 默认交易所 | `binance` |
| `DATA_CACHE_DIR` | 数据缓存目录 | `data_cache` |
| `RUNS_DIR` | 回测结果目录 | `runs` |
| `HTTPS_PROXY` | 代理地址（访问交易所 API） | — |

---

## Agent Skills

ClawQuant 提供 6 个 YAML Skill 定义（`skills/` 目录），AI Agent 可通过自然语言调用：

| Skill | Description |
|-------|-------------|
| `quant_data_pull` | 拉取交易数据 |
| `quant_backtest_batch` | 批量回测 |
| `quant_backtest_sweep` | 参数扫描 |
| `quant_radar_scan` | 机会扫描 |
| `quant_report_get` | 获取报告 |
| `quant_deploy` | 部署交易 |

示例对话：
> "在 BTC 和 ETH 上对比 DCA、均线交叉、网格三个策略，过去 10 天，给我 top3 报告"

Agent 将自动编排 `data pull → backtest batch → report batch` 完成全流程。

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| CLI Framework | [Typer](https://typer.tiangolo.com/) |
| Exchange API | [ccxt](https://github.com/ccxt/ccxt) |
| Data Processing | [pandas](https://pandas.pydata.org/) + [PyArrow](https://arrow.apache.org/docs/python/) |
| Charts | [matplotlib](https://matplotlib.org/) |
| Data Models | [Pydantic v2](https://docs.pydantic.dev/) |
| Terminal Output | [Rich](https://rich.readthedocs.io/) |

---

## Requirements

- Python >= 3.10
- 网络访问交易所 API（可配置代理）

---

## License

[MIT](LICENSE) © duolaAmeng
