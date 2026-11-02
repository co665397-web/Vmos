# Sử dụng image chính thức của Playwright (Đã có sẵn Chromium và mọi thư viện)
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Chỉ cài thêm các gói siêu nhẹ cho VNC (mất vài giây)
RUN apt-get update && apt-get install -y \
    xvfb \
    x11vnc \
    novnc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Tối ưu Docker Cache: Chỉ cài thư viện Python trước
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code sau cùng để khi sửa code không phải cài lại thư viện
COPY . .

RUN chmod +x start.sh

EXPOSE 8080
CMD ["/app/start.sh"]
