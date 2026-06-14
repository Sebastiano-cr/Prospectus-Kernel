"""Testes mockados para o enricher e messenger."""
import pytest
from unittest.mock import AsyncMock, patch

from agents.ports.llm_client import LLMResponse
from agents.enricher import _validate_and_structure_dossie, _mark_enrichment_failed
from agents.messenger import _generate_template_message
from agents.pure_functions import can_send_message_sync


class TestEnricherMock:
    """Testes do enricher usando mocks."""

    @pytest.mark.asyncio
    async def test_enrich_with_mock_litellm(self, sample_lead):
        """Testa o fluxo completo do enricher mockando o LLM client."""
        from agents.enricher import enrich_lead
        from agents.factory import ServiceFactory

        content = (
            '{\n'
            '  "resumo_perfil": "Restaurante tradicional com comida caseira",\n'
            '  "pontos_fracos": ["Nao possui website", "Pouca presenca digital"],\n'
            '  "oportunidades": ["Criar site", "Delivery online"],\n'
            '  "maturidade_digital": "baixo"\n'
            '}'
        )

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = LLMResponse(
            content=content, model="deepseek-chat"
        )

        with patch.object(ServiceFactory, "get_llm_client", return_value=mock_llm):
            result = await enrich_lead(
                sample_lead,
                litellm_url="http://test:4000",
                api_key="test-key",
            )

        assert result is not None
        assert result["enrichment_success"] is True
        assert "dossie" in result
        assert result["dossie"]["maturidade_digital"] in ("alto", "médio", "baixo")
        assert isinstance(result["dossie"]["pontos_fracos"], list)
        assert len(result["dossie"]["pontos_fracos"]) >= 1
        assert isinstance(result["dossie"]["oportunidades"], list)

    def test_validate_and_structure_dossie(self, sample_dossie):
        """Testa que _validate_and_structure_dossie normaliza corretamente."""
        result = _validate_and_structure_dossie(sample_dossie)

        assert result["maturidade_digital"] == "baixo"
        assert result["resumo_perfil"] == sample_dossie["resumo_perfil"]
        assert len(result["pontos_fracos"]) == 3
        assert len(result["oportunidades"]) == 3

    def test_validate_dossie_with_missing_fields(self):
        """Testa que campos faltando recebem defaults."""
        incomplete = {"resumo_perfil": "Perfil curto"}
        result = _validate_and_structure_dossie(incomplete)

        assert result["resumo_perfil"] == "Perfil curto"
        assert result["maturidade_digital"] in ("alto", "médio", "baixo")
        assert len(result["pontos_fracos"]) >= 1
        assert isinstance(result["oportunidades"], list)

    def test_mark_enrichment_failed(self):
        """Testa que _mark_enrichment_failed retorna estrutura correta."""
        lead = {"name": "Test"}
        result = _mark_enrichment_failed(lead, "timeout")

        assert result["enrichment_success"] is False
        assert result["enrichment_failed"] is True
        assert result["enrichment_error"] == "timeout"
        assert result["dossie"]["maturidade_digital"] == "baixo"


class TestMessengerMock:
    """Testes do messenger usando mocks."""

    def test_generate_template_message_all_faixas(self, sample_dossie):
        """Testa que templates para todas as faixas funcionam."""
        lead = {
            "name": "Restaurante Teste",
            "score": 65,
            "dossie": sample_dossie,
        }

        for faixa in ("frio", "morno", "quente"):
            msg = _generate_template_message(lead, faixa)
            assert isinstance(msg, str)
            assert len(msg) > 0

    def test_generate_template_message_fallback_without_dossie(self):
        """Testa que mensagem e gerada mesmo sem dossier completo."""
        lead = {"name": "Loja Teste", "score": 50, "dossie": {}}
        msg = _generate_template_message(lead, "morno")
        assert isinstance(msg, str)
        assert len(msg) > 0

    def test_can_send_message_respects_blocked_status(self):
        """Testa que leads com status bloqueado nao recebem mensagem."""
        assert can_send_message_sync({"status": "novo"}) is True
        assert can_send_message_sync({"status": "enriquecido"}) is True
        assert can_send_message_sync({"status": "vendido"}) is False
        assert can_send_message_sync({"status": "descartado"}) is False
        assert can_send_message_sync({"status": "repassado"}) is False


class TestScoringMock:
    """Testes do scorer."""

    def test_fallback_score_calculation(self, sample_dossie):
        """Testa que o fallback score produz valores no range correto."""
        from agents.scorer import _scoring_fallback

        result = _scoring_fallback(sample_dossie, "LiteLLM indisponivel")

        assert 0 <= result["score"] <= 100
        assert result["faixa"] in ("frio", "morno", "quente")
        assert result["scoring_fallback"] is True
        assert result["scoring_error"] == "LiteLLM indisponivel"

    def test_validate_and_structure_score(self):
        """Testa normalizacao do score."""
        from agents.scorer import _validate_and_structure_score

        result = _validate_and_structure_score({
            "score": 85,
            "justification": "Lead excelente",
            "faixa": "quente",
        })

        assert result["score"] == 85
        assert result["faixa"] == "quente"
        assert result["justification"] == "Lead excelente"

    def test_score_clamping(self):
        """Testa que scores fora do range sao normalizados."""
        from agents.scorer import _validate_and_structure_score

        result = _validate_and_structure_score({"score": 150})
        assert result["score"] == 100

        result = _validate_and_structure_score({"score": -10})
        assert result["score"] == 0
