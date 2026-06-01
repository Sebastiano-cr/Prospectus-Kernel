FROM python:3.11-slim
WORKDIR /app
COPY . /app/agents/
RUN pip install --no-cache-dir -r /app/agents/requirements.txt
EXPOSE 8000
ENV PYTHONPATH=/app
WORKDIR /app/agents
CMD ["python", "server.py"]