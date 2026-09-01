"""HTTP 路由层。

这里集中保存所有 Flask API 与页面入口，保证业务逻辑按功能拆分到其他模块，
路由只负责接收请求、调用服务、返回 JSON/模板。
"""

from __future__ import annotations

import csv
import io
import logging
import multiprocessing as mp
import os
import smtplib
import sys
import threading
import time
from datetime import datetime
from email.header import Header
from email.mime.text import MIMEText

from flask import jsonify, render_template, request, send_file, session

from stock_app.app import app
from stock_app.config import DEFAULT_DB_PATH
from stock_app.db import (
    delete_user_stock_alert,
    get_current_user,
    get_db_connection,
    get_user_email_config,
    get_user_preferences,
    get_user_stock_alerts,
    init_app_db,
    record_alert_event,
    require_login,
    save_user_email_config,
    save_user_preferences,
    save_user_stock_alert,
)
from stock_app.market import (
    collect_market_heat,
    collect_market_overview,
    collect_market_pulse,
    ensure_default_news_for_symbol,
    fetch_live_news,
    fetch_stock_snapshot,
    get_drop_ratio_from_period_high,
    get_table_names,
    group_high_low_diff,
    group_open_low_drop_distribution,
    list_user_news,
    run_backtest,
    summarize_stock_db,
)
from stock_app.market import (
    analyze_recent_stock_trends,
    count_rows_by_date,
    count_rows_by_recent_days,
)
from stock_app.strategy import (
    build_technical_signal_summary,
    calculate_portfolio_risk,
    evaluate_strategy_against_signal,
)
from werkzeug.security import generate_password_hash, check_password_hash


@app.before_request
def ensure_db_ready():
    """每次请求前，确保应用数据库已准备好。"""
    init_app_db()


def ok(payload=None):
    response = {"success": True}
    if payload is not None:
        response["data"] = payload
    return jsonify(response)


def error(message: str, status_code: int = 400):
    return jsonify({"success": False, "error": message}), status_code


def period_to_days(period: str) -> int:
    mapping = {"3m": 90, "6m": 180, "1y": 365}
    return mapping.get((period or "3m").lower(), 90)


def period_label(period: str) -> str:
    labels = {"3m": "3个月", "6m": "6个月", "1y": "1年"}
    return labels.get((period or "3m").lower(), "3个月")


def get_period_low(symbol: str, period: str):
    symbol = (symbol or "").strip().lower()
    if not symbol:
        return None
    days = period_to_days(period)
    conn = get_db_connection()
    try:
        table = symbol
        try:
            row = conn.execute(
                f"SELECT MIN(low) AS low_price FROM \"{table}\" WHERE date >= date('now', '-{days} days')",
            ).fetchone()
            if row and row["low_price"] is not None:
                return float(row["low_price"])
            rows = conn.execute(
                f"SELECT low FROM \"{table}\" ORDER BY date DESC LIMIT 365",
            ).fetchall()
            if not rows:
                return None
            low_values = [float(item["low"]) for item in rows if item["low"] is not None]
            return min(low_values) if low_values else None
        except Exception:
            return None
    finally:
        conn.close()


def send_email_alert(user_id: int, symbol: str, period: str, current_price: float, threshold_price: float):
    config = get_user_email_config(user_id)
    if not int(config.get("enabled") or 0):
        return False
    sender_email = (config.get("sender_email") or "").strip()
    recipient_email = (config.get("recipient_email") or "").strip()
    smtp_host = (config.get("smtp_host") or "").strip()
    smtp_username = (config.get("smtp_username") or "").strip()
    smtp_password = (config.get("smtp_password") or "").strip()
    if not smtp_host or not sender_email or not recipient_email or not smtp_username or not smtp_password:
        return False
    message = MIMEText(
        (
            f"股票预警提醒：{symbol.upper()} 在{period_label(period)}周期内触及最低价。\n"
            f"当前价格：{current_price:.2f}\n"
            f"周期最低价：{threshold_price:.2f}\n"
            f"请注意关注后续走势并及时处理。"
        ),
        "plain",
        "utf-8",
    )
    message["Subject"] = Header(f"[股票预警]{symbol.upper()} 达到 {period_label(period)} 最低价", "utf-8")
    message["From"] = sender_email
    message["To"] = recipient_email
    try:
        smtp_port = int(config.get("smtp_port") or 465)
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
            if int(config.get("use_tls") or 1):
                server.starttls()
        server.login(smtp_username, smtp_password)
        server.sendmail(sender_email, [recipient_email], message.as_string())
        server.quit()
        return True
    except Exception:
        return False


def evaluate_active_alerts():
    """扫描所有开启的股票预警，发现触达周期最低价时发送邮件并记录事件。"""
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM stock_alerts WHERE enabled = 1 ORDER BY updated_at DESC",
        ).fetchall()
    finally:
        conn.close()

    for row in rows:
        symbol = row["symbol"]
        period = row["period"]
        user_id = row["user_id"]
        snapshot = fetch_stock_snapshot(symbol.lower())
        if not snapshot:
            continue
        current_price = float(snapshot.get("close") or 0)
        threshold_price = get_period_low(symbol, period)
        if threshold_price is None:
            continue
        if current_price > threshold_price:
            continue
        last_triggered = row["last_triggered_at"]
        if last_triggered:
            try:
                last_dt = datetime.strptime(last_triggered, "%Y-%m-%d %H:%M:%S")
                if (datetime.now() - last_dt).total_seconds() < 3600:
                    continue
            except Exception:
                pass
        sent = send_email_alert(user_id, symbol, period, current_price, threshold_price)
        if sent:
            conn = get_db_connection()
            try:
                conn.execute(
                    "UPDATE stock_alerts SET last_triggered_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (row["id"],),
                )
                conn.commit()
            finally:
                conn.close()
            record_alert_event(user_id, symbol, period, current_price, threshold_price, f"{symbol.upper()} 达到 {period_label(period)} 最低价提醒")


logger = logging.getLogger("stock_alert_monitor")


def _alert_worker_entry():
    """子进程入口，避免 spawn 模式重复拉起监控器。"""
    os.environ["STOCK_ALERT_PROCESS"] = "1"
    run_alert_monitor()


def run_alert_monitor():
    """后台进程：每分钟扫描一次启用中的股票预警。"""
    while True:
        try:
            evaluate_active_alerts()
        except Exception:
            logger.exception("股票预警监控循环异常，准备继续重试")
        time.sleep(60)


_alert_monitor_lock = threading.Lock()
_alert_monitor_process = None
_alert_monitor_watchdog = None


def _monitor_watchdog_loop():
    """守护线程：监控子进程健康状态，进程退出时自动重启。"""
    global _alert_monitor_process
    while True:
        if _alert_monitor_process is None or not _alert_monitor_process.is_alive():
            logger.warning("股票预警子进程已退出，准备重启")
            if _alert_monitor_process is not None and _alert_monitor_process.pid is not None:
                try:
                    _alert_monitor_process.close()
                except Exception:
                    pass
            process = mp.get_context("spawn").Process(target=run_alert_monitor, name="stock-alert-monitor")
            process.daemon = True
            process.start()
            _alert_monitor_process = process
        time.sleep(10)


def start_alert_monitor():
    """启动进程隔离的预警监控器，并保留守护线程做兜底重启。"""
    global _alert_monitor_process, _alert_monitor_watchdog
    if sys.platform == "win32":
        logger.warning("Windows 环境下不启动 multiprocessing 子进程，回退到线程模式")
        if _alert_monitor_watchdog is None or not _alert_monitor_watchdog.is_alive():
            watchdog = threading.Thread(target=run_alert_monitor, name="stock-alert-monitor", daemon=True)
            watchdog.start()
            _alert_monitor_watchdog = watchdog
        return _alert_monitor_watchdog

    with _alert_monitor_lock:
        if _alert_monitor_process is not None and _alert_monitor_process.is_alive():
            return _alert_monitor_process

        if _alert_monitor_watchdog is None or not _alert_monitor_watchdog.is_alive():
            watchdog = threading.Thread(target=_monitor_watchdog_loop, name="stock-alert-monitor-watchdog", daemon=True)
            watchdog.start()
            _alert_monitor_watchdog = watchdog

        ctx = mp.get_context("fork")
        process = ctx.Process(target=_alert_worker_entry, name="stock-alert-monitor")
        process.daemon = True
        process.start()
        _alert_monitor_process = process
        return _alert_monitor_process


def build_report_snapshot(user=None):
    """构建一份用于导出和展示的分析简报。"""
    tables = get_table_names(DEFAULT_DB_PATH)
    market = collect_market_overview(limit=5)
    pulse = collect_market_pulse(limit=5)
    summary = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stock_count": len(tables),
        "market_sentiment": pulse.get("sentiment", "震荡"),
        "gainers": market.get("gainers", [])[:5],
        "losers": market.get("losers", [])[:5],
        "pulse": pulse.get("items", [])[:5],
        "portfolio": [],
        "strategies": [],
    }

    if user is None:
        return summary

    conn = get_db_connection()
    try:
        portfolio_rows = conn.execute(
            "SELECT * FROM portfolio WHERE user_id = ? ORDER BY updated_at DESC",
            (user["id"],),
        ).fetchall()
        strategy_rows = conn.execute(
            "SELECT * FROM stock_strategies WHERE user_id = ? ORDER BY updated_at DESC",
            (user["id"],),
        ).fetchall()
    finally:
        conn.close()

    portfolio_items = []
    portfolio_value = 0.0
    portfolio_pnl = 0.0
    for row in portfolio_rows:
        snapshot = fetch_stock_snapshot(row["symbol"].lower())
        current_price = float(snapshot["close"]) if snapshot and snapshot.get("close") is not None else 0.0
        market_value = float(row["shares"]) * current_price
        pnl = (current_price - float(row["avg_cost"])) * float(row["shares"])
        portfolio_value += market_value
        portfolio_pnl += pnl
        portfolio_items.append({
            "symbol": row["symbol"],
            "shares": float(row["shares"]),
            "avg_cost": float(row["avg_cost"]),
            "market_value": round(market_value, 2),
            "pnl": round(pnl, 2),
        })

    for row in strategy_rows:
        signal_summary = build_technical_signal_summary(row["symbol"])
        score_result = evaluate_strategy_against_signal(signal_summary, dict(row))
        summary["strategies"].append({
            "symbol": row["symbol"],
            "name": row["name"],
            "status": row["status"],
            "score": score_result.get("score", 0),
            "grade": score_result.get("grade", "弱"),
        })

    summary["portfolio"] = portfolio_items
    summary["portfolio_total_value"] = round(portfolio_value, 2)
    summary["portfolio_total_pnl"] = round(portfolio_pnl, 2)
    return summary


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/login")
def login_page():
    return render_template("auth.html", mode="login")


@app.route("/register")
def register_page():
    return render_template("auth.html", mode="register")


@app.route("/api/health")
def api_health():
    return ok({"status": "ok", "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})


@app.route("/api/report/summary")
def api_report_summary():
    try:
        user = get_current_user()
        payload = build_report_snapshot(user)
        return ok(payload)
    except Exception as exc:
        return error(f"生成分析简报失败: {exc}")


@app.route("/api/report/export")
def api_report_export():
    try:
        user = require_login()
        snapshot = build_report_snapshot(user)
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["category", "name", "value"])
        writer.writerow(["generated_at", "时间", snapshot.get("generated_at", "")])
        writer.writerow(["stock_count", "股票数量", snapshot.get("stock_count", 0)])
        writer.writerow(["market_sentiment", "市场情绪", snapshot.get("market_sentiment", "震荡")])
        writer.writerow(["portfolio_total_value", "总市值", snapshot.get("portfolio_total_value", 0)])
        writer.writerow(["portfolio_total_pnl", "总盈亏", snapshot.get("portfolio_total_pnl", 0)])
        for item in snapshot.get("gainers", []):
            writer.writerow(["gainer", item.get("symbol", ""), item.get("change_pct", 0)])
        for item in snapshot.get("losers", []):
            writer.writerow(["loser", item.get("symbol", ""), item.get("change_pct", 0)])
        for item in snapshot.get("portfolio", []):
            writer.writerow(["portfolio", item.get("symbol", ""), f"{item.get('market_value',0)}|{item.get('pnl',0)}|{item.get('shares',0)}"]) 
        for item in snapshot.get("strategies", []):
            writer.writerow(["strategy", item.get("symbol", ""), f"{item.get('name','')}|{item.get('score',0)}|{item.get('grade','')}"])
        payload = buffer.getvalue().encode("utf-8")
        return send_file(
            io.BytesIO(payload),
            mimetype="text/csv",
            as_attachment=True,
            download_name="stock_report.csv",
        )
    except PermissionError as exc:
        return error(str(exc), 401)
    except Exception as exc:
        return error(f"导出分析报告失败: {exc}")


@app.route("/api/tables")
def api_tables():
    try:
        tables = get_table_names(DEFAULT_DB_PATH)
        return ok({"tables": tables})
    except Exception as exc:
        return error(f"获取股票表失败: {exc}")


@app.route("/api/summary")
def api_summary():
    try:
        stats = summarize_stock_db(DEFAULT_DB_PATH, limit=20)
        return ok({"stats": stats})
    except Exception as exc:
        return error(f"统计数据库概览失败: {exc}")


@app.route("/api/date-summary")
def api_date_summary():
    target_date = request.args.get("date") or datetime.now().strftime("%Y-%m-%d")
    try:
        matches = count_rows_by_date(DEFAULT_DB_PATH, target_date, limit=200)
        return ok({"date": target_date, "matches": matches})
    except Exception as exc:
        return error(f"统计指定日期失败: {exc}")


@app.route("/api/recent-days")
def api_recent_days():
    try:
        days = int(request.args.get("days", "7"))
        end_date = request.args.get("end_date")
        payload = count_rows_by_recent_days(DEFAULT_DB_PATH, days, end_date=end_date, limit=200)
        return ok(payload)
    except ValueError:
        return error("days 参数必须是整数")
    except Exception as exc:
        return error(f"统计最近日期范围失败: {exc}")


@app.route("/api/drop-ratio")
def api_drop_ratio():
    try:
        days = request.args.get("days", type=int)
        table_name = request.args.get("table")
        end_date = request.args.get("end_date")
        payload = get_drop_ratio_from_period_high(DEFAULT_DB_PATH, days=days, end_date=end_date, table_name=table_name)
        return ok(payload)
    except Exception as exc:
        return error(f"统计跌幅失败: {exc}")


@app.route("/api/diff-group")
def api_diff_group():
    try:
        days = request.args.get("days", type=int)
        step = float(request.args.get("step", "1.0"))
        table_name = request.args.get("table")
        end_date = request.args.get("end_date")
        payload = group_high_low_diff(DEFAULT_DB_PATH, days=days, end_date=end_date, step=step, table_name=table_name)
        return ok(payload)
    except ValueError as exc:
        return error(str(exc))
    except Exception as exc:
        return error(f"统计高低差分组失败: {exc}")


@app.route("/api/open-low")
def api_open_low():
    try:
        days = request.args.get("days", type=int)
        step = float(request.args.get("step", "5.0"))
        table_name = request.args.get("table")
        end_date = request.args.get("end_date")
        payload = group_open_low_drop_distribution(DEFAULT_DB_PATH, days=days, end_date=end_date, step=step, table_name=table_name)
        return ok(payload)
    except ValueError as exc:
        return error(str(exc))
    except Exception as exc:
        return error(f"统计开盘价-最低价跌幅失败: {exc}")


@app.route("/api/trends")
def api_trends():
    try:
        days = int(request.args.get("days", "30"))
        diff_step = float(request.args.get("diff_step", "1.0"))
        drop_step = float(request.args.get("drop_step", "5.0"))
        table_name = request.args.get("table")
        end_date = request.args.get("end_date")
        payload = analyze_recent_stock_trends(
            DEFAULT_DB_PATH,
            days,
            end_date=end_date,
            diff_step=diff_step,
            drop_step=drop_step,
            table_name=table_name,
        )
        return ok(payload)
    except ValueError as exc:
        return error(str(exc))
    except Exception as exc:
        return error(f"综合趋势分析失败: {exc}")


@app.route("/api/profile", methods=["GET", "POST"])
def api_profile():
    user = get_current_user()
    if not user:
        return error("请先登录", 401)

    if request.method == "GET":
        return ok(get_user_preferences(user["id"]))

    try:
        payload = request.get_json(silent=True) or {}
        default_symbol = str(payload.get("default_symbol") or "bj920000").strip().lower()
        refresh_interval = int(payload.get("refresh_interval") or 60)
        alert_threshold = float(payload.get("alert_threshold") or 5.0)
        preferences = save_user_preferences(
            user["id"],
            default_symbol=default_symbol,
            refresh_interval=refresh_interval,
            alert_threshold=alert_threshold,
        )
        return ok(preferences)
    except (TypeError, ValueError):
        return error("个人设置参数不合法")


@app.route("/api/auth/register", methods=["POST"])
def api_register():
    try:
        payload = request.get_json(silent=True) or {}
        username = (payload.get("username") or "").strip()
        password = payload.get("password") or ""
        if not username or not password:
            return error("用户名与密码不能为空")
        if len(username) < 3 or len(password) < 6:
            return error("用户名至少 3 位，密码至少 6 位")
        conn = get_db_connection()
        try:
            row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
            if row:
                return error("用户名已存在")
            conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, generate_password_hash(password)),
            )
            conn.commit()
            user_id = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()[0]
            session["user_id"] = user_id
            return ok({"user": {"id": user_id, "username": username}})
        finally:
            conn.close()
    except Exception as exc:
        return error(f"注册失败: {exc}")


@app.route("/api/auth/login", methods=["POST"])
def api_login():
    try:
        payload = request.get_json(silent=True) or {}
        username = (payload.get("username") or "").strip()
        password = payload.get("password") or ""
        if not username or not password:
            return error("用户名和密码不能为空")
        conn = get_db_connection()
        try:
            row = conn.execute("SELECT id, username, password_hash FROM users WHERE username = ?", (username,)).fetchone()
            if not row or not check_password_hash(row["password_hash"], password):
                return error("用户名或密码不正确")
            session["user_id"] = row["id"]
            return ok({"user": {"id": row["id"], "username": row["username"]}})
        finally:
            conn.close()
    except Exception as exc:
        return error(f"登录失败: {exc}")


@app.route("/api/auth/logout", methods=["POST"])
def api_logout():
    session.clear()
    return ok({"message": "已退出登录"})


@app.route("/api/auth/me")
def api_me():
    user = get_current_user()
    preferences = get_user_preferences(user["id"]) if user else {}
    return ok({"user": user, "preferences": preferences})


@app.route("/api/stock/search")
def api_stock_search():
    try:
        keyword = (request.args.get("keyword") or request.args.get("q") or "").strip().lower()
        tables = get_table_names(DEFAULT_DB_PATH)
        if keyword:
            tables = [symbol for symbol in tables if keyword in symbol.lower()]
        items = []
        for symbol in tables[:200]:
            snapshot = fetch_stock_snapshot(symbol)
            if not snapshot:
                continue
            items.append({
                "symbol": symbol,
                "latest_date": snapshot.get("latest_date"),
                "close": snapshot.get("close"),
                "change_pct": snapshot.get("change_pct"),
                "high": snapshot.get("high"),
                "low": snapshot.get("low"),
                "volume": snapshot.get("volume"),
            })
        return ok({"items": items[:20]})
    except Exception as exc:
        return error(f"股票查询失败: {exc}")


@app.route("/api/stock/<symbol>")
def api_stock_detail(symbol: str):
    try:
        symbol = symbol.strip().upper()
        snapshot = fetch_stock_snapshot(symbol.lower())
        if not snapshot:
            return error(f"未找到股票: {symbol}", 404)
        strategy_rows = []
        user = get_current_user()
        if user:
            conn = get_db_connection()
            try:
                strategy_rows = conn.execute(
                    "SELECT * FROM stock_strategies WHERE user_id = ? AND symbol = ? ORDER BY updated_at DESC",
                    (user["id"], symbol.upper()),
                ).fetchall()
            finally:
                conn.close()
        return ok({
            "symbol": symbol,
            "snapshot": snapshot,
            "strategies": [dict(row) for row in strategy_rows],
            "signals": build_technical_signal_summary(symbol),
        })
    except Exception as exc:
        return error(f"获取股票详情失败: {exc}")


@app.route("/api/stock/<symbol>/signals")
def api_stock_signals(symbol: str):
    try:
        symbol = symbol.strip().upper()
        payload = build_technical_signal_summary(symbol)
        if payload.get("summary") == "no_data":
            return error(f"未找到股票: {symbol}", 404)
        if payload.get("summary") == "insufficient_data":
            return error(f"{symbol} 数据不足，无法计算技术信号", 400)
        return ok({"symbol": symbol, "signals": payload})
    except Exception as exc:
        return error(f"计算技术信号失败: {exc}")


@app.route("/api/stock/<symbol>/backtest")
def api_stock_backtest(symbol: str):
    try:
        symbol = (symbol or "").strip().upper()
        fast_period = int(request.args.get("fast_period", "5"))
        slow_period = int(request.args.get("slow_period", "10"))
        if fast_period <= 0 or slow_period <= 0:
            return error("均线周期必须大于 0")
        result = run_backtest(symbol.lower(), fast_period=fast_period, slow_period=slow_period)
        return ok({"backtest": result})
    except Exception as exc:
        return error(f"策略回测失败: {exc}")


@app.route("/api/news", methods=["GET", "POST"])
def api_news():
    try:
        if request.method == "POST":
            user = require_login()
            payload = request.get_json(silent=True) or {}
            symbol = (payload.get("symbol") or "").strip()
            title = (payload.get("title") or "").strip()
            content = (payload.get("content") or "").strip()
            source = (payload.get("source") or "custom").strip() or "custom"
            if not symbol or not title or not content:
                return error("股票代码、标题和内容不能为空")
            conn = get_db_connection()
            try:
                conn.execute(
                    "INSERT INTO stock_news (user_id, symbol, title, content, source) VALUES (?, ?, ?, ?, ?)",
                    (user["id"], symbol.upper(), title, content, source),
                )
                conn.commit()
                row = conn.execute(
                    "SELECT * FROM stock_news WHERE id = ?",
                    (conn.execute("SELECT last_insert_rowid() AS id").fetchone()[0],),
                ).fetchone()
                return ok({"item": dict(row)})
            finally:
                conn.close()

        symbol = (request.args.get("symbol") or "").strip().upper()
        tables = get_table_names(DEFAULT_DB_PATH)
        if symbol:
            tables = [table for table in tables if table.upper() == symbol.upper()]
        else:
            tables = tables[:50]
        for table in tables:
            ensure_default_news_for_symbol(table)
        items = list_user_news(symbol if symbol else None)
        live_items = fetch_live_news(symbol) if symbol else []
        merged = (live_items + items)[:8]
        return ok({"items": merged})
    except PermissionError as exc:
        return error(str(exc), 401)
    except Exception as exc:
        return error(f"获取股票新闻失败: {exc}")


@app.route("/api/stocks/screen")
def api_stock_screen():
    """智能股票筛选：按照涨跌幅、技术评分和趋势方向过滤候选股票。"""
    try:
        min_change = float(request.args.get("min_change", "0.0") or 0.0)
        min_score = float(request.args.get("min_score", "60.0") or 60.0)
        signal_filter = (request.args.get("signal") or "").strip().lower()
        items = []
        for table in get_table_names(DEFAULT_DB_PATH)[:200]:
            snapshot = fetch_stock_snapshot(table)
            if not snapshot:
                continue
            change_pct = float(snapshot.get("change_pct") or 0.0)
            if change_pct < min_change:
                continue
            signal_summary = build_technical_signal_summary(table)
            if not signal_summary or signal_summary.get("summary") in {"no_data", "insufficient_data"}:
                continue
            summary = signal_summary.get("summary", "震荡")
            score = int(signal_summary.get("score", 50))
            if score < min_score:
                continue
            if signal_filter and signal_filter not in summary.lower():
                continue
            focus = "均线/动量"
            if summary == "偏强":
                focus = "趋势承接"
            elif summary == "偏弱":
                focus = "回撤控制"
            items.append({
                "symbol": table,
                "close": snapshot.get("close"),
                "change_pct": change_pct,
                "summary": summary,
                "score": score,
                "signal_summary": summary,
                "focus": focus,
            })
        items.sort(key=lambda entry: (entry["score"], entry["change_pct"]), reverse=True)
        return ok({"items": items[:12]})
    except ValueError:
        return error("min_change 和 min_score 必须为数值")
    except Exception as exc:
        return error(f"智能筛选失败: {exc}")


@app.route("/api/market/overview")
def api_market_overview():
    try:
        return ok(collect_market_overview(limit=5))
    except Exception as exc:
        return error(f"获取市场概览失败: {exc}")


@app.route("/api/market/pulse")
def api_market_pulse():
    try:
        limit = int(request.args.get("limit", "5"))
        return ok(collect_market_pulse(limit=limit))
    except ValueError:
        return error("limit 参数必须是整数")
    except Exception as exc:
        return error(f"获取市场情绪雷达失败: {exc}")


@app.route("/api/market/heat")
def api_market_heat():
    try:
        limit = int(request.args.get("limit", "6"))
        return ok(collect_market_heat(limit=limit))
    except ValueError:
        return error("limit 参数必须为整数")
    except Exception as exc:
        return error(f"获取市场热度失败: {exc}")


@app.route("/api/strategies", methods=["GET", "POST"]) 
def api_strategies():
    try:
        user = require_login()
        if request.method == "GET":
            symbol = (request.args.get("symbol") or "").strip().upper()
            conn = get_db_connection()
            try:
                if symbol:
                    rows = conn.execute(
                        "SELECT * FROM stock_strategies WHERE user_id = ? AND symbol = ? ORDER BY updated_at DESC",
                        (user["id"], symbol),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM stock_strategies WHERE user_id = ? ORDER BY updated_at DESC",
                        (user["id"],),
                    ).fetchall()
                return ok({"items": [dict(row) for row in rows]})
            finally:
                conn.close()

        payload = request.get_json(silent=True) or {}
        symbol = (payload.get("symbol") or "").strip().upper()
        name = (payload.get("name") or "").strip()
        description = (payload.get("description") or "").strip()
        rule = (payload.get("rule") or "").strip()
        entry_condition = (payload.get("entry_condition") or "").strip()
        exit_condition = (payload.get("exit_condition") or "").strip()
        status = (payload.get("status") or "active").strip() or "active"
        if not symbol or not name:
            return error("股票代码和策略名称不能为空")
        conn = get_db_connection()
        try:
            conn.execute(
                """
                INSERT INTO stock_strategies (user_id, symbol, name, description, rule, entry_condition, exit_condition, status, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, symbol, name) DO UPDATE SET
                    description = excluded.description,
                    rule = excluded.rule,
                    entry_condition = excluded.entry_condition,
                    exit_condition = excluded.exit_condition,
                    status = excluded.status,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (user["id"], symbol, name, description, rule, entry_condition, exit_condition, status),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM stock_strategies WHERE user_id = ? AND symbol = ? AND name = ?",
                (user["id"], symbol, name),
            ).fetchone()
            return ok({"item": dict(row)})
        finally:
            conn.close()
    except PermissionError as exc:
        return error(str(exc), 401)
    except Exception as exc:
        return error(f"保存策略失败: {exc}")


@app.route("/api/strategies/score")
def api_strategy_score():
    try:
        user = require_login()
        symbol = (request.args.get("symbol") or "").strip().upper()
        if not symbol:
            return error("股票代码不能为空")
        conn = get_db_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM stock_strategies WHERE user_id = ? AND symbol = ? ORDER BY updated_at DESC",
                (user["id"], symbol),
            ).fetchall()
        finally:
            conn.close()
        signal_summary = build_technical_signal_summary(symbol)
        items = [evaluate_strategy_against_signal(signal_summary, dict(row)) for row in rows]
        return ok({"symbol": symbol, "signals": signal_summary, "items": items})
    except PermissionError as exc:
        return error(str(exc), 401)
    except Exception as exc:
        return error(f"策略评分失败: {exc}")


@app.route("/api/strategies/<int:strategy_id>", methods=["DELETE"])
def api_delete_strategy(strategy_id: int):
    try:
        user = require_login()
        conn = get_db_connection()
        try:
            row = conn.execute(
                "SELECT id FROM stock_strategies WHERE id = ? AND user_id = ?",
                (strategy_id, user["id"]),
            ).fetchone()
            if not row:
                return error("策略不存在或无权限删除", 404)
            conn.execute("DELETE FROM stock_strategies WHERE id = ?", (strategy_id,))
            conn.commit()
            return ok({"deleted_id": strategy_id})
        finally:
            conn.close()
    except PermissionError as exc:
        return error(str(exc), 401)
    except Exception as exc:
        return error(f"删除策略失败: {exc}")


@app.route("/api/watchlist", methods=["GET", "POST"])
def api_watchlist():
    try:
        user = require_login()
        if request.method == "GET":
            conn = get_db_connection()
            try:
                rows = conn.execute(
                    "SELECT * FROM watchlist WHERE user_id = ? ORDER BY created_at DESC",
                    (user["id"],),
                ).fetchall()
                return ok({"items": [dict(row) for row in rows]})
            finally:
                conn.close()

        payload = request.get_json(silent=True) or {}
        symbol = (payload.get("symbol") or "").strip().upper()
        note = (payload.get("note") or "").strip()
        if not symbol:
            return error("股票代码不能为空")
        conn = get_db_connection()
        try:
            conn.execute(
                "INSERT INTO watchlist (user_id, symbol, note) VALUES (?, ?, ?) ON CONFLICT(user_id, symbol) DO UPDATE SET note = excluded.note",
                (user["id"], symbol, note),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM watchlist WHERE user_id = ? AND symbol = ?",
                (user["id"], symbol),
            ).fetchone()
            return ok({"item": dict(row)})
        finally:
            conn.close()
    except PermissionError as exc:
        return error(str(exc), 401)
    except Exception as exc:
        return error(f"修改自选股失败: {exc}")


@app.route("/api/watchlist/<symbol>", methods=["DELETE"])
def api_delete_watchlist(symbol: str):
    try:
        user = require_login()
        symbol = (symbol or "").strip().upper()
        conn = get_db_connection()
        try:
            conn.execute("DELETE FROM watchlist WHERE user_id = ? AND symbol = ?", (user["id"], symbol))
            conn.commit()
            return ok({"deleted_symbol": symbol})
        finally:
            conn.close()
    except PermissionError as exc:
        return error(str(exc), 401)
    except Exception as exc:
        return error(f"删除自选股失败: {exc}")


@app.route("/api/portfolio", methods=["GET", "POST"])
def api_portfolio():
    try:
        user = require_login()
        if request.method == "GET":
            conn = get_db_connection()
            try:
                rows = conn.execute(
                    "SELECT * FROM portfolio WHERE user_id = ? ORDER BY updated_at DESC",
                    (user["id"],),
                ).fetchall()
                items = []
                for row in rows:
                    snapshot = fetch_stock_snapshot(row["symbol"].lower())
                    current_price = float(snapshot["close"]) if snapshot and snapshot.get("close") is not None else 0.0
                    market_value = float(row["shares"]) * current_price
                    pnl = (current_price - float(row["avg_cost"])) * float(row["shares"])
                    items.append({
                        "id": row["id"],
                        "symbol": row["symbol"],
                        "shares": float(row["shares"]),
                        "avg_cost": float(row["avg_cost"]),
                        "notes": row["notes"],
                        "market_price": current_price,
                        "market_value": round(market_value, 2),
                        "pnl": round(pnl, 2),
                        "updated_at": row["updated_at"],
                    })
                return ok({"items": items})
            finally:
                conn.close()

        payload = request.get_json(silent=True) or {}
        symbol = (payload.get("symbol") or "").strip().upper()
        shares = float(payload.get("shares") or 0)
        avg_cost = float(payload.get("avg_cost") or 0)
        notes = (payload.get("notes") or "").strip()
        if not symbol or shares <= 0 or avg_cost <= 0:
            return error("股票代码、持仓数量和成本价必须大于 0")

        conn = get_db_connection()
        try:
            conn.execute(
                """
                INSERT INTO portfolio (user_id, symbol, shares, avg_cost, notes, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, symbol) DO UPDATE SET
                    shares = excluded.shares,
                    avg_cost = excluded.avg_cost,
                    notes = excluded.notes,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (user["id"], symbol, shares, avg_cost, notes),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM portfolio WHERE user_id = ? AND symbol = ?",
                (user["id"], symbol),
            ).fetchone()
            return ok({"item": dict(row)})
        finally:
            conn.close()
    except PermissionError as exc:
        return error(str(exc), 401)
    except ValueError:
        return error("持仓数量和成本价必须为有效数字")
    except Exception as exc:
        return error(f"更新持仓失败: {exc}")


@app.route("/api/portfolio/<symbol>", methods=["DELETE"])
def api_delete_portfolio(symbol: str):
    try:
        user = require_login()
        symbol = (symbol or "").strip().upper()
        conn = get_db_connection()
        try:
            conn.execute("DELETE FROM portfolio WHERE user_id = ? AND symbol = ?", (user["id"], symbol))
            conn.commit()
            return ok({"deleted_symbol": symbol})
        finally:
            conn.close()
    except PermissionError as exc:
        return error(str(exc), 401)
    except Exception as exc:
        return error(f"删除持仓失败: {exc}")


@app.route("/api/plans", methods=["GET", "POST"])
def api_investment_plans():
    try:
        user = require_login()
        if request.method == "GET":
            conn = get_db_connection()
            try:
                rows = conn.execute(
                    "SELECT * FROM investment_plans WHERE user_id = ? ORDER BY updated_at DESC",
                    (user["id"],),
                ).fetchall()
                items = []
                for row in rows:
                    snapshot = fetch_stock_snapshot(row["symbol"].lower()) or {}
                    current_price = float(snapshot.get("close") or 0.0)
                    expected_value = float(row["monthly_amount"]) * int(row["months"]) * (1 + float(row["target_return"]) / 100)
                    projected_value = current_price * float(row["monthly_amount"]) * 0.5 + expected_value
                    items.append({
                        "id": row["id"],
                        "symbol": row["symbol"],
                        "monthly_amount": float(row["monthly_amount"]),
                        "target_return": float(row["target_return"]),
                        "months": int(row["months"]),
                        "note": row["note"],
                        "current_price": current_price,
                        "expected_value": round(expected_value, 2),
                        "projected_value": round(projected_value, 2),
                        "updated_at": row["updated_at"],
                    })
                return ok({"items": items})
            finally:
                conn.close()

        payload = request.get_json(silent=True) or {}
        symbol = (payload.get("symbol") or "").strip().upper()
        monthly_amount = float(payload.get("monthly_amount") or 0)
        target_return = float(payload.get("target_return") or 0)
        months = int(payload.get("months") or 12)
        note = (payload.get("note") or "").strip()
        if not symbol or monthly_amount <= 0 or months <= 0:
            return error("股票代码、月投入金额和计划周期必须合法")

        conn = get_db_connection()
        try:
            conn.execute(
                """
                INSERT INTO investment_plans (user_id, symbol, monthly_amount, target_return, months, note, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, symbol) DO UPDATE SET
                    monthly_amount = excluded.monthly_amount,
                    target_return = excluded.target_return,
                    months = excluded.months,
                    note = excluded.note,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (user["id"], symbol, monthly_amount, target_return, months, note),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM investment_plans WHERE user_id = ? AND symbol = ?",
                (user["id"], symbol),
            ).fetchone()
            return ok({"item": dict(row)})
        finally:
            conn.close()
    except PermissionError as exc:
        return error(str(exc), 401)
    except ValueError:
        return error("定投金额或计划参数必须为有效数字")
    except Exception as exc:
        return error(f"保存定投计划失败: {exc}")


@app.route("/api/plans/<int:plan_id>", methods=["DELETE"])
def api_delete_investment_plan(plan_id: int):
    try:
        user = require_login()
        conn = get_db_connection()
        try:
            row = conn.execute(
                "SELECT id FROM investment_plans WHERE id = ? AND user_id = ?",
                (plan_id, user["id"]),
            ).fetchone()
            if not row:
                return error("定投计划不存在或无权限删除", 404)
            conn.execute("DELETE FROM investment_plans WHERE id = ?", (plan_id,))
            conn.commit()
            return ok({"deleted_id": plan_id})
        finally:
            conn.close()
    except PermissionError as exc:
        return error(str(exc), 401)
    except Exception as exc:
        return error(f"删除定投计划失败: {exc}")


@app.route("/api/strategies/compare")
def api_strategy_compare():
    try:
        user = require_login()
        symbol = (request.args.get("symbol") or "").strip().upper()
        conn = get_db_connection()
        try:
            if symbol:
                rows = conn.execute(
                    "SELECT * FROM stock_strategies WHERE user_id = ? AND symbol = ? ORDER BY updated_at DESC",
                    (user["id"], symbol),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM stock_strategies WHERE user_id = ? ORDER BY updated_at DESC",
                    (user["id"],),
                ).fetchall()
        finally:
            conn.close()

        compare_items = []
        for row in rows:
            signal_summary = build_technical_signal_summary(row["symbol"])
            score_result = evaluate_strategy_against_signal(signal_summary, dict(row))
            compare_items.append({
                "id": row["id"],
                "symbol": row["symbol"],
                "name": row["name"],
                "status": row["status"],
                "score": score_result.get("score", 0),
                "grade": score_result.get("grade", "弱"),
                "summary": signal_summary.get("summary", "震荡"),
                "reasons": score_result.get("reasons", []),
            })

        compare_items.sort(key=lambda item: item["score"], reverse=True)
        leader = compare_items[0] if compare_items else None
        return ok({"symbol": symbol or None, "items": compare_items, "leader": leader})
    except PermissionError as exc:
        return error(str(exc), 401)
    except Exception as exc:
        return error(f"策略对比失败: {exc}")


@app.route("/api/insights/summary")
def api_insight_summary():
    try:
        user = require_login()
        conn = get_db_connection()
        try:
            strategies = conn.execute(
                "SELECT * FROM stock_strategies WHERE user_id = ? ORDER BY updated_at DESC",
                (user["id"],),
            ).fetchall()
            portfolio_rows = conn.execute(
                "SELECT * FROM portfolio WHERE user_id = ? ORDER BY updated_at DESC",
                (user["id"],),
            ).fetchall()
        finally:
            conn.close()

        pulse = collect_market_pulse(limit=5)
        portfolio_value = 0.0
        portfolio_pnl = 0.0
        for row in portfolio_rows:
            snapshot = fetch_stock_snapshot(row["symbol"].lower())
            current_price = float(snapshot["close"]) if snapshot and snapshot.get("close") is not None else 0.0
            market_value = float(row["shares"]) * current_price
            pnl = (current_price - float(row["avg_cost"])) * float(row["shares"])
            portfolio_value += market_value
            portfolio_pnl += pnl

        strategy_scores = []
        for row in strategies:
            signal_summary = build_technical_signal_summary(row["symbol"])
            score_result = evaluate_strategy_against_signal(signal_summary, dict(row))
            strategy_scores.append({
                "name": row["name"],
                "symbol": row["symbol"],
                "score": score_result.get("score", 0),
                "grade": score_result.get("grade", "弱"),
            })

        best_strategy = max(strategy_scores, key=lambda item: item["score"], default=None)
        focus_symbol = best_strategy["symbol"] if best_strategy else (portfolio_rows[0]["symbol"] if portfolio_rows else "无")

        recommendations = []
        trend = pulse.get("sentiment", "震荡")
        if trend == "偏强":
            recommendations.append("市场偏强，适合持续维持顺势策略并保持控仓节奏。")
        elif trend == "偏弱":
            recommendations.append("市场偏弱，建议降低单票仓位，等待更明确的回升信号。")
        else:
            recommendations.append("市场震荡，建议优先观察量价确认和均线支撑强度。")

        if best_strategy:
            recommendations.append(f"当前最优策略是 {best_strategy['name']}，评分 {best_strategy['score']}，建议优先执行。")
        else:
            recommendations.append("当前尚未配置有效策略，建议先保存至少一条个股策略。")

        if portfolio_pnl >= 0:
            recommendations.append("当前组合整体处于盈利状态，可适度加大对强势板块的观察和配置。")
        else:
            recommendations.append("当前组合存在回撤，优先降低高风险持仓并重新校验止损条件。")

        summary = {
            "trend": trend,
            "portfolio_value": round(portfolio_value, 2),
            "portfolio_pnl": round(portfolio_pnl, 2),
            "best_strategy": best_strategy["name"] if best_strategy else "暂无",
            "focus_symbol": focus_symbol,
            "recommendations": recommendations,
        }
        return ok({"summary": summary})
    except PermissionError as exc:
        return error(str(exc), 401)
    except Exception as exc:
        return error(f"生成交易建议失败: {exc}")


@app.route("/api/stock/<symbol>/backtest/curve")
def api_stock_backtest_curve(symbol: str):
    try:
        symbol = (symbol or "").strip().upper()
        combinations = [(5, 10), (10, 20), (20, 50)]
        items = []
        for fast_period, slow_period in combinations:
            result = run_backtest(symbol.lower(), fast_period=fast_period, slow_period=slow_period)
            items.append({
                "fast_period": fast_period,
                "slow_period": slow_period,
                "net_return": result.get("net_return", 0.0),
                "trades": result.get("trades", 0),
            })
        return ok({"symbol": symbol, "items": items})
    except Exception as exc:
        return error(f"生成回测趋势失败: {exc}")


@app.route("/api/portfolio/summary")
def api_portfolio_summary():
    try:
        user = require_login()
        conn = get_db_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM portfolio WHERE user_id = ? ORDER BY updated_at DESC",
                (user["id"],),
            ).fetchall()
        finally:
            conn.close()

        chart = []
        total_value = 0.0
        total_pnl = 0.0
        for index, row in enumerate(rows):
            snapshot = fetch_stock_snapshot(row["symbol"].lower())
            current_price = float(snapshot["close"]) if snapshot and snapshot.get("close") is not None else 0.0
            market_value = float(row["shares"]) * current_price
            pnl = (current_price - float(row["avg_cost"])) * float(row["shares"])
            total_value += market_value
            total_pnl += pnl
            chart.append({
                "label": row["symbol"],
                "value": round(market_value, 2),
            })

        return ok({
            "items": [{
                "symbol": row["symbol"],
                "shares": float(row["shares"]),
                "avg_cost": float(row["avg_cost"]),
                "market_value": round(float(row["shares"]) * (float(fetch_stock_snapshot(row["symbol"].lower())["close"]) if fetch_stock_snapshot(row["symbol"].lower()) else 0.0), 2),
                "pnl": round(((float(fetch_stock_snapshot(row["symbol"].lower())["close"]) if fetch_stock_snapshot(row["symbol"].lower()) else 0.0) - float(row["avg_cost"])) * float(row["shares"]), 2),
            } for row in rows],
            "chart": chart,
            "total_value": round(total_value, 2),
            "total_pnl": round(total_pnl, 2),
        })
    except PermissionError as exc:
        return error(str(exc), 401)
    except Exception as exc:
        return error(f"生成组合摘要失败: {exc}")


@app.route("/api/portfolio/risk")
def api_portfolio_risk():
    try:
        user = require_login()
        conn = get_db_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM portfolio WHERE user_id = ? ORDER BY updated_at DESC",
                (user["id"],),
            ).fetchall()
        finally:
            conn.close()
        payload = calculate_portfolio_risk([dict(row) for row in rows])
        return ok(payload)
    except PermissionError as exc:
        return error(str(exc), 401)
    except Exception as exc:
        return error(f"生成组合风险分析失败: {exc}")


@app.route("/api/notifications")
def api_notifications():
    try:
        user = require_login()
        conn = get_db_connection()
        try:
            strategies = conn.execute(
                "SELECT * FROM stock_strategies WHERE user_id = ? ORDER BY updated_at DESC",
                (user["id"],),
            ).fetchall()
            portfolio_rows = conn.execute(
                "SELECT * FROM portfolio WHERE user_id = ? ORDER BY updated_at DESC",
                (user["id"],),
            ).fetchall()
        finally:
            conn.close()

        prefs = get_user_preferences(user["id"])
        threshold = float(prefs.get("alert_threshold") or 5.0)
        items = []
        if not strategies:
            items.append({
                "title": "未配置策略",
                "message": "建议先创建至少一条适合个股的交易策略，以便进行有效评估。",
                "level": "warning",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })

        if portfolio_rows:
            portfolio_total = 0.0
            pnl_total = 0.0
            alert_hits = []
            for row in portfolio_rows:
                snapshot = fetch_stock_snapshot(row["symbol"].lower())
                current_price = float(snapshot["close"]) if snapshot and snapshot.get("close") is not None else 0.0
                market_value = float(row["shares"]) * current_price
                pnl = (current_price - float(row["avg_cost"])) * float(row["shares"])
                portfolio_total += market_value
                pnl_total += pnl
                change_pct = float((snapshot or {}).get("change_pct") or 0.0)
                if abs(change_pct) >= threshold:
                    alert_hits.append(f"{row['symbol']} {change_pct:.2f}%")

            if alert_hits:
                items.append({
                    "title": "个股波动触发阈值",
                    "message": "当前持仓中有股票超出您设定的提醒阈值：" + "；".join(alert_hits[:3]) + "。建议及时检查。",
                    "level": "warning",
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                })

            if pnl_total < 0:
                items.append({
                    "title": "组合回撤",
                    "message": f"当前持仓累计盈亏为 {pnl_total:.2f}，建议关注风险控制。",
                    "level": "warning",
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                })
            else:
                items.append({
                    "title": "盈利状态",
                    "message": f"当前组合已实现盈亏 {pnl_total:.2f}，整体表现尚可。",
                    "level": "success",
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                })

        if strategies:
            best = max(
                [evaluate_strategy_against_signal(build_technical_signal_summary(row["symbol"]), dict(row)) for row in strategies],
                key=lambda item: item.get("score", 0),
                default={"strategy_name": "无", "score": 0, "grade": "弱"},
            )
            if best.get("grade") == "弱":
                items.append({
                    "title": "策略表现偏弱",
                    "message": f"{best.get('strategy_name', '当前策略')} 评分较低，建议重新评估规则或修改参数。",
                    "level": "warning",
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                })
            else:
                items.append({
                    "title": "策略状态正常",
                    "message": f"{best.get('strategy_name', '当前策略')} 评分为 {best.get('score', 0)}，适合继续观察。",
                    "level": "info",
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                })

        if not items:
            items.append({
                "title": "提醒中心正常",
                "message": "当前没有需处理的风险事件，继续保持观察即可。",
                "level": "success",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })

        return ok({"items": items[:5], "alert_threshold": threshold})
    except PermissionError as exc:
        return error(str(exc), 401)
    except Exception as exc:
        return error(f"生成提醒中心失败: {exc}")


@app.route("/api/alerts", methods=["GET", "POST"])
def api_stock_alerts():
    try:
        user = require_login()
        if request.method == "GET":
            alerts = get_user_stock_alerts(user["id"])
            items = []
            for alert in alerts:
                snapshot = fetch_stock_snapshot(alert["symbol"].lower())
                period_low = get_period_low(alert["symbol"], alert["period"])
                current_price = float(snapshot.get("close") or 0.0) if snapshot else 0.0
                items.append({
                    "id": alert["id"],
                    "symbol": alert["symbol"],
                    "period": alert["period"],
                    "enabled": bool(int(alert["enabled"] or 0)),
                    "last_triggered_at": alert.get("last_triggered_at"),
                    "current_price": round(current_price, 2),
                    "period_low": round(period_low, 2) if period_low is not None else None,
                })
            return ok({"items": items})

        payload = request.get_json(silent=True) or {}
        symbol = (payload.get("symbol") or "").strip().upper()
        period = (payload.get("period") or "3m").strip().lower()
        enabled = bool(payload.get("enabled", True))
        if not symbol:
            return error("股票代码不能为空")
        if period not in {"3m", "6m", "1y"}:
            return error("预警周期必须为 3m、6m 或 1y")

        item = save_user_stock_alert(user["id"], symbol, period, enabled=enabled)
        return ok({"item": item})
    except PermissionError as exc:
        return error(str(exc), 401)
    except Exception as exc:
        return error(f"保存股票预警失败: {exc}")


@app.route("/api/alerts/<int:alert_id>", methods=["DELETE"])
def api_delete_stock_alert(alert_id: int):
    try:
        user = require_login()
        delete_user_stock_alert(user["id"], alert_id)
        return ok({"deleted_id": alert_id})
    except PermissionError as exc:
        return error(str(exc), 401)
    except Exception as exc:
        return error(f"删除股票预警失败: {exc}")


@app.route("/api/email/config", methods=["GET", "POST"])
def api_email_config():
    try:
        user = require_login()
        if request.method == "GET":
            return ok(get_user_email_config(user["id"]))

        payload = request.get_json(silent=True) or {}
        config = save_user_email_config(
            user["id"],
            sender_name=(payload.get("sender_name") or "").strip(),
            sender_email=(payload.get("sender_email") or "").strip(),
            smtp_host=(payload.get("smtp_host") or "").strip(),
            smtp_port=int(payload.get("smtp_port") or 465),
            smtp_username=(payload.get("smtp_username") or "").strip(),
            smtp_password=(payload.get("smtp_password") or "").strip(),
            use_tls=int(payload.get("use_tls") or 1),
            recipient_name=(payload.get("recipient_name") or "").strip(),
            recipient_email=(payload.get("recipient_email") or "").strip(),
            enabled=int(payload.get("enabled") or 0),
        )
        return ok(config)
    except PermissionError as exc:
        return error(str(exc), 401)
    except ValueError:
        return error("邮件配置参数不合法")
    except Exception as exc:
        return error(f"保存邮件配置失败: {exc}")


