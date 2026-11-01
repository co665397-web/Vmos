#!/bin/bash
export PYTHONUNBUFFERED=1

cd /app

echo "=== Đang khởi động Xvfb ==="
Xvfb :99 -screen 0 1280x720x24 &
export DISPLAY=:99
sleep 2

echo "=== Đang khởi động x11vnc ==="
x11vnc -display :99 -nopw -listen 0.0.0.0 -forever -shared &
sleep 2

echo "=== Đang khởi động FastAPI ==="
exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
