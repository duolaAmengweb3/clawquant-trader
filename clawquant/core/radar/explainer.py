"""Radar explainer: generate human-readable explanations for opportunities."""

from __future__ import annotations

from typing import Any, Dict


def explain_opportunity(opp: Dict[str, Any]) -> Dict[str, Any]:
    """Generate an explanation for a detected opportunity.

    Args:
        opp: Opportunity dict from scanner.

    Returns:
        Dict with 'summary', 'reasons', 'risk_notes', 'action'.
    """
    symbol = opp.get("symbol", "?")
    strategy = opp.get("strategy", "?")
    direction = opp.get("direction", "?")
    confidence = opp.get("confidence", 0)
    price = opp.get("last_price", 0)
    change_24h = opp.get("price_change_24h", 0)
    accuracy = opp.get("historical_accuracy", 0)
    signal_rate = opp.get("signal_rate", 0)

    # Summary
    if direction == "BUY":
        action_word = "买入"
        action_en = "Long"
    elif direction == "SELL":
        action_word = "卖出"
        action_en = "Short/Exit"
    else:
        action_word = "观望"
        action_en = "Hold"

    summary = f"{symbol} | {strategy} 策略触发{action_word}信号 | 置信度 {confidence:.0f}%"

    # Reasons
    reasons = []
    if direction == "BUY":
        reasons.append(f"{strategy} 策略在当前价格 ${price:,.2f} 发出买入信号")
    elif direction == "SELL":
        reasons.append(f"{strategy} 策略在当前价格 ${price:,.2f} 发出卖出信号")

    if change_24h > 0:
        reasons.append(f"24h 涨幅 {change_24h:+.2f}%，处于上升趋势")
    elif change_24h < -3:
        reasons.append(f"24h 跌幅 {change_24h:+.2f}%，可能超卖反弹")
    else:
        reasons.append(f"24h 变化 {change_24h:+.2f}%，波动较小")

    if accuracy > 60:
        reasons.append(f"历史信号准确率 {accuracy:.0f}%（较高）")
    elif accuracy > 40:
        reasons.append(f"历史信号准确率 {accuracy:.0f}%（中等）")
    else:
        reasons.append(f"历史信号准确率 {accuracy:.0f}%（偏低，谨慎参考）")

    # Risk notes
    risk_notes = []
    if confidence < 40:
        risk_notes.append("置信度较低，建议小仓位试探")
    if signal_rate > 30:
        risk_notes.append(f"信号频率 {signal_rate:.0f}% 偏高，可能存在过度交易风险")
    if abs(change_24h) > 10:
        risk_notes.append("24h 波动较大，注意风控")
    if accuracy < 50:
        risk_notes.append("历史胜率不足50%，信号可靠性有限")

    if not risk_notes:
        risk_notes.append("当前无明显风险警告")

    return {
        "symbol": symbol,
        "strategy": strategy,
        "direction": direction,
        "action": action_en,
        "summary": summary,
        "reasons": reasons,
        "risk_notes": risk_notes,
        "confidence": confidence,
        "key_metrics": {
            "price": price,
            "change_24h": change_24h,
            "historical_accuracy": accuracy,
            "signal_rate": signal_rate,
        },
    }
