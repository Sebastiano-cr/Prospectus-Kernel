"""
Health check and metrics endpoints.
"""
import logging
from fastapi import APIRouter
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from agents.runtime import get_store

logger = logging.getLogger(__name__)
router = APIRouter(tags=["management"])


@router.get("/health")
async def health_check():
    store = get_store()
    if store is None:
        return {"status": "degraded", "checks": {"chroma": "not_initialized"}}
    chroma_ready = await store.ready()
    return {
        "status": "healthy" if chroma_ready else "degraded",
        "checks": {"chroma": "healthy" if chroma_ready else "unreachable"},
    }


@router.get("/metrics")
async def metrics_endpoint():
    from fastapi.responses import Response
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
