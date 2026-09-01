"""兼容入口。

老版本项目是单文件 `stock_web.py`，但为了便于维护，
现在已拆分到 `stock_app/` 包。这里保留一个薄入口，
保证原有启动方式不变，并继续兼容脚本/文档中的调用方式。
"""

from stock_app.app import app
from stock_app.config import CONFIG
from stock_app.db import init_app_db


if __name__ == "__main__":
    init_app_db()
    from stock_app.routes import start_alert_monitor

    start_alert_monitor()
    app.run(host=CONFIG.host, port=CONFIG.port, debug=CONFIG.debug, use_reloader=CONFIG.use_reloader, threaded=CONFIG.use_multithreading)