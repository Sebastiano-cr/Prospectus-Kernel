FROM python:3.11-slim
WORKDIR /app

COPY agents/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agents/ ./agents/
COPY src/ ./src/

EXPOSE 8000
ENV PYTHONPATH=/app
CMD ["python", "agents/server.py"]
