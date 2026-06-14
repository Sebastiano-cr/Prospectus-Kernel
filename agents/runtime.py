"""
Global runtime state for the Kirin cognitive runtime.
Uses ChromaStore as the single unified storage backend.
"""
import asyncio
import logging
from typing import Optional
from src.store import ChromaStore

logger = logging.getLogger(__name__)

_store: Optional[ChromaStore] = None
_initialized: bool = False
_MAX_INIT_RETRIES = 5
_INIT_RETRY_DELAY = 3.0


async def initialize_memory_managers(config: dict) -> None:
    global _store, _initialized

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
            return
        except Exception as e:
            logger.warning(f"ChromaStore init attempt {attempt + 1} failed: {e}")
            _store = None
            _initialized = False
            if attempt < _MAX_INIT_RETRIES - 1:
                await asyncio.sleep(_INIT_RETRY_DELAY)

    logger.error("All ChromaStore init attempts failed")
    raise RuntimeError("Failed to initialize ChromaStore after multiple retries")


async def shutdown_memory_managers_async() -> None:
    global _store, _initialized

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
