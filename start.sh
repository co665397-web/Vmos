#!/bin/bash
export PYTHONUNBUFFERED=1

# Di chuyển vào thư mục chứa code
cd /app

# 1. Khởi động màn hình ảo Xvfb
Xvfb :99 -screen 0 1280x720x24 &
export DISPLAY=:99

# 2. Khởi động VNC Server
x11vnc -display :99 -nopw -listen 0.0.0.0 -forever -shared &

# 3. Khởi động FastAPI
exec uvicorn main:app --host 0.0.0.0 --port 8000
