#!/bin/bash
# Launcher para o Kirin Agents API
# Configura PYTHONPATH e variaveis de ambiente, depois sobe o servidor

export PYTHONPATH="${PYTHONPATH}:$(dirname "$0")/agents"
export POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
export POSTGRES_PORT="${POSTGRES_PORT:-5432}"
export POSTGRES_DB="${POSTGRES_DB:-kirin}"
export POSTGRES_USER="${POSTGRES_USER:-kirin}"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-}"
export QDRANT_HOST="${QDRANT_HOST:-localhost}"
export QDRANT_PORT="${QDRANT_PORT:-6333}"
export REDIS_HOST="${REDIS_HOST:-localhost}"
export REDIS_PORT="${REDIS_PORT:-6379}"
export LITELLM_URL="${LITELLM_URL:-http://localhost:4000}"
export DEEPSEEK_CHAT_API_KEY="${DEEPSEEK_CHAT_API_KEY:-test-key}"
export PORT="${PORT:-8000}"

cd "$(dirname "$0")/agents" && python3 server.py
