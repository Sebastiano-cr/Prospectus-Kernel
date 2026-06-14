"""
Testes de graceful degradation do ChromaStore.
Verifica que operações falham graciosamente com ChromaDB offline,
e que ensure_connection reconecta após reconnect do banco.
"""
import asyncio
import tempfile

from src.store import ChromaStore


def _run(coro):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def test_store_offline_returns_sentinel():
    """Sem inicializar, todas as operações retornam valores sentinela."""
    tmp = tempfile.mkdtemp()
    store = ChromaStore(path=tmp)

    val = _run(store.retrieve_lead_memory("lead_x", "dossie"))
    assert val is None

    val = _run(store.search_by_text("mensagens", "teste"))
    assert val == []

    val = _run(store.search_text("mensagens", "teste"))
    assert val == []

    ok = _run(store.store_lead_memory("lead_x", "dossie", {"a": 1}))
    assert ok is False

    ok = _run(store.store_text("mensagens", "texto", {"a": 1}))
    assert ok is False

    ok = _run(store.delete_lead_memory("lead_x", "dossie"))
    assert ok is False


def test_ready_returns_false_when_offline():
    """ready() retorna False sem ChromaDB."""
    store = ChromaStore()
    ok = _run(store.ready())
    assert ok is False


def test_ensure_connection_works():
    """ensure_connection retorna True quando ChromaDB está acessível."""
    tmp = tempfile.mkdtemp()
    store = ChromaStore(path=tmp)
    _run(store.initialize())

    ok = _run(store.ensure_connection())
    assert ok is True
    _run(store.shutdown())


def test_ensure_connection_recovers_after_shutdown():
    """ensure_connection reconecta após shutdown simulado (cliente nulo)."""
    tmp = tempfile.mkdtemp()
    store = ChromaStore(path=tmp)
    _run(store.initialize())

    # Simula que ChromaDB caiu
    store._initialized = False
    store._client = None

    ok = _run(store.ensure_connection())
    assert ok is True

    # Deve conseguir operar novamente
    ok = _run(store.store_lead_memory("lead_1", "teste", {"dado": "ok"}))
    assert ok is True

    _run(store.shutdown())


def test_operations_work_after_reconnect():
    """Após reconnect, operações funcionam normalmente com dados novos."""
    tmp = tempfile.mkdtemp()
    store = ChromaStore(path=tmp)
    _run(store.initialize())

    store._initialized = False
    store._client = None

    _run(store.ensure_connection())

    _run(store.store_lead_memory("lead_r", "teste", {"valor": "reconectou"}))
    result = _run(store.retrieve_lead_memory("lead_r", "teste"))
    assert result is not None
    assert result["valor"] == "reconectou"

    _run(store.shutdown())
