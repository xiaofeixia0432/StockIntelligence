#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
python3 -m pip install --upgrade pip >/dev/null
python3 -m pip install -r requirements.txt

export FLASK_APP=stock_web.py
export PORT="${PORT:-5000}"

if pgrep -f "gunicorn.*stock_web:app" >/dev/null 2>&1; then
  echo "Existing gunicorn process detected; restarting..."
  pkill -f "gunicorn.*stock_web:app" || true
fi

nohup gunicorn -c gunicorn.conf.py stock_web:app > stock_app.log 2>&1 &

echo "Stock app is running in background on http://0.0.0.0:${PORT}"
