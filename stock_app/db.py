"""数据库访问与用户认证辅助逻辑。

本模块负责：
- 获取 SQLite 连接
- 初始化用户与策略相关表
- 获取当前登录用户
- 校验登录状态
"""

from __future__ import annotations

import sqlite3

from flask import session
from werkzeug.security import check_password_hash, generate_password_hash

from stock_app.config import APP_DB_PATH


def get_db_connection(db_path: str = APP_DB_PATH):
    """创建带行工厂的 SQLite 连接，便于模板直接访问列名。"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_app_db():
    """确保应用数据表存在，包括用户、新闻、策略和自选股。"""
    conn = get_db_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS stock_news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NULL,
                symbol TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'system',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS stock_strategies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                rule TEXT NOT NULL DEFAULT '',
                entry_condition TEXT NOT NULL DEFAULT '',
                exit_condition TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, symbol, name)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, symbol)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS portfolio (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                shares REAL NOT NULL DEFAULT 0,
                avg_cost REAL NOT NULL DEFAULT 0,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, symbol)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id INTEGER PRIMARY KEY,
                default_symbol TEXT NOT NULL DEFAULT 'bj920000',
                refresh_interval INTEGER NOT NULL DEFAULT 60,
                alert_threshold REAL NOT NULL DEFAULT 5.0,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS investment_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                monthly_amount REAL NOT NULL DEFAULT 0,
                target_return REAL NOT NULL DEFAULT 0,
                months INTEGER NOT NULL DEFAULT 12,
                note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, symbol)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS stock_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                period TEXT NOT NULL DEFAULT '3m',
                enabled INTEGER NOT NULL DEFAULT 1,
                last_triggered_at TEXT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, symbol, period)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS email_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                sender_name TEXT NOT NULL DEFAULT '',
                sender_email TEXT NOT NULL DEFAULT '',
                smtp_host TEXT NOT NULL DEFAULT '',
                smtp_port INTEGER NOT NULL DEFAULT 465,
                smtp_username TEXT NOT NULL DEFAULT '',
                smtp_password TEXT NOT NULL DEFAULT '',
                use_tls INTEGER NOT NULL DEFAULT 1,
                recipient_name TEXT NOT NULL DEFAULT '',
                recipient_email TEXT NOT NULL DEFAULT '',
                enabled INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS alert_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                period TEXT NOT NULL,
                current_price REAL NOT NULL DEFAULT 0,
                threshold_price REAL NOT NULL DEFAULT 0,
                message TEXT NOT NULL DEFAULT '',
                sent_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def get_user_preferences(user_id: int):
    """返回用户偏好配置，确保缺省值稳定。"""
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT default_symbol, refresh_interval, alert_threshold, updated_at FROM user_preferences WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if row is None:
            return {
                "default_symbol": "bj920000",
                "refresh_interval": 60,
                "alert_threshold": 5.0,
                "updated_at": None,
            }
        return {
            "default_symbol": row["default_symbol"] or "bj920000",
            "refresh_interval": int(row["refresh_interval"] or 60),
            "alert_threshold": float(row["alert_threshold"] or 5.0),
            "updated_at": row["updated_at"],
        }
    finally:
        conn.close()


def save_user_preferences(user_id: int, **kwargs):
    """保存用户个性化配置，并在缺省字段时保留已有值。"""
    current = get_user_preferences(user_id)
    payload = {
        "default_symbol": (str(kwargs.get("default_symbol") or current["default_symbol"]) or "bj920000").lower(),
        "refresh_interval": int(kwargs.get("refresh_interval") or current["refresh_interval"]),
        "alert_threshold": float(kwargs.get("alert_threshold") or current["alert_threshold"]),
    }
    payload["refresh_interval"] = max(15, min(300, payload["refresh_interval"]))
    payload["alert_threshold"] = max(0.0, min(50.0, payload["alert_threshold"]))

    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO user_preferences (user_id, default_symbol, refresh_interval, alert_threshold, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                default_symbol = excluded.default_symbol,
                refresh_interval = excluded.refresh_interval,
                alert_threshold = excluded.alert_threshold,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                user_id,
                payload["default_symbol"],
                payload["refresh_interval"],
                payload["alert_threshold"],
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return get_user_preferences(user_id)


def get_user_email_config(user_id: int):
    """读取用户邮件配置。"""
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT * FROM email_configs WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if row is None:
            return {
                "sender_name": "",
                "sender_email": "",
                "smtp_host": "",
                "smtp_port": 465,
                "smtp_username": "",
                "smtp_password": "",
                "use_tls": 1,
                "recipient_name": "",
                "recipient_email": "",
                "enabled": 0,
                "updated_at": None,
            }
        return {
            "id": row["id"],
            "sender_name": row["sender_name"] or "",
            "sender_email": row["sender_email"] or "",
            "smtp_host": row["smtp_host"] or "",
            "smtp_port": int(row["smtp_port"] or 465),
            "smtp_username": row["smtp_username"] or "",
            "smtp_password": row["smtp_password"] or "",
            "use_tls": int(row["use_tls"] or 1),
            "recipient_name": row["recipient_name"] or "",
            "recipient_email": row["recipient_email"] or "",
            "enabled": int(row["enabled"] or 0),
            "updated_at": row["updated_at"],
        }
    finally:
        conn.close()


def save_user_email_config(user_id: int, **kwargs):
    """保存邮件发送/接收配置。"""
    current = get_user_email_config(user_id)
    payload = {
        "sender_name": str(kwargs.get("sender_name") or current["sender_name"] or "").strip(),
        "sender_email": str(kwargs.get("sender_email") or current["sender_email"] or "").strip(),
        "smtp_host": str(kwargs.get("smtp_host") or current["smtp_host"] or "").strip(),
        "smtp_port": int(kwargs.get("smtp_port") or current["smtp_port"] or 465),
        "smtp_username": str(kwargs.get("smtp_username") or current["smtp_username"] or "").strip(),
        "smtp_password": str(kwargs.get("smtp_password") or current["smtp_password"] or "").strip(),
        "use_tls": int(kwargs.get("use_tls") or current["use_tls"] or 1),
        "recipient_name": str(kwargs.get("recipient_name") or current["recipient_name"] or "").strip(),
        "recipient_email": str(kwargs.get("recipient_email") or current["recipient_email"] or "").strip(),
        "enabled": int(kwargs.get("enabled") or current["enabled"] or 0),
    }
    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO email_configs (
                user_id, sender_name, sender_email, smtp_host, smtp_port, smtp_username,
                smtp_password, use_tls, recipient_name, recipient_email, enabled, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                sender_name = excluded.sender_name,
                sender_email = excluded.sender_email,
                smtp_host = excluded.smtp_host,
                smtp_port = excluded.smtp_port,
                smtp_username = excluded.smtp_username,
                smtp_password = excluded.smtp_password,
                use_tls = excluded.use_tls,
                recipient_name = excluded.recipient_name,
                recipient_email = excluded.recipient_email,
                enabled = excluded.enabled,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                user_id,
                payload["sender_name"],
                payload["sender_email"],
                payload["smtp_host"],
                payload["smtp_port"],
                payload["smtp_username"],
                payload["smtp_password"],
                payload["use_tls"],
                payload["recipient_name"],
                payload["recipient_email"],
                payload["enabled"],
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return get_user_email_config(user_id)


def get_user_stock_alerts(user_id: int):
    """读取用户的股票预警配置。"""
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM stock_alerts WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def save_user_stock_alert(user_id: int, symbol: str, period: str, enabled: bool = True):
    """保存/更新单条股票预警。"""
    safe_symbol = (symbol or "").strip().upper()
    safe_period = (period or "3m").strip().lower()
    if not safe_symbol:
        raise ValueError("股票代码不能为空")
    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO stock_alerts (user_id, symbol, period, enabled, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, symbol, period) DO UPDATE SET
                enabled = excluded.enabled,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, safe_symbol, safe_period, 1 if enabled else 0),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM stock_alerts WHERE user_id = ? AND symbol = ? AND period = ?",
            (user_id, safe_symbol, safe_period),
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def delete_user_stock_alert(user_id: int, alert_id: int):
    """删除股票预警。"""
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM stock_alerts WHERE user_id = ? AND id = ?", (user_id, alert_id))
        conn.commit()
    finally:
        conn.close()


def record_alert_event(user_id: int, symbol: str, period: str, current_price: float, threshold_price: float, message: str):
    """记录提醒事件，便于后续追踪。"""
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO alert_events (user_id, symbol, period, current_price, threshold_price, message) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, (symbol or '').upper(), (period or '3m').lower(), float(current_price or 0), float(threshold_price or 0), message or ''),
        )
        conn.commit()
    finally:
        conn.close()


def get_current_user():
    """从 Flask session 中读取当前用户信息。"""
    user_id = session.get("user_id")
    if not user_id:
        return None
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT id, username, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def require_login():
    """确保请求已登录，否则抛出权限异常。"""
    user = get_current_user()
    if not user:
        raise PermissionError("请先登录")
    return user


def quote_identifier(identifier: str) -> str:
    """对 SQL 标识符进行转义，防止表名中包含特殊字符。"""
    return '"' + str(identifier).replace('"', '""') + '"'


def hash_password(password: str) -> str:
    """密码加密。"""
    return generate_password_hash(password)


def verify_password(password_hash: str, raw_password: str) -> bool:
    """校验密码。"""
    return check_password_hash(password_hash, raw_password)
