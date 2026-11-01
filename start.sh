#!/bin/bash
export PYTHONUNBUFFERED=1

Xvfb :99 -screen 0 1280x720x24 &
export DISPLAY=:99

x11vnc -display :99 -nopw -listen 0.0.0.0 -forever -shared &
# VNC vẫn chạy nội bộ ở cổng 6080
websockify --web /usr/share/novnc/ 6080 localhost:5900 &

# FastAPI chạy trên cổng 7860 (cổng duy nhất của Hugging Face)
exec uvicorn main:app --host 0.0.0.0 --port 7860
