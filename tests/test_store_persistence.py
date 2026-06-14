"""
Teste de persistência do ChromaStore — dados sobrevivem a restart.
"""
import asyncio
import tempfile
import os
from src.store import ChromaStore


def _run(coro):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def test_lead_memory_survives_restart():
    """Escreve lead memory, fecha store, abre novo store, lê de volta."""
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "chroma_persist")

    # Primeira vida
    s1 = ChromaStore(path=path)
    _run(s1.initialize())
    _run(s1.store_lead_memory("lead_42", "dossie", {"perfil": "sobreviveu"}))
    _run(s1.shutdown())

    # Segunda vida — mesmo path
    s2 = ChromaStore(path=path)
    _run(s2.initialize())
    result = _run(s2.retrieve_lead_memory("lead_42", "dossie"))
    _run(s2.shutdown())

    assert result is not None, "Dado deveria persistir entre restarts"
    assert result["perfil"] == "sobreviveu"


def test_text_search_survives_restart():
    """Escreve texto vetorizado, fecha, abre, busca."""
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "chroma_search")

    s1 = ChromaStore(path=path)
    _run(s1.initialize())
    _run(s1.store_text("mensagens", "cliente reclama de preço alto", {"source": "reddit"}))
    _run(s1.shutdown())

    s2 = ChromaStore(path=path)
    _run(s2.initialize())
    results = _run(s2.search_text("mensagens", "reclamação de preço", limit=5))
    _run(s2.shutdown())

    assert len(results) >= 1
    assert "preço" in results[0].get("text", "")


def test_multiple_memory_types_persist():
    """Múltiplos tipos de memória sobrevivem ao restart."""
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "chroma_multi")

    s1 = ChromaStore(path=path)
    _run(s1.initialize())
    _run(s1.store_lead_memory("lead_1", "dossie", {"tipo": "dossie"}))
    _run(s1.store_lead_memory("lead_1", "score", {"valor": 85}))
    _run(s1.shutdown())

    s2 = ChromaStore(path=path)
    _run(s2.initialize())
    dossie = _run(s2.retrieve_lead_memory("lead_1", "dossie"))
    score = _run(s2.retrieve_lead_memory("lead_1", "score"))
    _run(s2.shutdown())

    assert dossie["tipo"] == "dossie"
    assert score["valor"] == 85


def test_cache_does_not_persist():
    """Cache LRU é volátil — não sobrevive a restart."""
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "chroma_cache")

    s1 = ChromaStore(path=path)
    _run(s1.initialize())
    _run(s1.cache_set("chave_volatil", "valor", ttl_seconds=3600))
    _run(s1.shutdown())

    s2 = ChromaStore(path=path)
    _run(s2.initialize())
    val = _run(s2.cache_get("chave_volatil"))
    _run(s2.shutdown())

    assert val is None, "Cache não deve persistir entre restart — é só LRU em RAM"
