"""技术指标与策略评估模块。

用于为股票生成 RSI、MACD、布林带和均线分析，并对用户保存的策略作评分。
"""

from __future__ import annotations

from stock_app.market import fetch_stock_snapshot


def calculate_ema(values, period):
    """指数移动平均（EMA）。"""
    if not values or period <= 0:
        return []
    multiplier = 2.0 / (period + 1)
    result = []
    prev = None
    for value in values:
        current = float(value)
        if prev is None:
            prev = current
        else:
            prev = (current - prev) * multiplier + prev
        result.append(prev)
    return result


def calculate_rsi(values, period=14):
    """计算 RSI 指标。"""
    if len(values) <= period:
        return None
    deltas = [float(values[idx]) - float(values[idx - 1]) for idx in range(1, len(values))]
    gains = [max(delta, 0.0) for delta in deltas]
    losses = [max(-delta, 0.0) for delta in deltas]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for index in range(period, len(deltas)):
        avg_gain = ((avg_gain * (period - 1)) + gains[index]) / period
        avg_loss = ((avg_loss * (period - 1)) + losses[index]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calculate_macd(values, fast=12, slow=26, signal=9):
    """计算 MACD，并返回 macd / signal / histogram。"""
    if len(values) < slow:
        return {"macd": 0.0, "signal": 0.0, "histogram": 0.0}
    fast_ema = calculate_ema(values, fast)
    slow_ema = calculate_ema(values, slow)
    macd_line = [f - s for f, s in zip(fast_ema[-len(values):], slow_ema[-len(values):])]
    signal_line = calculate_ema(macd_line, signal)
    if not macd_line or not signal_line:
        return {"macd": 0.0, "signal": 0.0, "histogram": 0.0}
    return {
        "macd": macd_line[-1],
        "signal": signal_line[-1],
        "histogram": macd_line[-1] - signal_line[-1],
    }


def calculate_bollinger(values, period=20, std_dev=2):
    """计算布林带。"""
    if len(values) < period:
        return {"upper": None, "middle": None, "lower": None, "bandwidth": None}
    window = values[-period:]
    mean = sum(window) / len(window)
    variance = sum((value - mean) ** 2 for value in window) / len(window)
    std = variance ** 0.5
    upper = mean + std_dev * std
    lower = mean - std_dev * std
    return {
        "upper": upper,
        "middle": mean,
        "lower": lower,
        "bandwidth": (upper - lower) / mean if mean else 0.0,
    }


def build_technical_signal_summary(symbol: str):
    """汇总一只股票的技术指标状态，返回给前端展示。"""
    snapshot = fetch_stock_snapshot(symbol.lower())
    if not snapshot:
        return {"symbol": symbol, "summary": "no_data", "items": []}
    history = snapshot.get("history", [])
    closes = [float(item.get("close") or 0.0) for item in history]
    if len(closes) < 20:
        return {"symbol": symbol, "summary": "insufficient_data", "items": []}

    last_close = closes[-1]
    ma5 = sum(closes[-5:]) / 5
    ma10 = sum(closes[-10:]) / 10
    rsi = calculate_rsi(closes, 14)
    macd = calculate_macd(closes, 12, 26, 9)
    boll = calculate_bollinger(closes, 20, 2)

    signals = []
    if last_close > ma5 > ma10:
        signals.append({"name": "多头趋势", "value": "强", "tone": "up"})
    elif last_close < ma5 < ma10:
        signals.append({"name": "空头趋势", "value": "弱", "tone": "down"})
    else:
        signals.append({"name": "均线状态", "value": "震荡", "tone": "neutral"})

    if rsi is not None:
        if rsi >= 70:
            signals.append({"name": "RSI", "value": f"超买 {rsi:.1f}", "tone": "down"})
        elif rsi <= 30:
            signals.append({"name": "RSI", "value": f"超卖 {rsi:.1f}", "tone": "up"})
        else:
            signals.append({"name": "RSI", "value": f"中性 {rsi:.1f}", "tone": "neutral"})

    if macd.get("histogram") is not None:
        if macd["histogram"] > 0:
            signals.append({"name": "MACD", "value": "金叉向上", "tone": "up"})
        else:
            signals.append({"name": "MACD", "value": "死叉回落", "tone": "down"})

    if boll.get("upper") is not None:
        if last_close >= boll["upper"]:
            signals.append({"name": "布林带", "value": "偏高", "tone": "down"})
        elif last_close <= boll["lower"]:
            signals.append({"name": "布林带", "value": "偏低", "tone": "up"})
        else:
            signals.append({"name": "布林带", "value": "正常", "tone": "neutral"})

    summary = "偏强"
    up_score = sum(1 for item in signals if item["tone"] == "up")
    down_score = sum(1 for item in signals if item["tone"] == "down")
    if down_score > up_score:
        summary = "偏弱"
    elif up_score == down_score:
        summary = "震荡"

    score = max(0, min(100, 50 + (up_score - down_score) * 10))

    return {
        "symbol": symbol,
        "summary": summary,
        "score": score,
        "last_close": last_close,
        "ma5": ma5,
        "ma10": ma10,
        "rsi": rsi,
        "macd": macd,
        "bollinger": boll,
        "items": signals,
    }


def evaluate_strategy_against_signal(signal_summary: dict, strategy: dict):
    """根据当前技术信号评估单个策略的匹配程度。"""
    score = 50
    rule_text = (strategy.get("rule") or "").lower()
    description_text = (strategy.get("description") or "").lower()
    entry_text = (strategy.get("entry_condition") or "").lower()
    exit_text = (strategy.get("exit_condition") or "").lower()

    if not signal_summary or signal_summary.get("summary") in {"no_data", "insufficient_data"}:
        return {
            "strategy_id": strategy.get("id"),
            "strategy_name": strategy.get("name"),
            "score": 0,
            "grade": "弱",
            "reasons": ["缺少可用行情数据"],
        }

    ma5 = signal_summary.get("ma5")
    ma10 = signal_summary.get("ma10")
    last_close = float(signal_summary.get("last_close") or 0)
    rsi = signal_summary.get("rsi")
    macd = signal_summary.get("macd") or {}
    histogram = float(macd.get("histogram") or 0)
    bollinger = signal_summary.get("bollinger") or {}
    upper = bollinger.get("upper")
    lower = bollinger.get("lower")

    reasons = []
    if ma5 and ma10:
        if last_close > ma5 > ma10:
            score += 18
            reasons.append("价格位于短期均线上方")
        elif last_close < ma5 < ma10:
            score -= 18
            reasons.append("价格位于短期均线下方")
        else:
            reasons.append("均线状态处于震荡区间")

    if rsi is not None:
        if 45 <= rsi <= 70:
            score += 14
            reasons.append("RSI 区间偏健康")
        elif rsi > 70:
            score -= 10
            reasons.append("RSI 偏高，存在回撤风险")
        elif rsi < 30:
            score -= 10
            reasons.append("RSI 偏低，可能承压")

    if histogram > 0:
        score += 14
        reasons.append("MACD 处于上升动能")
    elif histogram < 0:
        score -= 12
        reasons.append("MACD 进入下降动能")

    if upper and lower:
        if last_close > upper:
            score -= 8
            reasons.append("价格接近布林上轨，存在回落压力")
        elif last_close < lower:
            score += 8
            reasons.append("价格接近布林下轨，存在补涨机会")
        else:
            score += 5
            reasons.append("价格位于布林带中间区间")

    keyword_hits = [
        keyword for keyword in [
            "均线", "趋势", "突破", "回调", "支撑", "压力", "买入", "卖出", "金叉", "死叉", "放量"
        ] if keyword in rule_text or keyword in description_text or keyword in entry_text or keyword in exit_text
    ]
    if keyword_hits:
        score += min(len(keyword_hits) * 2, 12)

    if strategy.get("status") == "paused":
        score -= 12
    elif strategy.get("status") == "closed":
        score -= 25

    score = max(0, min(100, int(score)))
    if score >= 80:
        grade = "强"
    elif score >= 60:
        grade = "中"
    else:
        grade = "弱"

    return {
        "strategy_id": strategy.get("id"),
        "strategy_name": strategy.get("name"),
        "score": score,
        "grade": grade,
        "reasons": reasons[:4],
    }


def calculate_portfolio_risk(portfolio_rows):
    """为持仓组合生成风险摘要：总市值、平均波动、风险等级。"""
    if not portfolio_rows:
        return {
            "total_value": 0.0,
            "total_pnl": 0.0,
            "avg_change_pct": 0.0,
            "risk_level": "低",
            "top_risk_symbol": None,
            "items": [],
        }

    total_value = 0.0
    total_pnl = 0.0
    weighted_changes = []
    risk_items = []

    for row in portfolio_rows:
        symbol = (row.get("symbol") or "").strip()
        shares = float(row.get("shares") or 0.0)
        avg_cost = float(row.get("avg_cost") or 0.0)
        snapshot = fetch_stock_snapshot(symbol.lower()) or {}
        current_price = float(snapshot.get("close") or 0.0)
        market_value = shares * current_price
        pnl = (current_price - avg_cost) * shares
        change_pct = float(snapshot.get("change_pct") or 0.0)
        total_value += market_value
        total_pnl += pnl
        weighted_changes.append(abs(change_pct) * market_value)
        risk_items.append({
            "symbol": symbol,
            "shares": shares,
            "market_value": round(market_value, 2),
            "change_pct": change_pct,
            "pnl": round(pnl, 2),
        })

    avg_change = 0.0
    if risk_items and total_value > 0:
        avg_change = sum(item["change_pct"] * item["market_value"] for item in risk_items) / total_value
    risk_level = "低"
    if abs(avg_change) >= 6.0:
        risk_level = "高"
    elif abs(avg_change) >= 3.0:
        risk_level = "中"

    top_risk = max(risk_items, key=lambda item: abs(float(item.get("change_pct") or 0.0)), default=None)
    return {
        "total_value": round(total_value, 2),
        "total_pnl": round(total_pnl, 2),
        "avg_change_pct": round(abs(avg_change) if total_value else 0.0, 2),
        "risk_level": risk_level,
        "top_risk_symbol": top_risk["symbol"] if top_risk else None,
        "items": risk_items,
    }
