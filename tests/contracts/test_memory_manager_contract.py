"""
Testes de contrato para IMemoryManager.
"""
import pytest
from agents.ports.memory_manager import IMemoryManager, MemoryResult


class TestMemoryManagerContract:
    """Testes de contrato para qualquer implementação de IMemoryManager."""

    @pytest.fixture
    def memory(self) -> IMemoryManager:
        """Deve ser substituído por cada implementação nos testes."""
        raise NotImplementedError("Subclass must provide memory fixture")

    @pytest.mark.asyncio
    async def test_store_and_retrieve(self, memory: IMemoryManager):
        namespace = "test_namespace"
        key = "test_key"
        data = {"field1": "value1", "field2": 42}

        stored = await memory.store(namespace, key, data)
        assert stored is True

        retrieved = await memory.retrieve(namespace, key)
        assert retrieved is not None
        assert retrieved["field1"] == "value1"
        assert retrieved["field2"] == 42

    @pytest.mark.asyncio
    async def test_delete(self, memory: IMemoryManager):
        namespace = "test_delete"
        key = "test_key"
        data = {"field1": "value1"}

        await memory.store(namespace, key, data)
        deleted = await memory.delete(namespace, key)
        assert deleted is True

        retrieved = await memory.retrieve(namespace, key)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_cache_set_and_get(self, memory: IMemoryManager):
        key = "test_cache_key"
        value = {"cached": True}

        set_result = await memory.cache_set(key, value, ttl_seconds=60)
        assert set_result is True

        retrieved = await memory.cache_get(key)
        assert retrieved is not None
        assert retrieved["cached"] is True

    @pytest.mark.asyncio
    async def test_cache_delete(self, memory: IMemoryManager):
        key = "test_cache_delete"
        value = {"cached": True}

        await memory.cache_set(key, value, ttl_seconds=60)
        deleted = await memory.cache_delete(key)
        assert deleted is True

        retrieved = await memory.cache_get(key)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_search_similar(self, memory: IMemoryManager):
        namespace = "test_search"
        query_vector = [0.1, 0.2, 0.3]

        results = await memory.search_similar(query_vector, namespace, limit=5)
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_initialize_and_shutdown(self, memory: IMemoryManager):
        await memory.initialize()
        await memory.shutdown()
