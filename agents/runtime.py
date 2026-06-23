"""
Global runtime state for the Prospectus-Kernel cognitive runtime.
Uses ChromaStore as the single unified storage backend.
"""
import asyncio
import logging
from typing import Optional
from src.store import ChromaStore

logger = logging.getLogger(__name__)

_store: Optional[ChromaStore] = None
_initialized: bool = False
_health_task: Optional[asyncio.Task] = None
_MAX_INIT_RETRIES = 5
_INIT_RETRY_DELAY = 3.0
_HEALTH_CHECK_INTERVAL = 30.0  # segundos entre checks de saúde


async def initialize_memory_managers(config: dict) -> None:
    global _store, _initialized, _health_task

    if _initialized:
        logger.warning("Memory already initialized. Skipping.")
        return

    path = config.get("chroma", {}).get("path", "./data/chroma")

    for attempt in range(_MAX_INIT_RETRIES):
        try:
            _store = ChromaStore(path=path)
            await _store.initialize()
            _initialized = True
            logger.info("ChromaStore initialized (replaces PostgreSQL + Qdrant + Redis)")
            # Inicia health check background
            _health_task = asyncio.create_task(_health_loop())
            return
        except Exception as e:
            logger.warning(f"ChromaStore init attempt {attempt + 1} failed: {e}")
            _store = None
            _initialized = False
            if attempt < _MAX_INIT_RETRIES - 1:
                await asyncio.sleep(_INIT_RETRY_DELAY)

    logger.error("All ChromaStore init attempts failed")
    raise RuntimeError("Failed to initialize ChromaStore after multiple retries")


async def _health_loop() -> None:
    """Background task que verifica saúde do ChromaDB e reconecta se necessário."""
    global _store, _initialized
    while True:
        try:
            await asyncio.sleep(_HEALTH_CHECK_INTERVAL)
            if _store and _initialized:
                ok = await _store.ensure_connection()
                if not ok:
                    logger.warning("ChromaDB health check failed — will retry")
                else:
                    _initialized = True
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.exception(f"Health check error: {e}")


async def shutdown_memory_managers_async() -> None:
    global _store, _initialized, _health_task

    if _health_task:
        _health_task.cancel()
        try:
            await _health_task
        except asyncio.CancelledError:
            pass
        _health_task = None

    if _initialized and _store:
        await _store.shutdown()

    _store = None
    _initialized = False
    logger.info("ChromaStore shut down")


def get_store() -> Optional[ChromaStore]:
    return _store


def get_postgres_memory() -> Optional[ChromaStore]:
    """Returns ChromaStore (replaces PostgresMemoryManager)."""
    return _store


def get_qdrant_memory() -> Optional[ChromaStore]:
    """Returns ChromaStore (replaces QdrantMemoryManager)."""
    return _store


def get_redis_memory() -> Optional[ChromaStore]:
    """Returns ChromaStore (replaces RedisMemoryManager)."""
    return _store


def get_embedding_router():
    return None


def is_initialized() -> bool:
    return _initialized
