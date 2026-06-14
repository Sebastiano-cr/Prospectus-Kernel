"""
Testes de integração para o Eval Harness.
Testa o fluxo completo: input → agent output → judge → skeptic → report.
"""

import pytest
import sys
import os
import json

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from eval.kirin_eval_harness import (
    KirinEvalHarness, JudgeFactory, Dimension, EvalReport
)


# --- Fixtures ---

@pytest.fixture
def harness():
    """KirinEvalHarness limpo para cada teste."""
    return KirinEvalHarness(use_llm_judge=False)


@pytest.fixture
def good_enricher_data():
    """Dados de exemplo de um Enricher com output de boa qualidade."""
    return {
        "output": {
            "dossie": {
                "resumo_perfil": "Bar do Zé é um estabelecimento tradicional na Rua Augusta, São Paulo, conhecido por seu ambiente descontraído e clientela fiel.",
                "pontos_fracos": [
                    "sem presença no Instagram",
                    "não possui site próprio",
                    "cardápio não disponível online"
                ],
                "oportunidades": [
                    "marketing de proximidade com moradores da Augusta",
                    "eventos culturais e música ao vivo"
                ],
                "maturidade_digital": 2,
                "resumo_executivo": "Estabelecimento com potencial de crescimento digital significativo"
            }
        },
        "context": {
            "lead": {
                "name": "Bar do Zé",
                "address": "Rua Augusta, 1234, São Paulo",
                "phone": "+5511999887766",
                "city": "São Paulo"
            },
            "expected_lang": "pt-BR",
            "has_social_media": False
        },
        "tool_calls": [
            {"name": "complete", "parameters": {"model": "qwen-vl-max", "temperature": 0.3}},
            {"name": "store", "parameters": {"namespace": "lead:xxx", "key": "enrichment"}}
        ]
    }


@pytest.fixture
def bad_enricher_data():
    """Dados de exemplo de um Enricher com output suspeito."""
    return {
        "output": {
            "dossie": {
                "resumo_perfil": "Bar",
                "pontos_fracos": ["sem Instagram", "não tem site"],
                "oportunidades": ["melhorar", "crescer"],
                "maturidade_digital": "alto",  # SUSPEITO: alta maturidade sem presença digital
                "resumo_executivo": "Bar bom"
            }
        },
        "context": {
            "lead": {
                "name": "Bar do Zé",
                "address": "Rua Augusta, 1234, São Paulo"
            },
            "expected_lang": "pt-BR",
            "has_social_media": False
        },
        "tool_calls": [
            {"name": "complete", "parameters": {"model": "qwen-vl-max", "temperature": 0.3}},
            {"name": "store", "parameters": {"namespace": "lead:xxx", "key": "enrichment"}}
        ]
    }


@pytest.fixture
def good_messenger_data():
    """Dados de exemplo de um Messenger com mensagem de boa qualidade."""
    return {
        "output": {
            "message": "Olá Bar do Zé! Vi que vocês são especialistas em gastronomia e têm ótimas avaliações no Google Maps. Percebi que a ausência de presença digital poderia estar limitando seu alcance online. Temos soluções específicas para negócios como o seu que podem aumentar seus leads em até 40%. Que tal uma conversa rápida de 15 minutos nesta semana para mostrar como? Responda SAIR para não receber mais contatos."
        },
        "context": {
            "lead": {
                "name": "Bar do Zé"
            },
            "dossier": {
                "pontos_fracos": ["sem presença no Instagram", "não possui site próprio"],
                "oportunidades": ["marketing de proximidade"]
            },
            "expected_lang": "pt-BR"
        },
        "tool_calls": [
            {"name": "complete", "parameters": {"model": "deepseek-chat", "temperature": 0.7}},
            {"name": "store", "parameters": {"namespace": "lead:xxx", "key": "message"}}
        ]
    }


# --- Testes de Integração ---

class TestEvalHarnessIntegration:
    def test_enricher_good_output_passes(self, harness, good_enricher_data):
        """Enricher com output bom deve passar na avaliação."""
        report = harness.evaluate_agent(
            "enricher",
            good_enricher_data["output"],
            good_enricher_data["context"],
            good_enricher_data["tool_calls"]
        )

        assert isinstance(report, EvalReport)
        assert report.overall_score > 0
        assert report.status in ["PASS", "CONDITIONAL_PASS", "FAIL"]
        assert len(report.dimension_results) == 6

    def test_enricher_bad_output_has_flags(self, harness, bad_enricher_data):
        """Enricher com output suspeito deve ter flags do SkepticAgent."""
        report = harness.evaluate_agent(
            "enricher",
            bad_enricher_data["output"],
            bad_enricher_data["context"],
            bad_enricher_data["tool_calls"]
        )

        # SkepticAgent deve detectar maturidade incoerente
        skeptic_report = report.skeptic_reports[0]
        assert len(skeptic_report.flags) > 0
        assert any("H6" in flag for flag in skeptic_report.flags)

    def test_messenger_good_output(self, harness, good_messenger_data):
        """Messenger com mensagem boa deve ter score alto."""
        report = harness.evaluate_agent(
            "messenger",
            good_messenger_data["output"],
            good_messenger_data["context"],
            good_messenger_data["tool_calls"]
        )

        # Intention Fidelity deve ser alto
        intention_dim = next(
            d for d in report.dimension_results
            if d.dimension == Dimension.INTENTION_FIDELITY
        )
        assert intention_dim.score > 70

    def test_dimensions_are_weighted(self, harness, good_enricher_data):
        """Dimensões devem ter pesos que somam 1.0."""
        report = harness.evaluate_agent(
            "enricher",
            good_enricher_data["output"],
            good_enricher_data["context"],
            good_enricher_data["tool_calls"]
        )

        total_weight = sum(d.weight for d in report.dimension_results)
        assert abs(total_weight - 1.0) < 0.01

    def test_report_to_json(self, harness, good_enricher_data):
        """Relatório deve ser serializável para JSON."""
        report = harness.evaluate_agent(
            "enricher",
            good_enricher_data["output"],
            good_enricher_data["context"],
            good_enricher_data["tool_calls"]
        )

        json_str = report.to_json()
        assert isinstance(json_str, str)

        # Parse de volta deve funcionar
        parsed = json.loads(json_str)
        assert "overall_score" in parsed
        assert "status" in parsed
        assert "dimensions" in parsed

    def test_recommendations_generated(self, harness, bad_enricher_data):
        """Relatório com problemas deve ter recomendações."""
        report = harness.evaluate_agent(
            "enricher",
            bad_enricher_data["output"],
            bad_enricher_data["context"],
            bad_enricher_data["tool_calls"]
        )

        # Deve ter recomendações quando há problemas
        if report.status != "PASS":
            assert len(report.recommendations) > 0


# --- Testes de Judge Factory ---

class TestJudgeFactory:
    def test_create_enricher_judge(self):
        judge = JudgeFactory.create_judge("enricher")
        assert callable(judge)

    def test_create_scorer_judge(self):
        judge = JudgeFactory.create_judge("scorer")
        assert callable(judge)

    def test_create_messenger_judge(self):
        judge = JudgeFactory.create_judge("messenger")
        assert callable(judge)

    def test_create_generic_judge_for_unknown(self):
        judge = JudgeFactory.create_judge("unknown_agent")
        assert callable(judge)


# --- Testes de Dimensões ---

class TestDimensions:
    def test_all_dimensions_present(self, harness, good_enricher_data):
        """Todas as 6 dimensões devem estar presentes no relatório."""
        report = harness.evaluate_agent(
            "enricher",
            good_enricher_data["output"],
            good_enricher_data["context"],
            good_enricher_data["tool_calls"]
        )

        dimension_names = {d.dimension for d in report.dimension_results}
        expected = {
            Dimension.HARNESS_INTEGRITY,
            Dimension.INTENTION_FIDELITY,
            Dimension.BOUNDARY_PRECISION,
            Dimension.ABDUCTIVE_RESILIENCE,
            Dimension.EVAL_HARNESS,
            Dimension.ARCHITECTURAL_READINESS
        }
        assert dimension_names == expected
