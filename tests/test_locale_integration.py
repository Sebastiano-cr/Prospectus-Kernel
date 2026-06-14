"""
Testes de integração — locale espanhol com agentes mockados.
"""
import pytest
from unittest.mock import AsyncMock, patch
from agents.ports.llm_client import LLMResponse
from src.locale import get_locale


class TestESLocaleEnricher:
    """Testa o enricher com locale=es e LLM mockado."""

    @pytest.mark.asyncio
    async def test_enrich_prompt_in_spanish(self):
        """Verifica que o prompt gerado para ES está em espanhol."""
        locale = get_locale("es")
        from agents.enricher import _build_enrichment_prompt

        prompt = _build_enrichment_prompt({
            "name": "Pizzaría Bella",
            "address": "Calle Principal 123",
            "phone": "+34 666 000 000",
            "website": "",
            "instagram_username": "",
            "google_maps_data": {},
            "instagram_data": {},
        }, locale)

        assert "Eres un especialista" in prompt
        assert "Pizzaría Bella" in prompt
        assert "No disponible" in prompt

    def test_parse_enrichment_text_es(self):
        """Verifica que _parse_enrichment_text funciona com seções em espanhol."""
        from agents.enricher import _parse_enrichment_text
        locale = get_locale("es")

        text = """sección de perfil: Pequeña pizzería familiar en el centro
sección de puntos débiles:
- no tiene sitio web
- poca presencia digital
sección de oportunidades:
- crear sitio web
- delivery online
sección de madurez digital: bajo"""

        result = _parse_enrichment_text(text, locale)
        assert "Pequeña pizzería familiar" in result.get("resumo_perfil", "")
        assert "no tiene sitio web" in result.get("pontos_fracos", [])
        assert "crear sitio web" in result.get("oportunidades", [])
        assert result.get("maturidade_digital") == "baixo"

    @pytest.mark.asyncio
    async def test_enrich_lead_es_locale(self, sample_lead):
        """Testa enrich_lead completo com locale=es e LLM mockado."""
        from agents.enricher import enrich_lead
        from agents.factory import ServiceFactory
        locale = get_locale("es")

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = LLMResponse(
            content='{"resumo_perfil": "Pizzería familiar auténtica", "pontos_fracos": ["sin web"], "oportunidades": ["delivery"], "maturidade_digital": "bajo"}',
            model="qwen-vl-max"
        )

        with patch.object(ServiceFactory, "get_llm_client", return_value=mock_llm):
            result = await enrich_lead(sample_lead, litellm_url="http://test:4000", api_key="test-key", locale=locale)

        assert result["enrichment_success"] is True
        assert result["dossie"]["resumo_perfil"] == "Pizzería familiar auténtica"
        assert "sin web" in result["dossie"]["pontos_fracos"]
        assert "delivery" in result["dossie"]["oportunidades"]


class TestESLocaleScorer:
    """Testa o scorer com locale=es."""

    @pytest.mark.asyncio
    async def test_score_lead_es_locale(self, sample_dossie):
        from agents.scorer import score_lead
        from agents.factory import ServiceFactory
        locale = get_locale("es")

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = LLMResponse(
            content='{"score": 65, "justification": "tiene oportunidades", "category": "tibio"}',
            model="deepseek-chat"
        )

        with patch.object(ServiceFactory, "get_llm_client", return_value=mock_llm):
            result = await score_lead(sample_dossie, litellm_url="http://test:4000", api_key="test-key", locale=locale)

        assert result.get("enrichment_success", True) is True
        assert result["score"] == 65


class TestESLocaleMessenger:
    """Testa o messenger com locale=es."""

    @pytest.mark.asyncio
    async def test_generate_message_es_locale(self, sample_scored_lead):
        from agents.messenger import generate_message
        from agents.factory import ServiceFactory
        locale = get_locale("es")

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = LLMResponse(
            content='{"message": "¡Hola! Queremos ayudarte a crecer tu negocio."}',
            model="deepseek-chat"
        )

        with patch.object(ServiceFactory, "get_llm_client", return_value=mock_llm):
            result = await generate_message(sample_scored_lead, litellm_url="http://test:4000", api_key="test-key", locale=locale)

        assert result is not None
        assert "Hola" in result


class TestESLocaleResearcher:
    """Testa o researcher com locale=es."""

    @pytest.mark.asyncio
    async def test_research_lead_es_locale(self, sample_lead):
        from agents.researcher import research_lead
        from agents.factory import ServiceFactory
        locale = get_locale("es")

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = LLMResponse(
            content='{"pesquisa": "información", "resumo_perfil": "perfil actualizado", "fontes_consultadas": ["google"]}',
            model="deepseek-chat"
        )

        with patch.object(ServiceFactory, "get_llm_client", return_value=mock_llm):
            result = await research_lead(sample_lead, litellm_url="http://test:4000", api_key="test-key", locale=locale)

        assert result is not None
        assert "pesquisa" in result
        assert isinstance(result["pesquisa"], dict)


class TestENLocale:
    """Testa o locale inglês nos agentes."""

    @pytest.mark.asyncio
    async def test_enrich_lead_en_locale(self, sample_lead):
        from agents.enricher import enrich_lead
        from agents.factory import ServiceFactory
        locale = get_locale("en")

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = LLMResponse(
            content='{"resumo_perfil": "Family pizzeria", "pontos_fracos": ["no website"], "oportunidades": ["delivery"], "maturidade_digital": "low"}',
            model="qwen-vl-max"
        )

        with patch.object(ServiceFactory, "get_llm_client", return_value=mock_llm):
            result = await enrich_lead(sample_lead, litellm_url="http://test:4000", api_key="test-key", locale=locale)

        assert result["enrichment_success"] is True
        assert result["dossie"]["resumo_perfil"] == "Family pizzeria"

    def test_en_prompt_is_english(self):
        locale = get_locale("en")
        from agents.enricher import _build_enrichment_prompt
        prompt = _build_enrichment_prompt({
            "name": "Test Cafe",
            "address": "123 Main St",
            "phone": "+1 555",
            "website": "",
            "instagram_username": "",
            "google_maps_data": {},
            "instagram_data": {},
        }, locale)
        assert "business intelligence" in prompt.lower()
        assert "Test Cafe" in prompt
        assert "Not available" in prompt
