#!/bin/bash
# Launcher para o Prospectus-Kernel API
export PYTHONPATH="${PYTHONPATH}:$(dirname "$0")"
export LITELLM_URL="${LITELLM_URL:-http://localhost:4000}"
export DEEPSEEK_CHAT_API_KEY="${DEEPSEEK_CHAT_API_KEY:-test-key}"
export CHROMA_PATH="${CHROMA_PATH:-./data/chroma}"
export PORT="${PORT:-8000}"

cd "$(dirname "$0")" && python3 agents/server.py
