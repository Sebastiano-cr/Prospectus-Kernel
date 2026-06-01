"""
Testes unitários para SkepticAgent.
Cobertura:
    - H1: Score vs Dossier mismatch
    - H2: Mensagem genérica
    - H3: Fontes falsas
    - H4: Desvio de idioma
    - H5: Tamanho suspeito
    - H6: Maturidade incoerente
    - H7: Emoção inconsistente
    - Relatório de confiança
    - Função de conveniência
"""

import pytest
import sys
import os

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.skeptic import SkepticAgent, SkepticReport, check_agent_output, get_skeptic


# --- Fixtures ---

@pytest.fixture
def skeptic():
    """SkepticAgent limpo para cada teste."""
    return SkepticAgent()


# --- H1: Score vs Dossier Mismatch ---

class TestH1ScoreVsDossier:
    def test_high_score_with_many_weaknesses_flags(self, skeptic):
        output = {"score": 90}
        context = {"dossier": {"pontos_fracos": ["w1", "w2", "w3", "w4"]}}
        result = skeptic._check_score_vs_dossier("scorer", output, context)
        assert result is not None
        assert "mismatch" in result.lower()

    def test_low_score_no_flag(self, skeptic):
        output = {"score": 50}
        context = {"dossier": {"pontos_fracos": ["w1", "w2", "w3", "w4"]}}
        result = skeptic._check_score_vs_dossier("scorer", output, context)
        assert result is None

    def test_high_score_few_weaknesses_no_flag(self, skeptic):
        output = {"score": 85}
        context = {"dossier": {"pontos_fracos": ["w1", "w2"]}}
        result = skeptic._check_score_vs_dossier("scorer", output, context)
        assert result is None

    def test_non_scorer_agent_returns_none(self, skeptic):
        output = {"score": 95}
        context = {"dossier": {"pontos_fracos": ["w1", "w2", "w3", "w4"]}}
        result = skeptic._check_score_vs_dossier("messenger", output, context)
        assert result is None


# --- H2: Mensagem Genérica ---

class TestH2GenericMessage:
    def test_generic_message_without_lead_name_flags(self, skeptic):
        output = {"message": "Somos uma empresa que oferece serviços para melhorar seu negócio. Nossos serviços são ótimos."}
        context = {"lead": {"name": "Bar do Zé"}}
        result = skeptic._check_generic_message("messenger", output, context)
        assert result is not None
        assert "genérica" in result.lower()

    def test_personalized_message_no_flag(self, skeptic):
        output = {"message": "Olá Bar do Zé! Vi que vocês precisam de ajuda com marketing digital. Posso ajudar?"}
        context = {"lead": {"name": "Bar do Zé"}}
        result = skeptic._check_generic_message("messenger", output, context)
        assert result is None

    def test_non_messenger_agent_returns_none(self, skeptic):
        output = {"message": "Qualquer coisa"}
        context = {"lead": {"name": "Bar do Zé"}}
        result = skeptic._check_generic_message("enricher", output, context)
        assert result is None


# --- H3: Fontes Falsas ---

class TestH3FakeSources:
    def test_suspicious_source_flags(self, skeptic):
        output = {"fontes_consultadas": [
            {"url": "https://example.com/fake"},
            {"url": "http://localhost:8080/data"}
        ]}
        result = skeptic._check_fake_sources("researcher", output, {})
        assert result is not None
        assert "suspeitas" in result.lower()

    def test_valid_sources_no_flag(self, skeptic):
        output = {"fontes_consultadas": [
            {"url": "https://www.google.com/maps"},
            {"url": "https://www.reclameaqui.com.br"}
        ]}
        result = skeptic._check_fake_sources("researcher", output, {})
        assert result is None

    def test_non_researcher_agent_returns_none(self, skeptic):
        output = {"fontes_consultadas": [{"url": "https://example.com"}]}
        result = skeptic._check_fake_sources("messenger", output, {})
        assert result is None


# --- H4: Desvio de Idioma ---

class TestH4LanguageDeviation:
    def test_english_output_for_ptbr_flags(self, skeptic):
        output = {"message": "The business is the best in the market and is for the people"}
        context = {"expected_lang": "pt-BR"}
        result = skeptic._check_language_deviation("messenger", output, context)
        assert result is not None
        assert "inglês" in result.lower()

    def test_portuguese_output_no_flag(self, skeptic):
        output = {"message": "O Bar do Zé é um ótimo estabelecimento na Rua Augusta para clientes que procuram qualidade"}
        context = {"expected_lang": "pt-BR"}
        result = skeptic._check_language_deviation("messenger", output, context)
        assert result is None

    def test_non_target_agent_returns_none(self, skeptic):
        output = {"message": "The test message"}
        context = {"expected_lang": "pt-BR"}
        result = skeptic._check_language_deviation("scorer", output, context)
        assert result is None

    def test_non_ptbr_expected_returns_none(self, skeptic):
        output = {"message": "The test message"}
        context = {"expected_lang": "en-US"}
        result = skeptic._check_language_deviation("messenger", output, context)
        assert result is None


# --- H5: Tamanho Suspeito ---

class TestH5SuspiciousLength:
    def test_exactly_300_chars_flags(self, skeptic):
        output = {"message": "A" * 300}
        result = skeptic._check_suspicious_length("messenger", output, {})
        assert result is not None
        assert "300" in result

    def test_very_short_message_flags(self, skeptic):
        output = {"message": "Hi"}
        result = skeptic._check_suspicious_length("messenger", output, {})
        assert result is not None
        assert "curta" in result.lower()

    def test_normal_message_no_flag(self, skeptic):
        output = {"message": "Olá! Vi que o Bar do Zé precisa de ajuda com marketing digital. Posso ajudar?"}
        result = skeptic._check_suspicious_length("messenger", output, {})
        assert result is None

    def test_enricher_short_resumo_flags(self, skeptic):
        output = {"dossie": {"resumo_perfil": "Bar"}}
        result = skeptic._check_suspicious_length("enricher", output, {})
        assert result is not None

    def test_enricher_normal_resumo_no_flag(self, skeptic):
        output = {"dossie": {"resumo_perfil": "Bar do Zé é um estabelecimento tradicional na Rua Augusta"}}
        result = skeptic._check_suspicious_length("enricher", output, {})
        assert result is None


# --- H6: Maturidade Incoerente ---

class TestH6MaturityIncoherence:
    def test_high_maturity_no_social_flags(self, skeptic):
        output = {"dossie": {"maturidade_digital": 9, "pontos_fracos": ["sem Instagram"]}}
        context = {"has_social_media": False}
        result = skeptic._check_maturity_incoherence("enricher", output, context)
        assert result is not None
        assert "incoerente" in result.lower() or "ausência" in result.lower()

    def test_low_maturity_no_flag(self, skeptic):
        output = {"dossie": {"maturidade_digital": 3, "pontos_fracos": ["sem Instagram"]}}
        context = {"has_social_media": False}
        result = skeptic._check_maturity_incoherence("enricher", output, context)
        assert result is None

    def test_high_maturity_with_social_no_flag(self, skeptic):
        output = {"dossie": {"maturidade_digital": 8, "pontos_fracos": []}}
        context = {"has_social_media": True}
        result = skeptic._check_maturity_incoherence("enricher", output, context)
        assert result is None

    def test_non_enricher_agent_returns_none(self, skeptic):
        output = {"dossie": {"maturidade_digital": 9}}
        result = skeptic._check_maturity_incoherence("scorer", output, {})
        assert result is None


# --- H7: Emoção Inconsistente ---

class TestH7EmotionInconsistency:
    def test_raiva_without_markers_flags(self, skeptic):
        output = {"emotion": "raiva", "text": "Estou muito feliz hoje!"}
        result = skeptic._check_emotion_inconsistency("discourse_ingestor", output, {})
        assert result is not None
        assert "raiva" in result.lower()

    def test_raiva_with_markers_no_flag(self, skeptic):
        output = {"emotion": "raiva", "text": "Estou com raiva desde serviço péssimo!"}
        result = skeptic._check_emotion_inconsistency("discourse_ingestor", output, {})
        assert result is None

    def test_unknown_emotion_returns_none(self, skeptic):
        output = {"emotion": "desconhecida", "text": "Qualquer coisa"}
        result = skeptic._check_emotion_inconsistency("discourse_ingestor", output, {})
        assert result is None

    def test_non_discourse_agent_returns_none(self, skeptic):
        output = {"emotion": "raiva", "text": "Nada aqui"}
        result = skeptic._check_emotion_inconsistency("messenger", output, {})
        assert result is None


# --- Relatório de Confiança ---

class TestSkepticReport:
    def test_no_flags_full_confidence(self, skeptic):
        report = skeptic.check("messenger", {"message": "Olá Bar do Zé! Vi que vocês precisam de ajuda com marketing digital. Posso mostrar como aumentar seus leads?"}, {"lead": {"name": "Bar do Zé"}})
        assert report.passed is True
        assert report.confidence == 1.0
        assert len(report.flags) == 0

    def test_flags_reduce_confidence(self, skeptic):
        output = {"message": "A" * 300}  # H5 flagged
        context = {"lead": {"name": "Bar do Zé"}}
        report = skeptic.check("messenger", output, context)
        assert report.passed is False
        assert report.confidence < 1.0

    def test_multiple_flags(self, skeptic):
        output = {
            "message": "Somos uma empresa que oferece serviços para melhorar seu negócio. Nossos serviços são ótimos. A" * 10,
            "emotion": "raiva"
        }
        context = {"lead": {"name": "Bar do Zé"}, "expected_lang": "pt-BR"}
        report = skeptic.check("messenger", output, context)
        assert len(report.flags) > 0

    def test_report_to_dict(self, skeptic):
        report = skeptic.check("messenger", {"message": "Olá"}, {})
        d = report.to_dict()
        assert "passed" in d
        assert "flags" in d
        assert "confidence" in d
        assert "flag_count" in d


# --- Função de Conveniência ---

class TestConvenienceFunction:
    def test_check_agent_output(self):
        report = check_agent_output("messenger", {"message": "Olá Bar do Zé!"}, {"lead": {"name": "Bar do Zé"}})
        assert isinstance(report, SkepticReport)
        assert report.agent_name == "messenger"

    def test_get_skeptic_singleton(self):
        s1 = get_skeptic()
        s2 = get_skeptic()
        assert s1 is s2
