#!/bin/bash
# Tắt buffering để log hiển thị ngay lập tức
export PYTHONUNBUFFERED=1

# 1. Khởi động màn hình ảo Xvfb (độ phân giải 1280x720)
Xvfb :99 -screen 0 1280x720x24 &
export DISPLAY=:99

# 2. Khởi động VNC Server (x11vnc)
x11vnc -display :99 -nopw -listen 0.0.0.0 -forever -shared &

# 3. Khởi động noVNC (websockify) để truyền hình ảnh qua web
# Lắng nghe trên cổng 6080 nội bộ
websockify --web /usr/share/novnc/ 6080 localhost:5900 &

# 4. Khởi động FastAPI (cổng 8000)
uvicorn main:app --host 0.0.0.0 --port 8000
