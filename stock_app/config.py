"""应用配置与路径常量。

这里集中管理数据库路径、Flask 配置和运行环境变量，避免各模块重复声明。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_DB_PATH = os.path.join(BASE_DIR, "stock_app.db")
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "stock.db")


def _get_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class AppConfig:
    app_name: str = "stock_analysis_app"
    secret_key: str = os.environ.get("STOCK_SECRET_KEY", "stock-analysis-secret-key")
    port: int = _get_int("PORT", 5858)
    debug: bool = _get_bool("DEBUG", False)
    host: str = os.environ.get("HOST", "0.0.0.0")
    use_multithreading: bool = _get_bool("USE_MULTITHREADING", True)
    use_reloader: bool = _get_bool("USE_RELOADER", False)
    alert_check_interval_seconds: int = _get_int("ALERT_CHECK_INTERVAL_SECONDS", 60)
    max_alert_retries: int = _get_int("MAX_ALERT_RETRIES", 3)


CONFIG = AppConfig()
SECRET_KEY = CONFIG.secret_key
APP_NAME = CONFIG.app_name
PORT = CONFIG.port
DEBUG = CONFIG.debug
HOST = CONFIG.host
