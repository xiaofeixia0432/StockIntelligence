"""Stock analysis application package.

该包按功能拆分为配置、数据库、行情分析、策略评估和路由层，
保留了原有 `stock_web.py` 的兼容入口，便于逐步迁移和维护。
"""

from .app import app

__all__ = ["app"]
