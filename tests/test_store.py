"""
Testes para src/store.py — ChromaStore (sync wrappers).
"""
import asyncio
import pytest
from src.store import ChromaStore


def _run(coro):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@pytest.fixture
def store(tmp_path):
    s = ChromaStore(path=str(tmp_path / "chroma_test"))
    _run(s.initialize())
    return s


def test_initialize_and_shutdown(tmp_path):
    s = ChromaStore(path=str(tmp_path / "chroma_init"))
    assert s._initialized is False
    _run(s.initialize())
    assert s._initialized is True
    _run(s.shutdown())
    assert s._client is None


def test_store_and_retrieve_lead_memory(store):
    _run(store.store_lead_memory("lead_1", "dossie", {"perfil": "teste"}))
    result = _run(store.retrieve_lead_memory("lead_1", "dossie"))
    assert result is not None
    assert result["perfil"] == "teste"


def test_cache_get_set(store):
    _run(store.cache_set("chave_teste", 42, ttl_seconds=60))
    val = _run(store.cache_get("chave_teste"))
    assert val == 42


def test_cache_miss(store):
    val = _run(store.cache_get("inexistente"))
    assert val is None


def test_cache_delete(store):
    _run(store.cache_set("para_deletar", "valor", ttl_seconds=60))
    _run(store.cache_delete("para_deletar"))
    val = _run(store.cache_get("para_deletar"))
    assert val is None


def test_cache_ttl_expiry(store):
    _run(store.cache_set("ttl_test", "valor", ttl_seconds=0))
    val = _run(store.cache_get("ttl_test"))
    assert val is None


def test_check_duplicate(store):
    assert _run(store.check_duplicate("dup_key_123")) is False
    _run(store.store_dedup("dup_key_123", {"data": "test"}))
    assert _run(store.check_duplicate("dup_key_123")) is True


def test_get_dedup(store):
    _run(store.store_dedup("dedup_key_456", {"name": "teste"}))
    result = _run(store.get_dedup("dedup_key_456"))
    assert result is not None
    assert result["name"] == "teste"


def test_delete_lead_memory(store):
    _run(store.store_lead_memory("lead_del", "dossie", {"data": "valioso"}))
    _run(store.delete_lead_memory("lead_del", "dossie"))
    result = _run(store.retrieve_lead_memory("lead_del", "dossie"))
    assert result is None


def test_store_text_and_search(store):
    _run(store.store_text("kirin_test", "cliente reclama de preço alto", {"source": "reddit"}))
    _run(store.store_text("kirin_test", "produto resolveu meu problema", {"source": "telegram"}))
    results = _run(store.search_text("kirin_test", "reclamação de preço", limit=5))
    assert len(results) >= 1


def test_retrieve_missing_lead_memory(store):
    result = _run(store.retrieve_lead_memory("nonexistent", "dossie"))
    assert result is None


def test_ready_before_initialization(tmp_path):
    s = ChromaStore(path=str(tmp_path / "chroma_ready"))
    assert _run(s.ready()) is False


def test_ready_after_initialization(store):
    assert _run(store.ready()) is True


def test_ready_after_shutdown(tmp_path):
    s = ChromaStore(path=str(tmp_path / "chroma_ready2"))
    _run(s.initialize())
    assert _run(s.ready()) is True
    _run(s.shutdown())
    assert _run(s.ready()) is False
