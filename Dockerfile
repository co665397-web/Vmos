# Dùng bản Python slim cơ bản để giảm dung lượng
FROM python:3.11-slim

# Cài đặt môi trường không tương tác
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Cài đặt các gói hệ thống cần thiết cho màn hình ảo và VNC
RUN apt-get update && apt-get install -y \
    xvfb \
    x11vnc \
    novnc \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy và cài đặt thư viện Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Cài đặt Chromium và các thư viện phụ thuộc của Playwright (Gộp chung 1 lệnh để tối ưu)
RUN playwright install --with-deps chromium

# Copy code
COPY . .

# Phân quyền cho start.sh
RUN chmod +x start.sh

# Mở cổng 8080
EXPOSE 8080

# Chạy tool
CMD ["/app/start.sh"]
