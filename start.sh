#!/bin/bash
export PYTHONUNBUFFERED=1

cd /app

echo "=== Khởi động Xvfb (Màn hình dọc tỷ lệ điện thoại) ==="
# Đặt độ phân giải chuẩn điện thoại để tối ưu hiển thị
Xvfb :99 -screen 0 540x960x24 &
export DISPLAY=:99
sleep 2

echo "=== Khởi động x11vnc ==="
x11vnc -display :99 -nopw -listen 0.0.0.0 -forever -shared -ncache 10 -noxdamage &
sleep 3

echo "=== Khởi động FastAPI ==="
exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
