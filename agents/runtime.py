"""
Global runtime state for the Kirin cognitive runtime.
Holds initialized memory managers and other shared resources.
"""
import logging
from typing import Optional
from agents.memory.postgres_memory import PostgresMemoryManager
from agents.memory.qdrant_memory import QdrantMemoryManager
from agents.memory.redis_memory import RedisMemoryManager

logger = logging.getLogger(__name__)

# Global instances of memory managers
_postgres_memory: Optional[PostgresMemoryManager] = None
_qdrant_memory: Optional[QdrantMemoryManager] = None
_redis_memory: Optional[RedisMemoryManager] = None
_embedding_router = None  # lazy import, defined in initialize
_initialized: bool = False

async def initialize_memory_managers(config: dict) -> None:
    """
    Asynchronously initialize all memory managers based on the provided configuration.

    Args:
        config: Dictionary with keys 'postgres', 'qdrant', 'redis' each containing connection parameters.
                Optional key 'embedding_router' with 'enabled' bool to activate EmbeddingRouter.
    """
    global _postgres_memory, _qdrant_memory, _redis_memory, _embedding_router, _initialized

    if _initialized:
        logger.warning("Memory managers already initialized. Skipping re-initialization.")
        return

    try:
        # Inicializa EmbeddingRouter se configurado
        router = None
        if config.get("embedding_router", {}).get("enabled", False):
            try:
                from agents.memory.embedding_router import create_default_router
                router = create_default_router()
                logger.info(f"EmbeddingRouter initialized. Active: {router.active_name}, "
                           f"Strategies: {list(router.list_strategies().keys())}")
            except Exception as e:
                logger.warning(f"Failed to initialize EmbeddingRouter: {e}")
        _embedding_router = router

        if "postgres" in config:
            postgres_config = config["postgres"]
            _postgres_memory = PostgresMemoryManager(
                host=postgres_config.get("host", "localhost"),
                port=postgres_config.get("port", 5432),
                database=postgres_config.get("database", "kirin"),
                user=postgres_config.get("user", "kirin"),
                password=postgres_config.get("password", "")
            )
            await _postgres_memory.initialize()

        if "qdrant" in config:
            qdrant_config = config["qdrant"]
            _qdrant_memory = QdrantMemoryManager(
                host=qdrant_config.get("host", "localhost"),
                port=qdrant_config.get("port", 6333),
                embedding_router=router
            )
            await _qdrant_memory.initialize()

        if "redis" in config:
            redis_config = config["redis"]
            _redis_memory = RedisMemoryManager(
                host=redis_config.get("host", "localhost"),
                port=redis_config.get("port", 6379),
                password=redis_config.get("password"),
                db=redis_config.get("db", 0)
            )
            await _redis_memory.initialize()

        _initialized = True
        logger.info("Memory managers initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize memory managers: {e}")
        _initialized = False
        await shutdown_memory_managers_async()
        raise

async def shutdown_memory_managers_async() -> None:
    """
    Asynchronously shutdown all memory manager instances.
    """
    global _postgres_memory, _qdrant_memory, _redis_memory, _embedding_router, _initialized

    if not _initialized:
        return

    try:
        if _postgres_memory:
            await _postgres_memory.shutdown()
        if _qdrant_memory:
            await _qdrant_memory.shutdown()
        if _redis_memory:
            await _redis_memory.shutdown()
    except Exception as e:
        logger.error(f"Error shutting down memory managers: {e}")
    finally:
        _postgres_memory = None
        _qdrant_memory = None
        _redis_memory = None
        _embedding_router = None
        _initialized = False
        logger.info("Memory managers shut down")

def get_postgres_memory() -> Optional[PostgresMemoryManager]:
    return _postgres_memory

def get_qdrant_memory() -> Optional[QdrantMemoryManager]:
    return _qdrant_memory

def get_redis_memory() -> Optional[RedisMemoryManager]:
    return _redis_memory

def get_embedding_router():
    """Get the EmbeddingRouter instance, if initialized."""
    return _embedding_router

def is_initialized() -> bool:
    return _initialized
