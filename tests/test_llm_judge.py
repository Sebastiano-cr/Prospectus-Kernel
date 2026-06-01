"""
Testes unitários para LLM Judge.
Cobertura:
    - Construção de prompts para cada agente
    - Parse de respostas LLM
    - Fallback quando LLM falha
    - Resultado com campos obrigatórios
"""

import pytest
import sys
import os
import json
from unittest.mock import AsyncMock, patch, MagicMock

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from eval.llm_judge import LLMJudge, LLMJudgeResult


# --- Fixtures ---

@pytest.fixture
def judge():
    """LLMJudge limpo para cada teste."""
    return LLMJudge(model="test-model")


@pytest.fixture
def sample_output():
    """Output de exemplo para testes."""
    return {
        "dossie": {
            "resumo_perfil": "Bar do Zé é um estabelecimento tradicional na Rua Augusta, São Paulo",
            "pontos_fracos": ["sem Instagram", "não possui site próprio"],
            "oportunidades": ["marketing de proximidade"],
            "maturidade_digital": 2,
            "resumo_executivo": "Estabelecimento com potencial de crescimento digital"
        }
    }


@pytest.fixture
def sample_context():
    """Contexto de exemplo para testes."""
    return {
        "lead": {
            "name": "Bar do Zé",
            "address": "Rua Augusta, 1234, São Paulo",
            "phone": "+5511999887766"
        }
    }


# --- Construção de Prompts ---

class TestPromptBuilding:
    def test_enricher_prompt_contains_lead_info(self, judge, sample_output, sample_context):
        prompt = judge._build_enricher_prompt(sample_output, sample_context)
        assert "Bar do Zé" in prompt
        assert "Rua Augusta" in prompt
        assert "dossiê" in prompt.lower()

    def test_scorer_prompt_contains_dossier(self, judge, sample_output, sample_context):
        output = {"score": 75, "faixa": "quente", "justificativa": "Bom lead"}
        prompt = judge._build_scorer_prompt(output, sample_context)
        assert "score" in prompt.lower()
        assert "faixa" in prompt.lower()

    def test_messenger_prompt_contains_message(self, judge, sample_context):
        output = {"message": "Olá Bar do Zé! Posso ajudar com marketing?"}
        prompt = judge._build_messenger_prompt(output, sample_context)
        assert "Olá Bar do Zé!" in prompt
        assert "marketing" in prompt

    def test_researcher_prompt_contains_sources(self, judge):
        output = {"fontes_consultadas": [{"url": "https://google.com/maps"}]}
        prompt = judge._build_researcher_prompt(output, {})
        assert "fontes" in prompt.lower()


# --- Parse de Respostas ---

class TestResponseParsing:
    def test_parse_valid_json(self, judge):
        response = '{"score": 85, "explanation": "Bom resultado", "criteria": {"json_structure": 90}}'
        parsed = judge._parse_llm_response(response)
        assert parsed is not None
        assert parsed["score"] == 85
        assert parsed["explanation"] == "Bom resultado"

    def test_parse_json_with_surrounding_text(self, judge):
        response = 'Aqui está o resultado:\n{"score": 70, "explanation": "OK"}\nFim.'
        parsed = judge._parse_llm_response(response)
        assert parsed is not None
        assert parsed["score"] == 70

    def test_parse_invalid_json(self, judge):
        response = 'Esta não é uma resposta JSON válida'
        parsed = judge._parse_llm_response(response)
        assert parsed is None

    def test_parse_empty_response(self, judge):
        response = ''
        parsed = judge._parse_llm_response(response)
        assert parsed is None

    def test_parse_malformed_json(self, judge):
        response = '{"score": 85, "explanation": "missing closing brace"'
        parsed = judge._parse_llm_response(response)
        assert parsed is None


# --- Resultado do Judge ---

class TestLLMJudgeResult:
    def test_result_to_dict(self):
        result = LLMJudgeResult(
            score=85,
            explanation="Bom resultado",
            criteria_scores={"json_structure": 90, "specificity": 80},
            passed=True,
            raw_llm_response='{"score": 85}'
        )
        d = result.to_dict()
        assert d["score"] == 85
        assert d["passed"] is True
        assert d["judge_type"] == "model-graded"
        assert "criteria_scores" in d

    def test_result_passed_threshold(self):
        result = LLMJudgeResult(score=80, explanation="", criteria_scores={}, passed=True)
        assert result.passed is True

    def test_result_below_threshold(self):
        result = LLMJudgeResult(score=79, explanation="", criteria_scores={}, passed=False)
        assert result.passed is False


# --- Mock de LLM ---

class TestLLMMockCalls:
    @pytest.mark.asyncio
    async def test_judge_enricher_with_mock(self, judge, sample_output, sample_context):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": '{"score": 85, "explanation": "Dossiê de boa qualidade", "criteria": {"json_structure": 90}}'
                }
            }]
        }
        mock_response.raise_for_status = MagicMock()

        async def mock_post(url, json=None):
            return mock_response

        with patch.object(judge, '_get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_get_client.return_value = mock_client

            result = await judge.judge_enricher(sample_output, sample_context)

            assert result.score == 85
            assert result.passed is True
            assert "Dossiê de boa qualidade" in result.explanation

    @pytest.mark.asyncio
    async def test_judge_handles_llm_error(self, judge, sample_output, sample_context):
        with patch.object(judge, '_get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.side_effect = Exception("LLM unavailable")
            mock_get_client.return_value = mock_client

            result = await judge.judge_enricher(sample_output, sample_context)

            # Fallback para score 50 quando LLM falha
            assert result.score == 50
            assert result.passed is False

    @pytest.mark.asyncio
    async def test_judge_handles_invalid_llm_response(self, judge, sample_output, sample_context):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": "Esta não é uma resposta JSON válida"
                }
            }]
        }
        mock_response.raise_for_status = MagicMock()

        async def mock_post(url, json=None):
            return mock_response

        with patch.object(judge, '_get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_get_client.return_value = mock_client

            result = await judge.judge_enricher(sample_output, sample_context)

            # Fallback para score 50 quando JSON inválido
            assert result.score == 50
            assert result.passed is False


# --- Integração com JudgeFactory ---

class TestJudgeIntegration:
    @pytest.mark.asyncio
    async def test_judge_generic_agent(self, judge):
        result = await judge.judge("unknown_agent", {}, {})
        assert result.score == 50
        assert "não implementado" in result.explanation.lower()


# --- Retry Logic ---

class TestRetryLogic:
    @pytest.mark.asyncio
    async def test_retry_on_timeout(self, judge, sample_output, sample_context):
        call_count = 0

        async def mock_post(url, json=None):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise asyncio.TimeoutError()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{
                    "message": {
                        "content": '{"score": 80, "explanation": "OK", "criteria": {}}'
                    }
                }]
            }
            mock_response.raise_for_status = MagicMock()
            return mock_response

        with patch.object(judge, '_get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_get_client.return_value = mock_client

            result = await judge.judge_enricher(sample_output, sample_context)

            # Deve ter feito 2 chamadas (1 falha + 1 sucesso)
            assert call_count == 2
            assert result.score == 80
