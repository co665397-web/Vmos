# Sử dụng image chính thức của Playwright (đã có sẵn Chromium và các thư viện hệ thống)
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Cài đặt thêm các gói cần thiết cho màn hình ảo và VNC
RUN apt-get update && apt-get install -y \
    xvfb \
    x11vnc \
    novnc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Cài đặt các thư viện Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ code vào container
COPY . .

# Cấp quyền thực thi cho file start.sh
RUN chmod +x start.sh

# Khai báo cổng (dự phòng)
EXPOSE 8080

# Chạy ứng dụng
CMD ["/app/start.sh"]
