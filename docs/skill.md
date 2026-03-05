# ClawQuant Skills 使用指南

> 本文档说明如何在 AI Agent（如 Claude / Lobechat / GPTs）中加载和使用 ClawQuant 的 6 个 Skill。

---

## 什么是 Skill？

Skill 是 AI Agent 的"工具按钮"——把 CLI 命令封装成 Agent 可调用的函数接口。用户用自然语言下达指令，Agent 自动选择合适的 Skill 执行。

ClawQuant 提供 **6 个 Skill**，覆盖完整量化研究工作流：

```
拉数据 → 回测 → 扫参数 → 生成报告 → 扫机会 → 部署交易
```

所有 Skill 定义文件位于：`clawquant/skills/*.yaml`

---

## Skill 一览表

| # | Skill 名称 | 一句话说明 | 对应 CLI 命令 |
|---|-----------|-----------|--------------|
| 1 | `quant_data_pull` | 拉取 K 线数据 | `clawquant data pull` |
| 2 | `quant_backtest_batch` | 多策略批量回测 | `clawquant backtest batch` |
| 3 | `quant_backtest_sweep` | 参数扫描寻优 | `clawquant backtest sweep` |
| 4 | `quant_report_get` | 生成回测报告 | `clawquant report generate` |
| 5 | `quant_radar_scan` | 扫描交易机会 | `clawquant radar scan` |
| 6 | `quant_deploy` | 部署模拟/实盘交易 | `clawquant deploy` |

---

## Skill 详解

### 1. quant_data_pull — 拉取K线数据

**用途：** 从交易所拉取 OHLCV（开高低收量）数据，自动缓存为 Parquet 格式。

**自然语言示例：**
- "拉取 BTC 和 ETH 过去 10 天的 1 小时 K 线数据"
- "Pull 30 days of 4h data for BTC/USDT"

**参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `symbols` | string | 是 | — | 交易对，逗号分隔，如 `BTC/USDT,ETH/USDT` |
| `interval` | string | 否 | `1h` | K线周期：`1m`, `5m`, `15m`, `1h`, `4h`, `1d` |
| `days` | integer | 否 | `10` | 拉取天数 |
| `exchange` | string | 否 | `binance` | 交易所名称 |

**实际执行的命令：**
```bash
clawquant --json data pull BTC/USDT,ETH/USDT --interval 1h --days 10 --exchange binance
```

---

### 2. quant_backtest_batch — 多策略批量回测

**用途：** 在多个策略 × 多个标的上批量跑回测，返回每个组合的绩效指标。

**自然语言示例：**
- "对比 DCA、MA交叉、Grid 在 BTC 和 ETH 上过去 30 天的表现"
- "Backtest ma_crossover and dca on BTC/USDT,ETH/USDT for 30 days"

**参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `strategies` | string | 是 | — | 策略名，逗号分隔，如 `dca,ma_crossover,grid` |
| `symbols` | string | 否 | `BTC/USDT` | 交易对，逗号分隔 |
| `interval` | string | 否 | `1h` | K线周期 |
| `days` | integer | 否 | `30` | 回测天数 |
| `capital` | number | 否 | `10000` | 初始资金（USDT） |

**实际执行的命令：**
```bash
clawquant --json backtest batch dca,ma_crossover,grid --symbols BTC/USDT,ETH/USDT --interval 1h --days 30 --capital 10000
```

---

### 3. quant_backtest_sweep — 参数扫描寻优

**用途：** 对单个策略做参数网格/随机搜索，找到最优参数组合，结果按稳定性评分排序。

**自然语言示例：**
- "扫描 MA交叉策略的最优参数，快线 5-20，慢线 20-50"
- "Sweep ma_crossover fast_period=[5,10,20] slow_period=[20,30,50] on BTC/USDT"

**参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `strategy` | string | 是 | — | 策略名称 |
| `symbol` | string | 否 | `BTC/USDT` | 交易对 |
| `interval` | string | 否 | `1h` | K线周期 |
| `days` | integer | 否 | `30` | 回测天数 |
| `param_grid` | string | 是 | — | JSON 参数网格，如 `{"fast_period": [5,10,20], "slow_period": [20,30,50]}` |
| `mode` | string | 否 | `grid` | 搜索模式：`grid`（网格）或 `random`（随机） |

**实际执行的命令：**
```bash
clawquant --json backtest sweep ma_crossover --symbol BTC/USDT --interval 1h --days 30 \
  --grid '{"fast_period": [5,10,20], "slow_period": [20,30,50]}' --mode grid
```

---

### 4. quant_report_get — 生成回测报告

**用途：** 根据回测 Run ID 生成完整报告，包括 JSON 数据、Markdown 文档和图表。

**自然语言示例：**
- "生成上次回测的报告"
- "Generate report for run ma_crossover_btc_usdt_20260304_abc12345"

**参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `run_id` | string | 是 | — | 回测的 Run ID |
| `formats` | string | 否 | `json,md,charts` | 输出格式，逗号分隔：`json`, `md`, `charts` |

**实际执行的命令：**
```bash
clawquant --json report generate <run_id> --formats json,md,charts
```

**报告输出到 `runs/<run_id>/` 目录：**
- `report.json` — 结构化指标数据
- `report.md` — Markdown 可读报告
- `equity.png` — 权益曲线图
- `drawdown.png` — 回撤图
- `trades.png` — 交易标记图

---

### 5. quant_radar_scan — 扫描交易机会

**用途：** 用多个策略扫描多个标的，返回带置信度评分和解释的交易机会排行。

**自然语言示例：**
- "扫描 BTC/ETH/SOL 有没有交易机会"
- "Scan BTC/USDT,ETH/USDT for signals using ma_crossover"

**参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `symbols` | string | 否 | `BTC/USDT,ETH/USDT` | 扫描标的，逗号分隔 |
| `strategies` | string | 否 | `ma_crossover,dca` | 使用的策略，逗号分隔 |
| `interval` | string | 否 | `1h` | K线周期 |
| `days` | integer | 否 | `10` | 数据回看天数 |
| `top_n` | integer | 否 | `10` | 返回前 N 个机会 |

**实际执行的命令：**
```bash
clawquant --json radar scan --symbols BTC/USDT,ETH/USDT --strategies ma_crossover,dca \
  --interval 1h --days 10 --top 10
```

---

### 6. quant_deploy — 部署交易

**用途：** 部署策略进行模拟交易（Paper）或实盘交易（Live）。Paper 模式模拟订单，Live 模式需要显式确认。

**自然语言示例：**
- "用 MA交叉策略在 BTC 上开始模拟交易"
- "Start paper trading ma_crossover on BTC/USDT"

**参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `mode` | string | 否 | `paper` | 部署模式：`paper`（模拟）或 `live`（实盘） |
| `strategy` | string | 是 | — | 策略名称 |
| `symbol` | string | 否 | `BTC/USDT` | 交易对 |
| `interval` | string | 否 | `1h` | K线周期 |
| `capital` | number | 否 | `10000` | 初始资金（USDT） |

**实际执行的命令：**
```bash
clawquant --json deploy paper ma_crossover --symbol BTC/USDT --interval 1h --capital 10000
```

> **安全提醒：** Live 模式涉及真实资金，Agent 应在执行前向用户确认。

---

## 可用的内置策略

Skills 中 `strategies` 参数可使用以下内置策略名：

| 策略名 | 中文名 | 类型 | 关键参数 |
|--------|--------|------|----------|
| `dca` | 定投 | 被动型 | `invest_amount`, `invest_interval` |
| `ma_crossover` | 均线交叉 | 趋势跟踪 | `fast_period`, `slow_period`, `ma_type` |
| `grid` | 网格交易 | 均值回归 | `grid_count`, `grid_spacing_pct`, `order_amount` |
| `rsi_reversal` | RSI反转 | 均值回归 | `rsi_period`, `oversold`, `overbought` |
| `bollinger_bands` | 布林带 | 均值回归 | `bb_period`, `bb_std` |
| `macd` | MACD | 趋势跟踪 | `fast_period`, `slow_period`, `signal_period` |
| `breakout` | 唐奇安突破 | 趋势跟踪 | `lookback` |

也可使用 `file:./path/to/my_strategy.py` 加载用户自定义策略。

---

## 如何在 AI Agent 中加载 Skills

### 方式一：Claude Code / Claude Desktop

将 YAML 文件注册为 MCP Tool 或在 AGENTS.md / CLAUDE.md 中描述即可。Agent 会根据自然语言自动匹配 Skill 调用。

### 方式二：Lobechat / ChatGPT GPTs

1. 在插件/工具配置面板中，添加自定义函数
2. 按照每个 YAML 中的 `name`、`description`、`parameters` 填写
3. `command` 字段作为执行入口，替换 `{project_root}` 为实际路径

### 方式三：自定义 Agent 框架

解析 `clawquant/skills/*.yaml`，将每个 Skill 注册为工具函数：

```python
import yaml, subprocess, json

def load_skills(skills_dir="clawquant/skills"):
    skills = {}
    for f in Path(skills_dir).glob("*.yaml"):
        skill = yaml.safe_load(f.read_text())
        skills[skill["name"]] = skill
    return skills

def call_skill(skill, params, project_root="."):
    cmd = skill["command"]
    for k, v in params.items():
        cmd = cmd.replace(f"{{{k}}}", str(v))
    cmd = cmd.replace("{project_root}", project_root)
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return json.loads(result.stdout)
```

---

## 典型工作流编排

### 场景一：快速策略对比

```
用户：对比 7 个内置策略在 BTC 上最近 30 天的表现

Agent 编排：
  1. quant_data_pull    → 拉 BTC/USDT 30天 1h 数据
  2. quant_backtest_batch → 7 个策略批量回测
  3. quant_report_get   → 为 Top 3 生成报告
```

### 场景二：参数调优

```
用户：帮我优化 MA交叉策略，快线试 5/10/15/20，慢线试 20/30/40/50

Agent 编排：
  1. quant_data_pull       → 拉数据
  2. quant_backtest_sweep  → 4×4=16 组参数扫描
  3. quant_report_get      → 为最优参数生成报告
```

### 场景三：每日机会扫描

```
用户：扫一下主流币有没有机会

Agent 编排：
  1. quant_radar_scan → 扫描 BTC/ETH/SOL/BNB 等标的
  2. 返回 Top N 机会 + 解释 + 置信度
```

### 场景四：模拟上线

```
用户：用最优参数的均线交叉策略跑模拟盘

Agent 编排：
  1. quant_deploy (paper) → 启动模拟交易
  2. 定期检查状态和绩效
```

---

## YAML Skill 文件格式说明

每个 `.yaml` 文件包含以下字段：

```yaml
name: skill_name              # Skill 唯一标识
description: |                 # 功能描述（Agent 用来判断何时调用）
  Multi-line description...
usage: |                       # 自然语言调用示例
  "用户可能这样说..."
command: |                     # 实际执行的 shell 命令模板
  cd "{project_root}" && clawquant --json ...
parameters:                    # 参数定义
  param_name:
    type: string|integer|number
    description: "参数说明"
    required: true|false       # 是否必填
    default: "默认值"          # 可选默认值
```

---

## 常见问题

**Q: 数据拉不下来？**
A: 检查网络/代理配置（`.env` 中的 `HTTPS_PROXY`），确保能访问交易所 API。

**Q: 策略名写错了？**
A: 运行 `clawquant strategy list` 查看所有可用策略名。

**Q: 怎么查看之前的 Run ID？**
A: 查看 `runs/` 目录，或在批量回测的 JSON 输出中获取。

**Q: Live 模式安全吗？**
A: Live 模式需要显式确认（`--i-know-what-im-doing`），Agent 默认不会自动执行实盘交易。
