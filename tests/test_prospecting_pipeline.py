"""
Teste E2E do pipeline de prospecção: enrich → score → message.
Mocka o LLM em cada etapa, verifica compatibilidade de schema entre fases.
"""
import pytest
from unittest.mock import AsyncMock, patch
from agents.llm_client import LLMResponse


@pytest.fixture
def sample_lead():
    return {
        "name": "Restaurante Teste",
        "address": "Rua Exemplo, 123",
        "phone": "+55 11 99999-9999",
        "website": "",
        "instagram_username": "",
        "rating": 4.2,
        "google_maps_url": "https://maps.google.com/?cid=teste123",
    }


LLM_RESPONSES = {
    "enricher": (
        '{"resumo_perfil": "Restaurante tradicional com comida caseira e ambiente familiar",'
        '"pontos_fracos": ["Nao possui website", "Pouca presenca digital"],'
        '"oportunidades": ["Criar site profissional", "Implementar delivery online"],'
        '"maturidade_digital": "baixo"}'
    ),
    "scorer": (
        '{"score": 65, "justification": "Lead possui pontos fracos claros mas oportunidades acionaveis.",'
        '"faixa": "morno"}'
    ),
    "messenger": (
        '{"message": "Ola Restaurante Teste! Notamos que sua presenca digital pode ser fortalecida. Podemos ajudar com um site profissional e delivery online. Vamos conversar?"}'
    ),
}


@pytest.mark.asyncio
async def test_full_prospecting_pipeline(sample_lead):
    """Enrich → Score → Message: output de cada fase é input válido da próxima."""
    from agents.enricher import enrich_lead
    from agents.scorer import score_lead
    from agents.messenger import generate_message

    # ── Fase 1: Enrich ─────────────────────────────────────────────────
    with patch("agents.enricher.llm_complete", new_callable=AsyncMock) as mock_enrich:
        mock_enrich.return_value = LLMResponse(content=LLM_RESPONSES["enricher"], model="qwen-vl-max")
        enriched = await enrich_lead(sample_lead, litellm_url="http://test:4000", api_key="test-key")

    assert enriched["enrichment_success"] is True
    assert "dossie" in enriched
    dossie = enriched["dossie"]
    assert dossie["resumo_perfil"]
    assert isinstance(dossie["pontos_fracos"], list)
    assert len(dossie["pontos_fracos"]) >= 1
    assert isinstance(dossie["oportunidades"], list)
    assert dossie["maturidade_digital"] in ("alto", "médio", "baixo")

    # ── Fase 2: Score ──────────────────────────────────────────────────
    with patch("agents.scorer.llm_complete", new_callable=AsyncMock) as mock_score:
        mock_score.return_value = LLMResponse(content=LLM_RESPONSES["scorer"], model="deepseek-chat")
        scored = await score_lead(dossie, litellm_url="http://test:4000", api_key="test-key")

    assert scored.get("enrichment_success", True) is True
    assert "score" in scored
    assert isinstance(scored["score"], (int, float))
    assert 0 <= scored["score"] <= 100

    # ── Fase 3: Message ────────────────────────────────────────────────
    scored_lead = {
        **sample_lead,
        "score": scored["score"],
        "faixa": scored.get("faixa", "morno"),
        "status": "qualificado",
        "dossie": dossie,
    }

    with patch("agents.messenger.llm_complete", new_callable=AsyncMock) as mock_msg:
        mock_msg.return_value = LLMResponse(content=LLM_RESPONSES["messenger"], model="deepseek-chat")
        message = await generate_message(scored_lead, litellm_url="http://test:4000", api_key="test-key")

    assert message is not None
    assert len(message) > 0
    assert "Restaurante Teste" in message

    # ── Verificação de consistência entre fases ─────────────────────────
    assert dossie["maturidade_digital"] == "baixo", "Lead com maturidade baixa deve ter score coerente"


@pytest.mark.asyncio
async def test_pipeline_with_en_locale(sample_lead):
    """Pipeline completo com locale=en."""
    from agents.enricher import enrich_lead
    from agents.scorer import score_lead
    from agents.messenger import generate_message
    from src.locale import get_locale

    locale = get_locale("en")

    with patch("agents.enricher.llm_complete", new_callable=AsyncMock) as mock_enrich:
        mock_enrich.return_value = LLMResponse(
            content='{"resumo_perfil": "Traditional family restaurant", "pontos_fracos": ["no website"], "oportunidades": ["online delivery"], "maturidade_digital": "low"}',
            model="qwen-vl-max",
        )
        enriched = await enrich_lead(sample_lead, litellm_url="http://test:4000", api_key="test-key", locale=locale)

    assert enriched["enrichment_success"] is True
    assert enriched["dossie"]["resumo_perfil"] == "Traditional family restaurant"

    dossie = enriched["dossie"]

    with patch("agents.scorer.llm_complete", new_callable=AsyncMock) as mock_score:
        mock_score.return_value = LLMResponse(
            content='{"score": 50, "justification": "Medium potential", "faixa": "warm"}',
            model="deepseek-chat",
        )
        scored = await score_lead(dossie, litellm_url="http://test:4000", api_key="test-key", locale=locale)

    assert scored["score"] == 50

    scored_lead = {**sample_lead, "score": 50, "faixa": "warm", "status": "qualified", "dossie": dossie}

    with patch("agents.messenger.llm_complete", new_callable=AsyncMock) as mock_msg:
        mock_msg.return_value = LLMResponse(
            content='{"message": "Hi Restaurante Teste! We noticed your online presence could be stronger. Can we help?"}',
            model="deepseek-chat",
        )
        message = await generate_message(scored_lead, litellm_url="http://test:4000", api_key="test-key", locale=locale)

    assert message is not None
    assert "Restaurante Teste" in message


@pytest.mark.asyncio
async def test_pipeline_schema_contract(sample_lead):
    """Verifica que o schema é compatível entre enrich → score → message."""
    from agents.enricher import enrich_lead
    from agents.scorer import score_lead
    from agents.messenger import generate_message

    with patch("agents.enricher.llm_complete", new_callable=AsyncMock) as mock_enrich:
        mock_enrich.return_value = LLMResponse(content=LLM_RESPONSES["enricher"], model="qwen-vl-max")
        enriched = await enrich_lead(sample_lead, litellm_url="http://test:4000", api_key="test-key")

    dossie = enriched["dossie"]

    assert "resumo_perfil" in dossie
    assert "pontos_fracos" in dossie
    assert "oportunidades" in dossie
    assert "maturidade_digital" in dossie

    with patch("agents.scorer.llm_complete", new_callable=AsyncMock) as mock_score:
        mock_score.return_value = LLMResponse(content=LLM_RESPONSES["scorer"], model="deepseek-chat")
        scored = await score_lead(dossie, litellm_url="http://test:4000", api_key="test-key")

    assert "score" in scored
    assert "faixa" in scored

    scored_lead = {**sample_lead, "score": scored["score"], "faixa": scored.get("faixa"), "status": "qualificado", "dossie": dossie}
    assert "name" in scored_lead
    assert "score" in scored_lead
    assert "faixa" in scored_lead
    assert "dossie" in scored_lead

    with patch("agents.messenger.llm_complete", new_callable=AsyncMock) as mock_msg:
        mock_msg.return_value = LLMResponse(content=LLM_RESPONSES["messenger"], model="deepseek-chat")
        message = await generate_message(scored_lead, litellm_url="http://test:4000", api_key="test-key")

    assert message is not None
