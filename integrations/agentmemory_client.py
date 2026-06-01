"""
integrations/agentmemory_client.py

Cliente HTTP mínimo para o agentmemory sidecar (porta 3111).
Usado pelo Scorer e Messenger para buscar contexto acumulado de leads anteriores.

Ativação: AGENTMEMORY_ENABLED=true (default: false — zero impacto se desligado)
"""
import os
import logging
import httpx
from typing import Optional

logger = logging.getLogger(__name__)

_ENABLED = os.getenv("AGENTMEMORY_ENABLED", "false").lower() == "true"
_BASE    = os.getenv("AGENTMEMORY_URL", "http://agentmemory:3111")
_SECRET  = os.getenv("AGENTMEMORY_SECRET", "")
_PROJECT = "kirin_production"
_TIMEOUT = 5.0  # nunca bloquear o pipeline por mais de 5s


def _headers() -> dict:
    h = {"Content-Type": "application/json"}
    if _SECRET:
        h["Authorization"] = f"Bearer {_SECRET}"
    return h


async def observe(session_id: str, data: dict) -> None:
    """Registra observação na sessão atual. Fire-and-forget."""
    if not _ENABLED:
        return
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            await c.post(f"{_BASE}/agentmemory/observe", headers=_headers(), json={
                "project": _PROJECT,
                "sessionId": session_id,
                "observation": data,
            })
    except Exception as e:
        logger.debug(f"agentmemory observe silenced: {e}")


async def smart_search(query: str, limit: int = 3) -> list[dict]:
    """Busca híbrida BM25+vector. Retorna lista de observações relevantes."""
    if not _ENABLED:
        return []
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.post(f"{_BASE}/agentmemory/smart-search", headers=_headers(), json={
                "project": _PROJECT,
                "query": query,
                "limit": limit,
            })
        if r.status_code == 200:
            return r.json().get("results", [])
    except Exception as e:
        logger.debug(f"agentmemory smart_search silenced: {e}")
    return []


async def session_start(lead_id: str, context: dict) -> str:
    """Inicia sessão para um lead. Retorna session_id."""
    if not _ENABLED:
        return lead_id
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.post(f"{_BASE}/agentmemory/session/start", headers=_headers(), json={
                "project": _PROJECT,
                "agentId": "kirin-pipeline",
                "context": context,
            })
        if r.status_code == 200:
            return r.json().get("sessionId", lead_id)
    except Exception as e:
        logger.debug(f"agentmemory session_start silenced: {e}")
    return lead_id


async def session_end(session_id: str, summary: dict) -> None:
    """Finaliza sessão e consolida memória."""
    if not _ENABLED:
        return
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            await c.post(f"{_BASE}/agentmemory/session/end", headers=_headers(), json={
                "project": _PROJECT,
                "sessionId": session_id,
                "summary": summary,
            })
    except Exception as e:
        logger.debug(f"agentmemory session_end silenced: {e}")


async def remember(content: str, tags: Optional[list[str]] = None) -> None:
    """Salva fato de longo prazo (padrão, template vencedor, etc.)."""
    if not _ENABLED:
        return
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            await c.post(f"{_BASE}/agentmemory/remember", headers=_headers(), json={
                "project": _PROJECT,
                "content": content,
                "tags": tags or [],
            })
    except Exception as e:
        logger.debug(f"agentmemory remember silenced: {e}")
