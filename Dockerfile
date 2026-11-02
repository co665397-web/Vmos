FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Cài đặt các gói hệ thống cần thiết, dùng --no-install-recommends để giảm dung lượng
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    x11vnc \
    novnc \
    curl \
    wget \
    libnss3 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libgbm1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy và cài đặt thư viện Python trước để tận dụng bộ nhớ đệm (Cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Cài đặt Playwright Chromium (Chỉ tải những gì cần thiết)
RUN playwright install chromium

# Copy code sau cùng (Khi sửa code sẽ không phải cài lại thư viện)
COPY . .

RUN chmod +x start.sh

EXPOSE 8080
CMD ["/app/start.sh"]
