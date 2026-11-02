#!/bin/bash
export PYTHONUNBUFFERED=1

mkdir -p /tmp/.X11-unix
chmod 1777 /tmp/.X11-unix

echo "=== Khởi động Xvfb (Màn hình dọc) ==="
Xvfb :99 -screen 0 600x1024x24 &
export DISPLAY=:99
sleep 2

echo "=== Khởi động x11vnc ==="
x11vnc -display :99 -nopw -listen 0.0.0.0 -forever -shared -ncache 10 -noxdamage &
sleep 3

echo "=== Khởi động FastAPI ==="
# SỬA LỖI TẠI ĐÂY: Dùng python -m uvicorn
exec python -m uvicorn main:app --host 0.0.0.0 --port 8080
