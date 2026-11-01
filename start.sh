#!/bin/bash
# Khởi động màn hình ảo Xvfb
Xvfb :99 -screen 0 1280x720x24 &
export DISPLAY=:99

# Khởi động VNC Server
x11vnc -display :99 -nopw -listen 0.0.0.0 -forever -shared &

# Khởi động noVNC (Cổng 6080)
websockify --web /usr/share/novnc/ 6080 localhost:5900 &

# Khởi động FastAPI (Cổng 8000)
uvicorn main:app --host 0.0.0.0 --port 8000
