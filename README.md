# ClawQuant Trader

量化研究基建工具链，供 AI Agent（龙虾）通过自然语言调用，实现批量回测、策略评分、机会扫描、报告生成等研究能力。

## Quick Start

```bash
# 创建虚拟环境并安装依赖
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt

# 配置环境变量（可选，用于实盘数据）
cp .env.example .env
# 编辑 .env 填入 Binance API Key

# 查看帮助
python -m clawquant.clawquant_cli --help
```

## Commands

### Data Management
```bash
# 拉取数据
clawquant data pull BTC/USDT,ETH/USDT --interval 1h --days 10

# 数据质量检查
clawquant data inspect BTC/USDT --interval 1h

# 查看缓存状态
clawquant data cache-status
```

### Strategy Management
```bash
# 列出所有策略
clawquant strategy list

# 验证策略
clawquant strategy validate --name ma_crossover

# 生成策略模板
clawquant strategy scaffold --name my_strategy --output ./strategies_user/
```

### Backtesting
```bash
# 单次回测
clawquant backtest run ma_crossover --symbol BTC/USDT --interval 1h --days 30

# 批量回测
clawquant backtest batch dca,ma_crossover,grid --symbols BTC/USDT,ETH/USDT

# 参数扫描
clawquant backtest sweep ma_crossover --grid '{"fast_period": [5,10,20], "slow_period": [20,30,50]}'

# 走前验证
clawquant backtest walkforward ma_crossover --days 90 --splits 3
```

### Radar (Opportunity Scanning)
```bash
# 扫描交易机会
clawquant radar scan --symbols BTC/USDT,ETH/USDT --strategies ma_crossover,dca

# 解释特定机会
clawquant radar explain BTC/USDT ma_crossover
```

### Reports
```bash
# 生成报告（JSON + Markdown + 图表）
clawquant report generate <run_id>

# 批量报告对比
clawquant report batch <run_id1>,<run_id2>,<run_id3>
```

### Deployment
```bash
# 模拟交易
clawquant deploy paper ma_crossover --symbol BTC/USDT

# 实盘交易（需要确认）
clawquant deploy live ma_crossover --i-know-what-im-doing

# 查看部署状态
clawquant deploy status

# 停止/平仓
clawquant deploy stop ma_crossover
clawquant deploy flatten ma_crossover
```

## JSON Output

所有命令支持 `--json` 全局标志，输出 JSON 格式供 Agent 消费：

```bash
clawquant --json backtest run ma_crossover --symbol BTC/USDT --days 10
```

## Built-in Strategies

| Strategy | Description | Type |
|----------|-------------|------|
| `dca` | Dollar Cost Averaging - 定投 | Passive |
| `ma_crossover` | Moving Average Crossover - 均线交叉 | Trend Following |
| `grid` | Grid Trading - 网格交易 | Mean Reversion |

## Custom Strategies

将自定义策略 `.py` 文件放入 `strategies_user/` 目录，继承 `BaseStrategy` 并实现 6 个方法即可被自动发现。

使用 `clawquant strategy scaffold` 生成模板。

## Project Structure

```
clawquant/
├── clawquant_cli.py          # CLI 入口
├── cli/                      # CLI 命令实现
├── core/                     # 核心逻辑
│   ├── data/                 # 数据拉取/缓存/检查
│   ├── runtime/              # 策略加载/沙箱
│   ├── backtest/             # 回测引擎
│   ├── evaluate/             # 指标计算/评分
│   ├── radar/                # 机会扫描
│   ├── report/               # 报告生成
│   └── deploy/               # 部署管理
├── strategies_builtin/       # 内置策略
├── strategies_user/          # 用户策略
├── integrations/             # 外部服务集成
└── skills/                   # Agent Skill 定义
```

## Tech Stack

- **Python 3.11+** | **Typer** (CLI) | **ccxt** (Exchange) | **pandas** (Data) | **matplotlib** (Charts) | **pydantic** (Models) | **Rich** (Output)
