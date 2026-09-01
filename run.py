import os

from stock_app.config import CONFIG
from stock_web import app

if __name__ == "__main__":
    from stock_app.db import init_app_db
    from stock_app.routes import start_alert_monitor

    init_app_db()
    start_alert_monitor()
    app.run(host=CONFIG.host, port=CONFIG.port, debug=CONFIG.debug, use_reloader=CONFIG.use_reloader, threaded=CONFIG.use_multithreading)
