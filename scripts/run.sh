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
python3 run.py
