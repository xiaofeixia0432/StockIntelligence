"""行情与分析模块。

本模块封装了对 `stock_stats.py` 的调用，以及前端所需的通用数据读取逻辑：
- 股票快照
- 股票搜索
- 市场概览
- 新闻查询
- 移动平均线/回测
"""

from __future__ import annotations

import json
import sqlite3
import urllib.parse
import urllib.request
from datetime import datetime

from stock_app.config import DEFAULT_DB_PATH
from stock_app.db import get_db_connection, quote_identifier
from stock_stats import (
    DEFAULT_DB_PATH as STATS_DB_PATH,
    analyze_recent_stock_trends,
    count_rows_by_date,
    count_rows_by_recent_days,
    get_drop_ratio_from_period_high,
    get_table_names,
    group_high_low_diff,
    group_open_low_drop_distribution,
    summarize_stock_db,
)


def fetch_stock_rows(symbol: str, limit: int = 30):
    """读取指定股票最近若干条行情记录。"""
    if not symbol:
        return []
    conn = sqlite3.connect(DEFAULT_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        try:
            rows = conn.execute(
                f'SELECT date, open, high, low, close, volume FROM {quote_identifier(symbol)} ORDER BY date DESC LIMIT ?',
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]
        except sqlite3.DatabaseError:
            return []
    finally:
        conn.close()


def fetch_stock_snapshot(symbol: str):
    """封装单只股票的最新快照，包括涨跌幅和历史曲线。"""
    rows = fetch_stock_rows(symbol, limit=30)
    if not rows:
        return None
    latest = rows[0]
    previous = rows[1] if len(rows) > 1 else None
    latest_close = float(latest.get("close", 0) or 0)
    previous_close = float(previous.get("close", 0) or 0) if previous else latest_close
    change_pct = ((latest_close - previous_close) / previous_close * 100) if previous_close else 0.0
    return {
        "symbol": symbol,
        "latest_date": latest.get("date"),
        "open": latest.get("open"),
        "high": latest.get("high"),
        "low": latest.get("low"),
        "close": latest.get("close"),
        "volume": latest.get("volume"),
        "change_pct": round(change_pct, 4),
        "history": list(reversed(rows)),
    }


def ensure_default_news_for_symbol(symbol: str):
    """为每个股票补一条默认新闻，确保前端有系统资讯可展示。"""
    normalized_symbol = (symbol or "").strip().upper()
    if not normalized_symbol:
        return
    conn = get_db_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM stock_news WHERE user_id IS NULL AND symbol = ? LIMIT 1",
            (normalized_symbol,),
        ).fetchone()
        if existing:
            return
        snapshot = fetch_stock_snapshot(normalized_symbol.lower())
        if not snapshot:
            return
        close_price = float(snapshot.get("close") or 0)
        sentiment = "强势" if snapshot.get("change_pct", 0) >= 0 else "承压"
        title = f"{normalized_symbol} {sentiment}，最新收盘价 {close_price:.2f}"
        content = (
            f"{normalized_symbol} 当前交易表现{sentiment}，最新收盘价为 {close_price:.2f}，"
            f"近一段时间涨跌幅 {snapshot.get('change_pct', 0):.2f}% ，建议结合量价关系、支撑位与策略规则判断。"
        )
        conn.execute(
            "INSERT INTO stock_news (user_id, symbol, title, content, source) VALUES (?, ?, ?, ?, 'system')",
            (None, normalized_symbol, title, content),
        )
        conn.commit()
    finally:
        conn.close()


def list_user_news(symbol: str = None):
    """列出系统新闻和当前用户个性化新闻，按时间倒序返回。"""
    from stock_app.db import get_current_user
    user = get_current_user()
    normalized_symbol = (symbol or "").strip().upper()
    conn = get_db_connection()
    try:
        if normalized_symbol:
            if user:
                rows = conn.execute(
                    "SELECT * FROM stock_news WHERE (user_id IS NULL OR user_id = ?) AND symbol = ? ORDER BY created_at DESC LIMIT 20",
                    (user["id"], normalized_symbol),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM stock_news WHERE user_id IS NULL AND symbol = ? ORDER BY created_at DESC LIMIT 20",
                    (normalized_symbol,),
                ).fetchall()
        else:
            if user:
                rows = conn.execute(
                    "SELECT * FROM stock_news WHERE user_id IS NULL OR user_id = ? ORDER BY created_at DESC LIMIT 40",
                    (user["id"],),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM stock_news WHERE user_id IS NULL ORDER BY created_at DESC LIMIT 40",
                ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def fetch_live_news(symbol: str):
    """拉取外部财经新闻摘要，失败时返回系统兜底内容，避免阻塞页面。"""
    normalized_symbol = (symbol or "").strip().upper()
    if not normalized_symbol:
        return []

    fallback = [
        {
            "symbol": normalized_symbol,
            "title": f"{normalized_symbol} 市场情绪观察",
            "content": f"{normalized_symbol} 近期价格波动较大，建议结合成交量、均线和支撑位判断短线风险。",
            "source": "system",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
        {
            "symbol": normalized_symbol,
            "title": f"{normalized_symbol} 资金流向提醒",
            "content": f"{normalized_symbol} 关注量价确认、均线顺势和回撤支撑，防止追高后的波动放大。",
            "source": "system",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
    ]
    encoded = urllib.parse.quote(normalized_symbol)
    try:
        url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{encoded}?modules=price,summaryProfile,financialData"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8", "ignore"))
            summary = payload.get("quoteSummary", {}).get("result", [{}])[0]
            if not summary:
                return fallback
            profile = summary.get("summaryProfile") or {}
            description = (profile.get("longBusinessSummary") or "").strip()
            if description:
                return [{
                    "symbol": normalized_symbol,
                    "title": f"{normalized_symbol} 公司概况",
                    "content": description[:250],
                    "source": "yahoo",
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }]
    except Exception:
        return fallback
    return fallback


def collect_market_overview(limit: int = 5):
    """统计涨跌幅前列和后列，形成市场概览。"""
    tables = get_table_names(DEFAULT_DB_PATH)[: max(limit * 10, 50)]
    rows = []
    for table in tables:
        snapshot = fetch_stock_snapshot(table)
        if not snapshot:
            continue
        rows.append({
            "symbol": table,
            "close": snapshot.get("close"),
            "change_pct": snapshot.get("change_pct", 0),
            "volume": snapshot.get("volume"),
        })
    rows.sort(key=lambda item: (float(item.get("change_pct") or 0.0), float(item.get("volume") or 0.0)), reverse=True)
    gainers = rows[:limit]
    losers = sorted(rows, key=lambda item: (float(item.get("change_pct") or 0.0), float(item.get("volume") or 0.0)))[:limit]
    return {"gainers": gainers, "losers": losers}


def collect_market_pulse(limit: int = 5):
    """汇总市场情绪雷达：筛出最强和最弱品种，给出简明建议。"""
    from stock_app.strategy import build_technical_signal_summary

    tables = get_table_names(DEFAULT_DB_PATH)
    items = []
    for table in tables[: max(limit * 4, 20)]:
        snapshot = fetch_stock_snapshot(table)
        if not snapshot:
            continue
        signal = build_technical_signal_summary(table)
        change_pct = float(snapshot.get("change_pct") or 0.0)
        summary = signal.get("summary") if signal else "震荡"
        score = 50 + change_pct * 10
        if summary == "偏强":
            score += 12
        elif summary == "偏弱":
            score -= 12
        elif summary == "震荡":
            score += 2
        score = max(0, min(100, int(score)))

        if score >= 70:
            tone = "up"
            recommendation = "强势偏多，适合观察回调支撑"
        elif score <= 35:
            tone = "down"
            recommendation = "弱势偏空，建议等待确认回升"
        else:
            tone = "neutral"
            recommendation = "震荡为主，先看量价确认"

        items.append({
            "symbol": table,
            "change_pct": round(change_pct, 2),
            "summary": summary,
            "score": score,
            "tone": tone,
            "recommendation": recommendation,
        })

    items.sort(key=lambda item: (item["score"], float(item["change_pct"] or 0)), reverse=True)
    top_items = items[:max(limit, 1)]
    strong_count = sum(1 for item in top_items if item["tone"] == "up")
    weak_count = sum(1 for item in top_items if item["tone"] == "down")
    if strong_count > weak_count:
        sentiment = "偏强"
    elif weak_count > strong_count:
        sentiment = "偏弱"
    else:
        sentiment = "震荡"

    return {"sentiment": sentiment, "items": top_items, "total": len(items)}


def collect_market_heat(limit: int = 6):
    """汇总市场热度：把涨跌榜、情绪雷达、热点轮动整合成一份简短建议。"""
    overview = collect_market_overview(limit=max(limit, 6))
    pulse = collect_market_pulse(limit=max(limit, 6))
    gainers = overview.get("gainers", [])[:limit]
    losers = overview.get("losers", [])[:limit]
    leaders = pulse.get("items", [])[:limit]

    return {
        "sentiment": pulse.get("sentiment", "震荡"),
        "gainers": gainers,
        "losers": losers,
        "leaders": leaders,
        "hot_items": [
            {"symbol": item.get("symbol"), "score": item.get("score"), "summary": item.get("summary"), "change_pct": item.get("change_pct")}
            for item in leaders
        ],
    }


def calculate_moving_average(values, period):
    """简单移动平均。"""
    if not values:
        return []
    result = []
    for index in range(len(values)):
        if index + 1 < period:
            result.append(None)
        else:
            window = values[index - period + 1:index + 1]
            result.append(sum(window) / len(window))
    return result


def run_backtest(symbol: str, fast_period: int = 5, slow_period: int = 10):
    """一个简单的均线策略回测，适合演示。"""
    snapshot = fetch_stock_snapshot(symbol)
    if not snapshot:
        return {"symbol": symbol, "trades": 0, "net_return": 0.0, "final_value": 0.0, "result": "no_data"}

    history = snapshot.get("history", [])
    if len(history) < max(fast_period, slow_period):
        return {"symbol": symbol, "trades": 0, "net_return": 0.0, "final_value": 0.0, "result": "insufficient_data"}

    closes = [float(item.get("close") or 0.0) for item in history]
    fast_ma = calculate_moving_average(closes, fast_period)
    slow_ma = calculate_moving_average(closes, slow_period)

    cash = 10000.0
    position = 0.0
    trades = 0
    for index in range(len(history)):
        fast_val = fast_ma[index]
        slow_val = slow_ma[index]
        close_val = closes[index]
        if fast_val is None or slow_val is None or close_val <= 0:
            continue
        if fast_val > slow_val and position <= 0:
            position = cash / close_val
            cash = 0.0
            trades += 1
        elif fast_val < slow_val and position > 0:
            cash = position * close_val
            position = 0.0
            trades += 1

    final_value = cash + position * closes[-1]
    net_return = ((final_value - 10000.0) / 10000.0) * 100.0
    return {
        "symbol": symbol,
        "fast_period": fast_period,
        "slow_period": slow_period,
        "trades": trades,
        "net_return": round(net_return, 2),
        "initial_value": 10000.0,
        "final_value": round(final_value, 2),
        "result": "ok",
    }


# 兼容原有 `stock_web.py` 对 stock_stats 的直接使用
__all__ = [
    "DEFAULT_DB_PATH",
    "STATS_DB_PATH",
    "analyze_recent_stock_trends",
    "count_rows_by_date",
    "count_rows_by_recent_days",
    "get_drop_ratio_from_period_high",
    "get_table_names",
    "group_high_low_diff",
    "group_open_low_drop_distribution",
    "summarize_stock_db",
    "fetch_stock_rows",
    "fetch_stock_snapshot",
    "ensure_default_news_for_symbol",
    "list_user_news",
    "fetch_live_news",
    "collect_market_overview",
    "calculate_moving_average",
    "run_backtest",
]
