#!/usr/bin/env bash
set -euo pipefail

pids=$(ps -ef | grep 'gunicorn stock_web:app' | grep -v grep | awk '{print $2}')
if [ -z "$pids" ]; then
  echo "No stock web process is running."
  exit 0
fi

for pid in $pids; do
  kill "$pid"
done

echo "Stopped stock web process(es): $pids"
