FROM python:3.11-slim

# Cài đặt thư viện hệ thống cho màn hình ảo, VNC và Playwright
RUN apt-get update && apt-get install -y \
    xvfb \
    x11vnc \
    novnc \
    wget \
    curl \
    libnss3 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libgbm1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Cài đặt Playwright và các dependencies của Chromium
RUN playwright install chromium
RUN playwright install-deps

# Copy toàn bộ code vào container
COPY . .

RUN chmod +x start.sh

CMD ["./start.sh"]
