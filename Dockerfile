FROM python:3.11-slim

# Cài đặt các gói hệ thống cần thiết cho màn hình ảo, VNC và Playwright
RUN apt-get update && apt-get install -y \
    xvfb \
    x11vnc \
    novnc \
    websockify \
    wget \
    curl \
    libnss3 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libgbm1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Cài đặt thư viện Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Cài đặt trình duyệt Chromium cho Playwright
RUN playwright install chromium

# Copy toàn bộ mã nguồn vào container
COPY . .

# Cấp quyền thực thi cho script khởi động
RUN chmod +x start.sh

# Chạy script khởi động
CMD ["./start.sh"]
