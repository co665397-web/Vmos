#!/bin/bash
export PYTHONUNBUFFERED=1

cd /app

# Khởi động màn hình ảo
Xvfb :99 -screen 0 1280x720x24 &
export DISPLAY=:99

# Khởi động VNC Server
x11vnc -display :99 -nopw -listen 0.0.0.0 -forever -shared &

# Chạy FastAPI (Tự động nhận cổng ${PORT} do Cloady cấp, nếu không có thì mặc định 8080)
exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
