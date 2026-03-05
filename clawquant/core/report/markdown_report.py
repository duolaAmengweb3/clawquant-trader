"""Markdown report generation — professional, human-readable backtest reports."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List


def generate_markdown_report(
    run_dir: Path,
    metrics: Dict[str, float],
    score: Dict[str, float],
    run_meta: dict,
    trades: List[dict],
) -> Path:
    """Generate a professional Markdown report with analysis and commentary."""
    strat = run_meta.get("strategy", {})
    data = run_meta.get("data", {})
    config = run_meta.get("config", {})
    run_id = run_meta.get("run_id", "unknown")
    env = run_meta.get("environment", {})

    lines: list[str] = []
    _add = lines.append
    _ext = lines.extend

    # ── Header ──
    _add(f"# 回测报告: {strat.get('name', 'unknown')}")
    _add("")
    _add(f"> Run ID: `{run_id}`")
    _add(f"> 生成时间: {run_meta.get('timestamp', 'N/A')}")
    _add("")
    _add("---")
    _add("")

    # ── Executive Summary ──
    _add("## 概览")
    _add("")
    total_ret_pct = metrics.get("total_return_pct", 0)
    total_ret = metrics.get("total_return", 0)
    max_dd_pct = metrics.get("max_drawdown_pct", 0)
    sharpe = metrics.get("sharpe_ratio", 0)
    total_trades = metrics.get("total_trades", 0)
    win_rate = metrics.get("win_rate", 0)
    score_total = score.get("total", 0)
    bar_count = data.get("bar_count", 0)
    initial_capital = config.get("initial_capital", 10000)

    verdict = _get_verdict(total_ret_pct, max_dd_pct, sharpe, total_trades, bar_count)

    _add(f"**{strat.get('name', '')}** 策略在 **{data.get('symbol', '')}** "
         f"（{data.get('interval', '')} K线，{bar_count} 根）上的回测结果：")
    _add("")
    _add(f"| 项目 | 结果 |")
    _add(f"|------|------|")
    _add(f"| 总收益 | **{'+' if total_ret >= 0 else ''}{total_ret:.2f} USDT** ({'+' if total_ret_pct >= 0 else ''}{total_ret_pct:.2f}%) |")
    _add(f"| 最大回撤 | {max_dd_pct:.2f}% |")
    _add(f"| 稳定性评分 | **{score_total:.1f} / 100** |")
    _add(f"| 总交易次数 | {total_trades} 笔 |")
    _add(f"| 胜率 | {win_rate:.1f}% |")
    _add("")
    _add(f"**综合评价**: {verdict}")
    _add("")

    # ── Data reliability warning ──
    warnings = _generate_warnings(metrics, bar_count, total_trades, sharpe, data.get("interval", "1h"))
    if warnings:
        _add("## ⚠ 数据可靠性提示")
        _add("")
        for w in warnings:
            _add(f"- {w}")
        _add("")

    # ── Strategy Info ──
    _add("## 策略信息")
    _add("")
    _add(f"| 项目 | 值 |")
    _add(f"|------|-----|")
    _add(f"| 策略名称 | {strat.get('name', 'N/A')} |")
    _add(f"| 版本 | {strat.get('version', 'N/A')} |")
    _add(f"| 参数 | `{strat.get('params', {})}` |")
    _add("")

    # ── Data Info ──
    _add("## 数据信息")
    _add("")
    _add(f"| 项目 | 值 |")
    _add(f"|------|-----|")
    _add(f"| 交易对 | {data.get('symbol', 'N/A')} |")
    _add(f"| K线周期 | {data.get('interval', 'N/A')} |")
    _add(f"| 时间范围 | {data.get('start', 'N/A')} → {data.get('end', 'N/A')} |")
    _add(f"| K线数量 | {bar_count} |")
    _add(f"| 数据来源 | {data.get('source', 'N/A')} |")
    _add("")

    # ── Configuration ──
    _add("## 回测配置")
    _add("")
    _add(f"| 项目 | 值 |")
    _add(f"|------|-----|")
    _add(f"| 初始资金 | {initial_capital:,.2f} USDT |")
    _add(f"| 手续费 | {config.get('fee_bps', 10)} bps ({config.get('fee_bps', 10) / 100:.2f}%) |")
    _add(f"| 滑点 | {config.get('slippage_bps', 5)} bps ({config.get('slippage_bps', 5) / 100:.2f}%) |")
    _add(f"| 成交模型 | {config.get('fill_model', 'next_open')} (下一根K线开盘价) |")
    _add("")

    # ── Performance Metrics with commentary ──
    _add("## 绩效指标详解")
    _add("")

    # Returns section
    _add("### 收益类")
    _add("")
    ann_ret = metrics.get("annualized_return", 0)
    _add(f"| 指标 | 值 | 说明 |")
    _add(f"|------|-----|------|")
    _add(f"| 总收益 | {'+' if total_ret >= 0 else ''}{total_ret:.2f} USDT ({'+' if total_ret_pct >= 0 else ''}{total_ret_pct:.2f}%) | 回测期间的绝对/百分比收益 |")
    _add(f"| 年化收益 | {ann_ret:.2f}% | {_interpret_ann_return(ann_ret, bar_count, data.get('interval', '1h'))} |")
    _add(f"| 期望值 | {metrics.get('expectancy', 0):.2f} USDT/笔 | 每笔交易的平均预期收益 |")
    _add("")

    # Risk section
    _add("### 风险类")
    _add("")
    ann_vol = metrics.get("annualized_volatility", 0)
    max_dd = metrics.get("max_drawdown", 0)
    _add(f"| 指标 | 值 | 说明 |")
    _add(f"|------|-----|------|")
    _add(f"| 最大回撤 | {max_dd:.2f} USDT ({max_dd_pct:.2f}%) | {_interpret_drawdown(max_dd_pct)} |")
    _add(f"| 年化波动率 | {ann_vol:.2f}% | {_interpret_volatility(ann_vol)} |")
    _add("")

    # Risk-adjusted section
    _add("### 风险调整收益")
    _add("")
    sortino = metrics.get("sortino_ratio", 0)
    calmar = metrics.get("calmar_ratio", 0)
    pf = metrics.get("profit_factor", 0)
    _add(f"| 指标 | 值 | 说明 |")
    _add(f"|------|-----|------|")
    _add(f"| Sharpe Ratio | {sharpe:.4f} | {_interpret_sharpe(sharpe)} |")
    _add(f"| Sortino Ratio | {sortino:.4f} | {_interpret_sortino(sortino)} |")
    _add(f"| Calmar Ratio | {calmar:.4f} | 年化收益 / 最大回撤，越高越好 |")
    pf_str = "∞" if pf == float("inf") else f"{pf:.2f}"
    _add(f"| 盈亏比 (Profit Factor) | {pf_str} | {_interpret_pf(pf)} |")
    _add("")

    # Trade stats
    _add("### 交易统计")
    _add("")
    avg_pnl = metrics.get("avg_trade_pnl", 0)
    avg_bars = metrics.get("avg_bars_held", 0)
    _add(f"| 指标 | 值 |")
    _add(f"|------|-----|")
    _add(f"| 总交易笔数 | {total_trades} |")
    _add(f"| 胜率 | {win_rate:.1f}% |")
    _add(f"| 平均单笔盈亏 | {'+' if avg_pnl >= 0 else ''}{avg_pnl:.2f} USDT |")
    _add(f"| 平均持仓K线数 | {avg_bars:.1f} |")
    _add("")

    # ── Stability Score breakdown ──
    _add("## 稳定性评分详解")
    _add("")
    _add(f"### 总分: {score_total:.1f} / 100 — {_score_grade(score_total)}")
    _add("")
    _add(f"| 维度 | 权重 | 得分 | 解读 |")
    _add(f"|------|------|------|------|")
    _add(f"| 收益质量 (Quality) | 30% | {score.get('quality', 0):.1f} | {_explain_quality(score.get('quality', 0))} |")
    _add(f"| 风险控制 (Risk) | 30% | {score.get('risk', 0):.1f} | {_explain_risk(score.get('risk', 0))} |")
    _add(f"| 稳健性 (Robustness) | 20% | {score.get('robustness', 0):.1f} | {_explain_robustness(score.get('robustness', 0), total_trades)} |")
    _add(f"| 成本敏感度 (Cost) | 10% | {score.get('cost_sensitivity', 0):.1f} | {_explain_cost(score.get('cost_sensitivity', 0))} |")
    _add(f"| 交易频率 (Overtrade) | 10% | {score.get('overtrade', 0):.1f} | {_explain_overtrade(score.get('overtrade', 0))} |")
    _add("")

    # ── Key Findings ──
    _add("## 关键发现")
    _add("")
    findings = _generate_findings(metrics, score, total_trades, bar_count, data.get("interval", "1h"))
    for i, f in enumerate(findings, 1):
        _add(f"{i}. {f}")
    _add("")

    # ── Risk Warnings & Suggestions ──
    _add("## 风险提示与建议")
    _add("")
    suggestions = _generate_suggestions(metrics, score, total_trades, bar_count, data.get("interval", "1h"))
    for s in suggestions:
        _add(f"- {s}")
    _add("")

    # ── Trade table ──
    if trades:
        _add("## 交易明细")
        _add("")
        _add("| # | 开仓时间 | 平仓时间 | 方向 | 开仓价 | 平仓价 | 盈亏 (USDT) | 盈亏% |")
        _add("|---|----------|----------|------|--------|--------|-------------|-------|")
        for i, t in enumerate(trades[:30], 1):
            entry_time = str(t.get("entry_time", ""))[:16]
            exit_time = str(t.get("exit_time", ""))[:16]
            pnl = t.get("pnl", 0)
            pnl_pct = t.get("pnl_pct", 0)
            side = "做多" if t.get("side", "") == "LONG" else "做空"
            pnl_sign = "+" if pnl >= 0 else ""
            _add(
                f"| {i} | {entry_time} | {exit_time} | {side} "
                f"| {t.get('entry_price', 0):,.2f} | {t.get('exit_price', 0):,.2f} "
                f"| {pnl_sign}{pnl:.2f} | {pnl_sign}{pnl_pct:.2f}% |"
            )
        if len(trades) > 30:
            _add(f"\n*... 共 {len(trades)} 笔交易，仅显示前 30 笔*")
        _add("")

    # ── Charts ──
    _ext([
        "## 图表",
        "",
        "### 权益曲线",
        "![权益曲线](equity.png)",
        "",
        "### 回撤曲线",
        "![回撤曲线](drawdown.png)",
        "",
        "### 交易标记",
        "![交易标记](trades.png)",
        "",
    ])

    # ── Footer ──
    _ext([
        "---",
        "",
        "**免责声明**: 本报告基于历史数据回测生成，不构成任何投资建议。"
        "过去的表现不代表未来的收益。回测结果可能受到过度拟合、数据偏差等因素影响。"
        "请在实盘交易前充分了解风险。",
        "",
        f"*ClawQuant Trader v{env.get('engine_version', '0.1.0')} | "
        f"引擎: 事件驱动 | 成交模型: {config.get('fill_model', 'next_open')}*",
    ])

    report_path = run_dir / "report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


# ---------------------------------------------------------------------------
# Interpretation helpers
# ---------------------------------------------------------------------------

def _get_verdict(ret_pct: float, dd_pct: float, sharpe: float, trades: int, bars: int) -> str:
    """Generate an overall verdict."""
    if bars < 100:
        reliability = "数据量较少，结论可靠性有限。"
    elif bars < 500:
        reliability = ""
    else:
        reliability = ""

    if trades < 3:
        trade_note = "交易次数过少，统计意义不足。"
    else:
        trade_note = ""

    if ret_pct > 20 and dd_pct < 5 and sharpe > 2:
        core = "策略表现优异，收益高、回撤小、风险调整收益出色。"
    elif ret_pct > 10 and dd_pct < 10:
        core = "策略表现良好，有一定盈利能力且风险可控。"
    elif ret_pct > 0 and dd_pct < 20:
        core = "策略有正收益，但需关注回撤风险。"
    elif ret_pct > 0:
        core = "策略虽有正收益，但回撤较大，风险偏高。"
    elif ret_pct > -5:
        core = "策略基本持平，未展现明显优势。"
    else:
        core = "策略出现亏损，需要重新审视参数或策略逻辑。"

    parts = [core]
    if trade_note:
        parts.append(trade_note)
    if reliability:
        parts.append(reliability)
    return " ".join(parts)


def _generate_warnings(metrics: dict, bars: int, trades: int, sharpe: float, interval: str) -> list[str]:
    """Generate data reliability warnings."""
    warnings = []
    if bars < 50:
        warnings.append(f"K线数量仅 {bars} 根，数据量极少，回测结果不具参考价值。建议至少使用 200+ 根K线。")
    elif bars < 200:
        warnings.append(f"K线数量 {bars} 根，数据量偏少。建议增加回测时间范围以提高结果可靠性。")

    if trades < 3:
        warnings.append(f"仅 {trades} 笔交易，无法形成有效的统计分布。建议增加数据量或调整策略参数。")
    elif trades < 10:
        warnings.append(f"{trades} 笔交易偏少，统计显著性不足。建议至少 30 笔交易以获得可靠结论。")

    if sharpe > 100:
        warnings.append(f"Sharpe Ratio = {sharpe:.0f}，数值异常偏高，通常是数据量不足或回测周期过短导致的。不应作为策略优劣的判断依据。")

    ann_ret = metrics.get("annualized_return", 0)
    if abs(ann_ret) > 10000:
        warnings.append(f"年化收益率 {ann_ret:.0f}%，数值异常。这是短周期回测外推到全年的结果，不代表真实年化收益。")

    return warnings


def _interpret_ann_return(ann_ret: float, bars: int, interval: str) -> str:
    if bars < 200:
        return "短周期外推，仅供参考"
    if ann_ret > 100:
        return "极高，需结合风险指标综合判断"
    if ann_ret > 30:
        return "表现优秀"
    if ann_ret > 10:
        return "表现良好"
    if ann_ret > 0:
        return "小幅盈利"
    return "亏损"


def _interpret_drawdown(dd_pct: float) -> str:
    if dd_pct < 2:
        return "回撤极小，风险控制优秀"
    if dd_pct < 5:
        return "回撤可控，处于较低水平"
    if dd_pct < 10:
        return "回撤适中，在可接受范围"
    if dd_pct < 20:
        return "回撤较大，需注意风险管理"
    return "回撤严重，建议降低仓位或调整策略"


def _interpret_volatility(vol: float) -> str:
    if vol < 10:
        return "波动性很低，策略较为平稳"
    if vol < 30:
        return "波动性适中"
    if vol < 60:
        return "波动性较高，加密货币市场的常见水平"
    return "波动性极高，需要更严格的风控"


def _interpret_sharpe(sharpe: float) -> str:
    if sharpe > 100:
        return "数值异常（数据量不足导致），不具参考价值"
    if sharpe > 3:
        return "优异，每单位风险获得极高回报"
    if sharpe > 2:
        return "优秀"
    if sharpe > 1:
        return "良好，高于市场平均水平"
    if sharpe > 0.5:
        return "尚可，有改善空间"
    if sharpe > 0:
        return "较低，风险调整收益不理想"
    return "负值，策略亏损"


def _interpret_sortino(sortino: float) -> str:
    if sortino > 100:
        return "数值异常，不具参考价值"
    if sortino > 3:
        return "优异，下行风险极低"
    if sortino > 2:
        return "优秀"
    if sortino > 1:
        return "良好"
    return "一般"


def _interpret_pf(pf: float) -> str:
    if pf == float("inf"):
        return "无亏损交易（可能因交易次数过少）"
    if pf > 3:
        return "优秀，盈利远超亏损"
    if pf > 2:
        return "良好"
    if pf > 1.5:
        return "尚可"
    if pf > 1:
        return "微利，盈亏接近"
    return "亏损，总亏损超过总盈利"


def _score_grade(total: float) -> str:
    if total >= 90:
        return "卓越 (A+)"
    if total >= 80:
        return "优秀 (A)"
    if total >= 70:
        return "良好 (B)"
    if total >= 60:
        return "及格 (C)"
    if total >= 40:
        return "较差 (D)"
    return "不及格 (F)"


def _explain_quality(s: float) -> str:
    if s >= 80:
        return "风险调整收益优秀，策略有明显的 alpha"
    if s >= 60:
        return "收益质量良好"
    if s >= 40:
        return "收益质量一般，风险调整后收益有限"
    return "收益质量较差"


def _explain_risk(s: float) -> str:
    if s >= 80:
        return "风控优秀，回撤和波动都在低位"
    if s >= 60:
        return "风控尚可，回撤处于可接受范围"
    if s >= 40:
        return "风控一般，回撤偏大"
    return "风控较差，需要加强止损和仓位管理"


def _explain_robustness(s: float, trades: int) -> str:
    if trades < 5:
        return f"交易仅 {trades} 笔，样本不足，得分被惩罚"
    if s >= 80:
        return "胜率和盈亏比稳定，策略表现一致"
    if s >= 60:
        return "稳健性良好"
    if s >= 40:
        return "稳健性一般，表现有一定波动"
    return "稳健性差，策略可能过拟合"


def _explain_cost(s: float) -> str:
    if s >= 80:
        return "手续费对利润影响很小"
    if s >= 60:
        return "手续费影响适中"
    if s >= 40:
        return "手续费占比较高，考虑降低交易频率"
    return "手续费严重侵蚀利润"


def _explain_overtrade(s: float) -> str:
    if s >= 80:
        return "交易频率合理，持仓时间充分"
    if s >= 50:
        return "交易频率中等"
    return "交易过于频繁，可能产生不必要的成本"


def _generate_findings(metrics: dict, score: dict, trades: int, bars: int, interval: str) -> list[str]:
    """Generate key findings."""
    findings = []
    ret_pct = metrics.get("total_return_pct", 0)
    dd_pct = metrics.get("max_drawdown_pct", 0)
    wr = metrics.get("win_rate", 0)

    if ret_pct > 0:
        findings.append(f"策略在回测期间实现了 {ret_pct:.2f}% 的正收益。")
    else:
        findings.append(f"策略在回测期间亏损 {abs(ret_pct):.2f}%。")

    if dd_pct > 0:
        ratio = abs(ret_pct / dd_pct) if dd_pct > 0 else 0
        if ratio > 3:
            findings.append(f"收益/回撤比为 {ratio:.1f}:1，风险收益比优秀。")
        elif ratio > 1:
            findings.append(f"收益/回撤比为 {ratio:.1f}:1，尚可。")
        else:
            findings.append(f"收益/回撤比仅 {ratio:.1f}:1，收益不足以补偿风险。")

    if trades > 0 and wr > 70:
        findings.append(f"胜率 {wr:.1f}% 处于高位，策略的信号准确度较好。")
    elif trades > 0 and wr < 40:
        findings.append(f"胜率仅 {wr:.1f}%，策略需要较高的盈亏比来弥补低胜率。")

    # Score-based findings
    scores = [(score.get("quality", 0), "收益质量"), (score.get("risk", 0), "风险控制"),
              (score.get("robustness", 0), "稳健性")]
    best = max(scores, key=lambda x: x[0])
    worst = min(scores, key=lambda x: x[0])
    findings.append(f"最强维度: {best[1]} ({best[0]:.0f}分)，最弱维度: {worst[1]} ({worst[0]:.0f}分)。")

    return findings


def _generate_suggestions(metrics: dict, score: dict, trades: int, bars: int, interval: str) -> list[str]:
    """Generate risk warnings and actionable suggestions."""
    suggestions = []

    if bars < 200:
        suggestions.append("**增加数据量**: 当前数据量不足，建议使用 `--days 90` 或更长时间获取更多K线数据。")

    if trades < 10:
        suggestions.append("**增加交易样本**: 交易次数过少，考虑缩短K线周期（如 `--interval 15m`）或延长回测期。")

    dd_pct = metrics.get("max_drawdown_pct", 0)
    if dd_pct > 15:
        suggestions.append("**加强风控**: 最大回撤超过 15%，建议设置更严格的止损或降低单次仓位比例。")

    if score.get("cost_sensitivity", 100) < 60:
        suggestions.append("**降低交易成本**: 手续费对利润影响较大，考虑降低交易频率或使用限价单。")

    if score.get("overtrade", 100) < 50:
        suggestions.append("**减少交易频率**: 过于频繁的交易增加了成本和执行风险，考虑增加信号过滤条件。")

    if score.get("robustness", 100) < 50:
        suggestions.append("**提高稳健性**: 建议使用 `backtest sweep` 做参数敏感性分析，或 `backtest walkforward` 做走前验证。")

    ret_pct = metrics.get("total_return_pct", 0)
    if ret_pct < 0:
        suggestions.append("**策略亏损**: 该策略在当前参数和市场环境下不盈利，建议调整参数或更换策略。")

    suggestions.append("**跨周期验证**: 建议在不同时间范围和K线周期上重复回测，确认策略不是偶然有效。")
    suggestions.append("**实盘前请谨慎**: 回测不等于实盘，实际交易中可能面临流动性不足、延迟、极端行情等额外风险。")

    return suggestions
