# ======================================
# Dockerfile - Sistem Pesantren (Flask)
# ======================================

# Base image Python 3.12 slim (lebih kecil ukurannya)
FROM python:3.12-slim

# Set working directory di dalam container
WORKDIR /app

# Install system dependencies yang diperlukan
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements.txt terlebih dahulu (memanfaatkan Docker layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy semua source code ke dalam container
COPY . .

# Buat direktori uploads jika belum ada
RUN mkdir -p uploads

# Expose port 8080 (Cloud Run default port)
EXPOSE 8080

# Jalankan aplikasi menggunakan Gunicorn
# - workers: 2 (cukup untuk Cloud Run free tier)
# - bind: 0.0.0.0:8080 (semua interface, port 8080)
# - timeout: 120 (untuk request yang lama seperti import Excel)
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--timeout", "120", "--access-logfile", "-", "app:app"]
