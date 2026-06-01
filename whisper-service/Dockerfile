# ESTÁGIO 1: Builder com ffmpeg completo
FROM jrottenberg/ffmpeg:alpine AS ffmpeg-builder

# ESTÁGIO 2: Runtime mínimo
FROM python:3.13-slim

# Copiar ffmpeg e suas bibliotecas do estágio de build
COPY --from=ffmpeg-builder /usr/local /usr/local

WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Expose the port the app runs on
EXPOSE 8003

# Health check for HTTP endpoint using Python requests (or wget, but we can use python for consistency)
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python3 -c "import requests; r=requests.get('http://localhost:8003/health'); exit(0 if r.status_code==200 else 1)" || exit 1

# Command to run the app
CMD ["python", "main.py"]