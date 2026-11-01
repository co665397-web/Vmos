#!/bin/bash
export PYTHONUNBUFFERED=1

cd /app

echo "=== Khởi động Xvfb (Màn hình dọc) ==="
# Tăng lên 600x1024 để chữ và nút bấm rõ nét hơn
Xvfb :99 -screen 0 600x1024x24 &
export DISPLAY=:99
sleep 2

echo "=== Khởi động x11vnc ==="
x11vnc -display :99 -nopw -listen 0.0.0.0 -forever -shared -ncache 10 -noxdamage &
sleep 3

echo "=== Khởi động FastAPI ==="
exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
