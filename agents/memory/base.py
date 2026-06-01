"""
Abstract base class for memory managers in the Kirin cognitive runtime.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

class BaseMemoryManager(ABC):
    """
    Abstract base class for all memory managers.
    Defines the interface for storing and retrieving cognitive state.
    """

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the memory manager connection/resources."""
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """Shutdown and cleanup resources."""
        pass

    @abstractmethod
    async def store_lead_memory(self, lead_id: str, memory_type: str, data: Dict[str, Any]) -> bool:
        """
        Store memory associated with a lead.

        Args:
            lead_id: Unique identifier for the lead
            memory_type: Type of memory (e.g., 'enrichment', 'interaction', 'preference')
            data: Memory data to store

        Returns:
            True if stored successfully, False otherwise
        """
        pass

    @abstractmethod
    async def retrieve_lead_memory(self, lead_id: str, memory_type: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve memory associated with a lead.

        Args:
            lead_id: Unique identifier for the lead
            memory_type: Type of memory to retrieve

        Returns:
            Memory data if found, None otherwise
        """
        pass

    @abstractmethod
    async def search_similar_memories(self, query_vector: List[float], memory_type: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search for memories similar to a query vector.

        Args:
            query_vector: Embedding vector to search for
            memory_type: Type of memory to search in
            limit: Maximum number of results to return

        Returns:
            List of similar memories with metadata
        """
        pass

    @abstractmethod
    async def store_conversation_context(self, lead_id: str, context: Dict[str, Any], ttl: int = 3600) -> bool:
        """
        Store short-term conversation context with TTL.

        Args:
            lead_id: Unique identifier for the lead
            context: Context data to store
            ttl: Time to live in seconds (default 1 hour)

        Returns:
            True if stored successfully, False otherwise
        """
        pass

    @abstractmethod
    async def retrieve_conversation_context(self, lead_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve short-term conversation context.

        Args:
            lead_id: Unique identifier for the lead

        Returns:
            Context data if found and not expired, None otherwise
        """
        pass

    # ─── Cache operations (Redis-backed) ─────────────────────────────────────

    @abstractmethod
    async def cache_get(self, key: str) -> Optional[Any]:
        """
        Get a value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value if found, None otherwise
        """
        pass

    @abstractmethod
    async def cache_set(self, key: str, value: Any, ttl_seconds: int = 3600) -> bool:
        """
        Set a value in cache with TTL.

        Args:
            key: Cache key
            value: Value to cache (must be JSON-serializable)
            ttl_seconds: Time to live in seconds

        Returns:
            True if stored successfully
        """
        pass

    @abstractmethod
    async def cache_delete(self, key: str) -> bool:
        """
        Delete a value from cache.

        Args:
            key: Cache key

        Returns:
            True if deleted successfully
        """
        pass

    # ─── Structured storage operations (PostgreSQL-backed) ───────────────────

    @abstractmethod
    async def store(self, namespace: str, key: str, data: Dict[str, Any]) -> bool:
        """
        Store structured data.

        Args:
            namespace: Data namespace (e.g., 'resonance_cluster', 'lead_profile')
            key: Unique key within namespace
            data: Data to store

        Returns:
            True if stored successfully
        """
        pass

    @abstractmethod
    async def retrieve(self, namespace: str, key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve structured data.

        Args:
            namespace: Data namespace
            key: Unique key

        Returns:
            Data if found, None otherwise
        """
        pass

    @abstractmethod
    async def delete(self, namespace: str, key: str) -> bool:
        """
        Delete structured data.

        Args:
            namespace: Data namespace
            key: Unique key

        Returns:
            True if deleted successfully
        """
        pass

    @abstractmethod
    async def search_by_text(self, namespace: str, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search structured data by text pattern.

        Args:
            namespace: Data namespace
            query: Text search pattern
            limit: Maximum number of results

        Returns:
            List of matching records
        """
        pass
