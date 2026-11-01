#!/bin/bash
export PYTHONUNBUFFERED=1

# Di chuyển vào thư mục chứa code
cd /app

# 1. Khởi động màn hình ảo Xvfb (giảm độ phân giải để tiết kiệm RAM)
Xvfb :99 -screen 0 1280x720x24 &
export DISPLAY=:99

# 2. Khởi động VNC Server
x11vnc -display :99 -nopw -listen 0.0.0.0 -forever -shared &

# 3. Khởi động FastAPI (Tự động nhận cổng từ Cloady, mặc định là 8080)
exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
