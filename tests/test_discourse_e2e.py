"""
Teste end-to-end do pipeline de Discourse com LLM real (LiteLLM).

Requer LITELLM_URL configurado (default: http://litellm:4000).
Pula automaticamente se LiteLLM não estiver acessível.

Uso:
    LITELLM_URL=http://localhost:4000 python -m pytest tests/test_discourse_e2e.py -v
"""
import os
import pytest
from src.analysis.analyzer import ingest_discourse, analyze_language_game


LITELLM_URL = os.getenv("LITELLM_URL", "http://litellm:4000")
API_KEY = os.getenv("DEEPSEEK_CHAT_API_KEY", "sk-placeholder")


@pytest.mark.skipif(
    not os.getenv("LITELLM_URL"),
    reason="LITELLM_URL not set — skipping real LLM test",
)
@pytest.mark.asyncio
async def test_ingest_discourse_with_litellm():
    """Ingere um fragmento real de discurso via LiteLLM."""
    fragment = await ingest_discourse(
        text="Preço muito alto, não vale o que cobram. Tô procurando alternativa.",
        source="reddit",
        context="discussão sobre ferramentas SaaS",
        litellm_url=LITELLM_URL,
        api_key=API_KEY,
    )

    assert fragment is not None
    assert fragment.get("text")
    assert fragment.get("source") == "reddit"
    assert fragment.get("emotion")
    assert fragment.get("topic")
    assert "fragment_id" in fragment
    assert "timestamp" in fragment
    assert fragment.get("ingestion_success", True) is not False


@pytest.mark.skipif(
    not os.getenv("LITELLM_URL"),
    reason="LITELLM_URL not set — skipping real LLM test",
)
@pytest.mark.asyncio
async def test_discourse_pipeline_with_litellm():
    """Pipeline completo: ingest → language game → análise."""
    fragment = await ingest_discourse(
        text="Ninguém mais compra site. Tudo mundo quer só Instagram e TikTok.",
        source="youtube",
        context="comentário em vídeo sobre web design",
        litellm_url=LITELLM_URL,
        api_key=API_KEY,
    )
    assert fragment is not None

    analysis = await analyze_language_game(
        fragment,
        litellm_url=LITELLM_URL,
        api_key=API_KEY,
    )

    assert analysis is not None
    assert analysis.get("surface_problem")
    assert analysis.get("hidden_problem")
    assert analysis.get("belief")
    assert analysis.get("tension")
    assert isinstance(analysis.get("possible_solutions"), list)
    assert isinstance(analysis.get("tension_score"), (int, float))


@pytest.mark.skipif(
    not os.getenv("LITELLM_URL"),
    reason="LITELLM_URL not set — skipping real LLM test",
)
@pytest.mark.asyncio
async def test_discourse_pipeline_english():
    """Pipeline completo com locale=en e texto em inglês."""
    from src.locale import get_locale
    locale = get_locale("en")

    fragment = await ingest_discourse(
        text="This tool is way too expensive for what it does. Looking for alternatives.",
        source="reddit",
        context="SaaS pricing discussion",
        litellm_url=LITELLM_URL,
        api_key=API_KEY,
        locale=locale,
    )
    assert fragment is not None
    assert fragment.get("emotion")
    assert fragment.get("topic")
