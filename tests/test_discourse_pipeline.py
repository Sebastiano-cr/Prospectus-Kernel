"""
Testes com mock do LLM para o pipeline completo de Discourse.
"""
import pytest
from unittest.mock import AsyncMock, patch

from agents.ports.llm_client import LLMResponse
from src.analysis.analyzer import ingest_discourse, analyze_language_game


LLM_INGESTION_RESPONSE = '''{
    "text": "Preço muito alto para meu orçamento",
    "source": "reddit",
    "context": "discussão sobre ferramentas",
    "emotion": "frustration",
    "topic": "pricing"
}'''

LLM_ANALYSIS_RESPONSE = '''{
    "surface_problem": "preço alto",
    "hidden_problem": "orçamento limitado",
    "belief": "ferramentas caras não valem o investimento",
    "fear": "gastar dinheiro em algo que não funciona",
    "hidden_desire": "validação antes de comprar",
    "objection_type": "price",
    "identity_marker": "bootstrapper",
    "market_stage": "growing",
    "tension": "quer resolver mas tem medo de perder dinheiro",
    "framing_pattern": "pragmatism",
    "social_context": "fórum de startups",
    "discourse_role": "skeptic",
    "language_game": "risk vs reward",
    "possible_solutions": ["free trial", "social proof", "garantia"]
}'''


@pytest.mark.asyncio
async def test_ingest_discourse_mock():
    from agents.factory import ServiceFactory
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = LLMResponse(
        content=LLM_INGESTION_RESPONSE, model="deepseek-chat"
    )

    with patch.object(ServiceFactory, "get_llm_client", return_value=mock_llm):
        result = await ingest_discourse(
            text="Preço muito alto",
            source="reddit",
            context="forum",
            litellm_url="http://mock",
            api_key="mock",
        )

    assert result["text"] == "Preço muito alto para meu orçamento"
    assert result["source"] == "reddit"
    assert result["emotion"] == "frustration"
    assert result["topic"] == "pricing"
    assert "fragment_id" in result
    assert "timestamp" in result


@pytest.mark.asyncio
async def test_ingest_discourse_fallback_on_llm_error():
    from agents.factory import ServiceFactory
    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(side_effect=Exception("LLM unavailable"))

    with patch.object(ServiceFactory, "get_llm_client", return_value=mock_llm):
        result = await ingest_discourse(
            text="Preço muito alto",
            source="reddit",
            context="forum",
            litellm_url="http://mock",
            api_key="mock",
        )

    assert not result.get("ingestion_success", True)
    assert "LLM unavailable" in result.get("ingestion_error", "")


@pytest.mark.asyncio
async def test_analyze_language_game_mock():
    from agents.factory import ServiceFactory
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = LLMResponse(
        content=LLM_ANALYSIS_RESPONSE, model="deepseek-chat"
    )

    fragment = {
        "text": "Preço muito alto para meu orçamento",
        "source": "reddit",
        "context": "discussão sobre ferramentas",
        "emotion": "frustration",
        "topic": "pricing",
        "fragment_id": "abc123",
    }

    with patch.object(ServiceFactory, "get_llm_client", return_value=mock_llm):
        result = await analyze_language_game(
            fragment,
            litellm_url="http://mock",
            api_key="mock",
        )

    assert result["surface_problem"] == "preço alto"
    assert result["hidden_problem"] == "orçamento limitado"
    assert result["objection_type"] == "price"
    assert result["discourse_role"] == "skeptic"
    assert isinstance(result["possible_solutions"], list)
    assert "free trial" in result["possible_solutions"]
    assert isinstance(result.get("tension_score"), (int, float))


@pytest.mark.asyncio
async def test_analyze_language_game_fallback_on_empty_text():
    fragment = {
        "text": "",
        "source": "reddit",
        "context": "",
        "emotion": "neutral",
        "topic": "unknown",
    }

    result = await analyze_language_game(
        fragment,
        litellm_url="http://mock",
        api_key="mock",
    )

    assert result.get("analysis_fallback") is True
    assert result["surface_problem"] == "unknown"
