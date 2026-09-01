"""应用工厂与入口模块。

该模块用于创建 Flask 应用，并注册所有路由。后续扩展功能时，
建议继续在 `stock_app/` 包中添加新模块而不是继续在单文件中堆积。
"""

from __future__ import annotations

import os

from flask import Flask

from stock_app.config import BASE_DIR, SECRET_KEY

app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"), static_folder=os.path.join(BASE_DIR, "static"))
app.config["JSON_SORT_KEYS"] = False
app.secret_key = SECRET_KEY

# 在应用创建完成后注册所有路由，避免循环依赖。
from stock_app.routes import *  # noqa: F401,F403

__all__ = ["app"]
