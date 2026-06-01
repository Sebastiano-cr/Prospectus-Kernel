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

# Set the PYTHONPATH to include the parent directory (so we can import agents)
ENV PYTHONPATH="/app:/app/.."

# Health check: verify Redis connectivity using Python
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python3 -c "import redis; r=redis.Redis(host='$REDIS_HOST', port=$REDIS_PORT, db=0); r.ping()" || exit 1

# Command to run the worker
CMD ["python", "worker.py"]