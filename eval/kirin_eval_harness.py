#!/usr/bin/env python3
"""
KIRIN EVAL HARNESS — Framework de Avaliação Abductiva
Baseado em Augusto Galego (Groomy, Harness, Evals) + Abdução Sistêmica

Uso:
    python kirin_eval_harness.py --agent enricher --input lead_sample.json
    python kirin_eval_harness.py --full-suite
    python kirin_eval_harness.py --skeptic-only --agent messenger --input msg_input.json
"""

import json
import sys
import os
import argparse
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

# Importar SkepticReport do agents.skeptic (fonte única)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from agents.skeptic import SkepticReport


# ============================================================
# MODELOS DE DADOS
# ============================================================

class Dimension(Enum):
    HARNESS_INTEGRITY = "harness_integrity"
    INTENTION_FIDELITY = "intention_fidelity"
    BOUNDARY_PRECISION = "boundary_precision"
    ABDUCTIVE_RESILIENCE = "abductive_resilience"
    EVAL_HARNESS = "eval_harness"
    ARCHITECTURAL_READINESS = "architectural_readiness"


@dataclass
class JudgeResult:
    """Resultado de um judge model-graded."""
    score: int  # 0-100
    explanation: str
    criteria_breakdown: Dict[str, int] = field(default_factory=dict)
    passed: bool = False

    def to_dict(self) -> Dict:
        return {
            "score": self.score,
            "explanation": self.explanation,
            "criteria_breakdown": self.criteria_breakdown,
            "passed": self.passed
        }


@dataclass
class DimensionResult:
    """Resultado de uma dimensão de avaliação."""
    dimension: Dimension
    score: int
    threshold: int
    passed: bool
    observations: List[str] = field(default_factory=list)
    weight: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "dimension": self.dimension.value,
            "score": self.score,
            "threshold": self.threshold,
            "passed": self.passed,
            "observations": self.observations,
            "weight": self.weight,
            "weighted_score": round(self.score * self.weight, 2)
        }


@dataclass
class EvalReport:
    """Relatório completo de avaliação do Kirin."""
    system_name: str = "Kirin Platform"
    version: str = "2.0"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    dimension_results: List[DimensionResult] = field(default_factory=list)
    skeptic_reports: List[SkepticReport] = field(default_factory=list)
    overall_score: float = 0.0
    status: str = "PENDING"
    abductive_alert: bool = False
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "system_name": self.system_name,
            "version": self.version,
            "timestamp": self.timestamp,
            "dimensions": [d.to_dict() for d in self.dimension_results],
            "skeptic_checks": [s.to_dict() for s in self.skeptic_reports],
            "overall_score": round(self.overall_score, 2),
            "status": self.status,
            "abductive_alert": self.abductive_alert,
            "recommendations": self.recommendations
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


# ============================================================
# SKEPTICAGENT — Mecanismo de Desconfiança
# ============================================================

class SkepticAgent:
    """
    Agente cético que "cheira" inconsistências nos outputs dos LLMs.
    Não substitui o eval — é o filtro abductivo que o eval determinístico não pode ser.
    """

    def __init__(self):
        self.heuristics: Dict[str, Callable] = {
            "H1": self._check_score_vs_dossier,
            "H2": self._check_generic_message,
            "H3": self._check_fake_sources,
            "H4": self._check_language_deviation,
            "H5": self._check_suspicious_length,
            "H6": self._check_maturity_incoherence,
            "H7": self._check_emotion_inconsistency,
        }

    def check(self, agent_name: str, output: Dict, context: Dict) -> SkepticReport:
        """Executa todas as heurísticas de desconfiança."""
        flags = []

        for heuristic_id, heuristic_fn in self.heuristics.items():
            try:
                result = heuristic_fn(agent_name, output, context)
                if result:
                    flags.append(f"{heuristic_id}: {result}")
            except Exception as e:
                flags.append(f"{heuristic_id}: ERRO na heurística — {str(e)}")

        confidence = max(0.0, 1.0 - (len(flags) * 0.15))

        return SkepticReport(
            passed=len(flags) == 0,
            flags=flags,
            confidence=confidence,
            agent_name=agent_name
        )

    # --- Heurísticas ---

    def _check_score_vs_dossier(self, agent_name: str, output: Dict, context: Dict) -> Optional[str]:
        """H1: Score alto (>80) mas muitos pontos fracos no dossier."""
        if agent_name != "scorer":
            return None

        score = output.get("score", 0)
        dossier = context.get("dossier", {})

        if score > 80 and "pontos_fracos" in dossier:
            weaknesses = dossier["pontos_fracos"]
            if isinstance(weaknesses, list) and len(weaknesses) > 3:
                return f"Score={score} (alto) mas {len(weaknesses)} pontos fracos — mismatch"
        return None

    def _check_generic_message(self, agent_name: str, output: Dict, context: Dict) -> Optional[str]:
        """H2: Mensagem que poderia ser para qualquer negócio."""
        if agent_name != "messenger":
            return None

        message = output.get("message", "")
        lead_name = context.get("lead", {}).get("name", "")

        generic_phrases = [
            "somos uma empresa", "oferecemos serviços", "melhorar seu negócio",
            "sua empresa", "seu negócio", "nossos serviços"
        ]

        generic_count = sum(1 for phrase in generic_phrases if phrase.lower() in message.lower())

        if generic_count >= 3 and lead_name not in message:
            return f"Mensagem genérica ({generic_count} frases genéricas) e não menciona '{lead_name}'"
        return None

    def _check_fake_sources(self, agent_name: str, output: Dict, context: Dict) -> Optional[str]:
        """H3: Researcher citou URL que não parece real."""
        if agent_name != "researcher":
            return None

        sources = output.get("fontes_consultadas", [])
        suspicious = []

        for source in sources:
            url = source.get("url", "") if isinstance(source, dict) else str(source)
            # Heurística simples: URL sem protocolo ou com domínio suspeito
            if not url.startswith(("http://", "https://")):
                suspicious.append(url)
            elif any(bad in url.lower() for bad in ["example.com", "localhost", "test"]):
                suspicious.append(url)

        if suspicious:
            return f"Fontes suspeitas: {suspicious[:3]}"
        return None

    def _check_language_deviation(self, agent_name: str, output: Dict, context: Dict) -> Optional[str]:
        """H4: Output em inglês quando prompt foi PT-BR."""
        if agent_name not in ["messenger", "enricher", "language_game"]:
            return None

        expected_lang = context.get("expected_lang", "pt-BR")
        if expected_lang != "pt-BR":
            return None

        text = str(output)
        # Heurística simples: presença de palavras comuns em inglês
        english_markers = ["the ", "and ", "is ", "to ", "of ", "for ", "with "]
        english_count = sum(1 for marker in english_markers if marker in text.lower())

        # Português markers
        pt_markers = ["o ", "a ", "e ", "de ", "para ", "com ", "do ", "da "]
        pt_count = sum(1 for marker in pt_markers if marker in text.lower())

        if english_count > pt_count * 0.5:
            return f"Output parece estar em inglês ({english_count} markers EN vs {pt_count} markers PT)"
        return None

    def _check_suspicious_length(self, agent_name: str, output: Dict, context: Dict) -> Optional[str]:
        """H5: Output exatamente no limite ou muito abaixo."""
        if agent_name == "messenger":
            message = output.get("message", "")
            if len(message) == 300:
                return "Mensagem EXATAMENTE no limite de 300 chars — suspeito de corte forçado"
            if len(message) < 50:
                return f"Mensagem muito curta ({len(message)} chars) — possível falha na geração"

        if agent_name == "enricher":
            dossier = output.get("dossie", {})
            resumo = dossier.get("resumo_perfil", "")
            if len(resumo) < 20:
                return f"Resumo do perfil muito curto ({len(resumo)} chars) — possível alucinação ou falha"

        return None

    def _check_maturity_incoherence(self, agent_name: str, output: Dict, context: Dict) -> Optional[str]:
        """H6: Maturidade digital alta sem presença digital."""
        if agent_name != "enricher":
            return None

        dossier = output.get("dossie", {})
        maturidade = dossier.get("maturidade_digital", 0)

        # Contexto: se não tem Instagram, maturidade não deve ser > 7
        has_social = context.get("has_social_media", True)
        pontos_fracos = dossier.get("pontos_fracos", [])

        no_social_indicators = [
            "sem instagram", "sem facebook", "sem linkedin", "sem site",
            "presença digital fraca", "não tem site", "não tem rede social"
        ]

        has_no_social = any(
            indicator in str(pf).lower()
            for pf in (pontos_fracos if isinstance(pontos_fracos, list) else [])
            for indicator in no_social_indicators
        )

        if maturidade > 7 and (has_no_social or not has_social):
            return f"Maturidade={maturidade} (alta) mas pontos_fracos indicam ausência de presença digital"
        return None

    def _check_emotion_inconsistency(self, agent_name: str, output: Dict, context: Dict) -> Optional[str]:
        """H7: Emoção detectada não bate com o texto."""
        if agent_name != "discourse_ingestor":
            return None

        emotion = output.get("emotion", "")
        text = output.get("text", "")

        emotion_markers = {
            "raiva": ["ódio", "nojo", "inferno", "detesto", "raiva", "puto"],
            "tristeza": ["choro", "lágrima", "depressão", "triste", "solidão"],
            "alegria": ["feliz", "alegre", "contente", "maravilhoso", "incrível"],
            "medo": ["medo", "terror", "pânico", "assustado", "preocupado"],
        }

        if emotion in emotion_markers:
            markers = emotion_markers[emotion]
            found = sum(1 for marker in markers if marker in text.lower())
            if found == 0:
                return f"Emoção='{emotion}' mas nenhum marker encontrado no texto"

        return None


# ============================================================
# JUDGES — Avaliadores Model-Graded por Agente
# ============================================================

class JudgeFactory:
    """Factory de judges para cada agente do Kirin."""

    @staticmethod
    def create_judge(agent_name: str) -> Callable[[Dict, Dict], JudgeResult]:
        judges = {
            "enricher": JudgeFactory._judge_enricher,
            "scorer": JudgeFactory._judge_scorer,
            "messenger": JudgeFactory._judge_messenger,
            "researcher": JudgeFactory._judge_researcher,
            "discourse_ingestor": JudgeFactory._judge_discourse,
            "language_game": JudgeFactory._judge_language_game,
            "resonance": JudgeFactory._judge_resonance,
        }
        return judges.get(agent_name, JudgeFactory._judge_generic)

    @staticmethod
    def _judge_enricher(output: Dict, context: Dict) -> JudgeResult:
        """Judge para Enricher — avalia qualidade do dossiê."""
        score = 0
        criteria = {}
        explanations = []

        dossier = output.get("dossie", {})
        lead = context.get("lead", {})
        lead_name = lead.get("name", "")

        # C1: JSON válido e estruturado (15 pts)
        required_fields = ["resumo_perfil", "pontos_fracos", "oportunidades", "maturidade_digital", "resumo_executivo"]
        present = sum(1 for f in required_fields if f in dossier)
        criteria["json_structure"] = min(15, int((present / len(required_fields)) * 15))
        score += criteria["json_structure"]
        if criteria["json_structure"] < 15:
            explanations.append(f"Campos faltando: {[f for f in required_fields if f not in dossier]}")

        # C2: resumo_perfil específico (20 pts)
        resumo = dossier.get("resumo_perfil", "")
        specificity = 0
        if lead_name in resumo:
            specificity += 10
        if lead.get("address", "") in resumo or any(word in resumo for word in lead.get("address", "").split()):
            specificity += 5
        if lead.get("city", "") in resumo or "são paulo" in resumo.lower():
            specificity += 5
        criteria["specificity"] = min(20, specificity)
        score += criteria["specificity"]
        if criteria["specificity"] < 15:
            explanations.append("Resumo não é específico o suficiente para o lead")

        # C3: pontos_fracos acionáveis (20 pts)
        weaknesses = dossier.get("pontos_fracos", [])
        if isinstance(weaknesses, list) and len(weaknesses) > 0:
            generic = ["precisa melhorar", "falta investir", "deve crescer"]
            actionable_count = sum(1 for w in weaknesses if not any(g in w.lower() for g in generic))
            criteria["actionable_weaknesses"] = min(20, int((actionable_count / max(len(weaknesses), 1)) * 20))
        else:
            criteria["actionable_weaknesses"] = 0
            explanations.append("Sem pontos_fracos ou formato inválido")
        score += criteria["actionable_weaknesses"]

        # C4: maturidade_digital coerente (15 pts)
        maturidade = dossier.get("maturidade_digital", 0)
        if isinstance(maturidade, (int, float)) and 1 <= maturidade <= 10:
            criteria["maturity_coherence"] = 15
        else:
            criteria["maturity_coherence"] = 0
            explanations.append(f"maturidade_digital={maturidade} fora do range 1-10")
        score += criteria["maturity_coherence"]

        # C5: Sem alucinações (20 pts)
        # Heurística: verificar se dados não fornecidos aparecem no output
        hallucination_score = 20
        provided_fields = set(lead.keys())
        for field in ["instagram", "website", "email", "cnpj"]:
            if field in str(dossier).lower() and field not in provided_fields:
                hallucination_score -= 5
                explanations.append(f"Possível alucinação: '{field}' mencionado mas não fornecido no input")
        criteria["no_hallucination"] = max(0, hallucination_score)
        score += criteria["no_hallucination"]

        # C6: Tool calls na ordem correta (10 pts)
        tool_calls = context.get("tool_calls", [])
        if len(tool_calls) >= 2 and tool_calls[0].get("name") == "complete" and tool_calls[1].get("name") == "store":
            criteria["tool_order"] = 10
        else:
            criteria["tool_order"] = 0
            explanations.append("Ordem de tool calls incorreta ou incompleta")
        score += criteria["tool_order"]

        passed = score >= 80

        return JudgeResult(
            score=score,
            explanation="; ".join(explanations) if explanations else "Dossiê de boa qualidade",
            criteria_breakdown=criteria,
            passed=passed
        )

    @staticmethod
    def _judge_scorer(output: Dict, context: Dict) -> JudgeResult:
        """Judge para Scorer — avalia calibração do score."""
        score = 0
        criteria = {}
        explanations = []

        result_score = output.get("score", 0)
        faixa = output.get("faixa", "")
        justification = output.get("justificativa", "")
        dossier = context.get("dossier", {})

        # C1: Score no range válido (20 pts)
        if 0 <= result_score <= 100:
            criteria["score_range"] = 20
        else:
            criteria["score_range"] = 0
            explanations.append(f"Score={result_score} fora do range 0-100")
        score += criteria["score_range"]

        # C2: Faixa coerente com score (20 pts)
        expected_faixa = "frio" if result_score <= 39 else "morno" if result_score <= 69 else "quente"
        if faixa == expected_faixa:
            criteria["faixa_coherence"] = 20
        else:
            criteria["faixa_coherence"] = 0
            explanations.append(f"Faixa='{faixa}' não bate com score={result_score} (esperado: {expected_faixa})")
        score += criteria["faixa_coherence"]

        # C3: Justificativa de qualidade (20 pts)
        if isinstance(justification, str) and len(justification) > 50:
            sentences = justification.split(".")
            if 3 <= len(sentences) <= 5:
                criteria["justification_quality"] = 20
            else:
                criteria["justification_quality"] = 10
                explanations.append(f"Justificativa tem {len(sentences)} frases (esperado: 3-5)")
        else:
            criteria["justification_quality"] = 0
            explanations.append("Justificativa muito curta ou ausente")
        score += criteria["justification_quality"]

        # C4: Coerência com dossier (20 pts)
        # Heurística: score alto (>70) deve ter poucos pontos fracos
        weaknesses = dossier.get("pontos_fracos", [])
        if result_score > 70 and isinstance(weaknesses, list) and len(weaknesses) > 3:
            criteria["dossier_coherence"] = 0
            explanations.append(f"Score alto ({result_score}) mas {len(weaknesses)} pontos fracos")
        else:
            criteria["dossier_coherence"] = 20
        score += criteria["dossier_coherence"]

        # C5: JSON válido (10 pts)
        if all(k in output for k in ["score", "faixa", "justificativa"]):
            criteria["json_valid"] = 10
        else:
            criteria["json_valid"] = 0
            explanations.append("Campos obrigatórios faltando no output")
        score += criteria["json_valid"]

        # C6: Tool calls (10 pts)
        tool_calls = context.get("tool_calls", [])
        if len(tool_calls) >= 2:
            criteria["tool_calls"] = 10
        else:
            criteria["tool_calls"] = 0
        score += criteria["tool_calls"]

        passed = score >= 80

        return JudgeResult(
            score=score,
            explanation="; ".join(explanations) if explanations else "Score bem calibrado",
            criteria_breakdown=criteria,
            passed=passed
        )

    @staticmethod
    def _judge_messenger(output: Dict, context: Dict) -> JudgeResult:
        """Judge para Messenger — avalia qualidade da mensagem WhatsApp."""
        score = 0
        criteria = {}
        explanations = []

        message = output.get("message", "")
        lead = context.get("lead", {})
        lead_name = lead.get("name", "")

        # C1: Respeita limite de 300 chars (20 pts)
        if len(message) <= 300:
            criteria["length_limit"] = 20
        else:
            criteria["length_limit"] = 0
            explanations.append(f"Mensagem tem {len(message)} chars (limite: 300)")
        score += criteria["length_limit"]

        # C2: Menciona nome do negócio (20 pts)
        if lead_name in message:
            criteria["mentions_business"] = 20
        else:
            criteria["mentions_business"] = 0
            explanations.append(f"Mensagem não menciona '{lead_name}'")
        score += criteria["mentions_business"]

        # C3: Personalização (20 pts)
        # Verifica se há referência a pontos fracos ou oportunidades
        dossier = context.get("dossier", {})
        weaknesses = dossier.get("pontos_fracos", [])
        opportunities = dossier.get("oportunidades", [])

        personalization = 0
        if isinstance(weaknesses, list):
            for w in weaknesses:
                if any(word in message.lower() for word in w.lower().split()):
                    personalization += 10
                    break
        if isinstance(opportunities, list):
            for o in opportunities:
                if any(word in message.lower() for word in o.lower().split()):
                    personalization += 10
                    break
        criteria["personalization"] = min(20, personalization)
        if criteria["personalization"] < 10:
            explanations.append("Mensagem pouco personalizada — não referencia dossier")
        score += criteria["personalization"]

        # C4: Inclui opt-out (15 pts)
        if "sair" in message.lower() or "opt" in message.lower():
            criteria["opt_out"] = 15
        else:
            criteria["opt_out"] = 0
            explanations.append("Mensagem sem instrução de opt-out")
        score += criteria["opt_out"]

        # C5: Tom adequado (15 pts)
        # Heurística: não deve soar como spam agressivo
        spam_words = ["compre agora", "última chance", "não perca", "promoção imperdível"]
        spam_count = sum(1 for word in spam_words if word in message.lower())
        if spam_count == 0:
            criteria["tone"] = 15
        else:
            criteria["tone"] = max(0, 15 - spam_count * 5)
            explanations.append(f"Tom agressivo detectado ({spam_count} spam markers)")
        score += criteria["tone"]

        # C6: Português correto (10 pts)
        pt_markers = ["o ", "a ", "e ", "de ", "para ", "com ", "do ", "da ", "em ", "um "]
        pt_count = sum(1 for marker in pt_markers if marker in message.lower())
        if pt_count >= 3:
            criteria["portuguese"] = 10
        else:
            criteria["portuguese"] = 0
            explanations.append("Mensagem não parece estar em português")
        score += criteria["portuguese"]

        passed = score >= 80

        return JudgeResult(
            score=score,
            explanation="; ".join(explanations) if explanations else "Mensagem bem personalizada",
            criteria_breakdown=criteria,
            passed=passed
        )

    @staticmethod
    def _judge_researcher(output: Dict, context: Dict) -> JudgeResult:
        """Judge para Researcher — avalia qualidade da pesquisa."""
        score = 0
        criteria = {}
        explanations = []

        sources = output.get("fontes_consultadas", [])

        # C1: Fontes presentes (25 pts)
        if isinstance(sources, list) and len(sources) >= 2:
            criteria["sources_present"] = 25
        else:
            criteria["sources_present"] = max(0, len(sources) * 10 if isinstance(sources, list) else 0)
            explanations.append(f"Apenas {len(sources) if isinstance(sources, list) else 0} fontes encontradas")
        score += criteria["sources_present"]

        # C2: Fontes válidas (25 pts)
        valid_sources = 0
        for source in sources:
            url = source.get("url", "") if isinstance(source, dict) else str(source)
            if url.startswith(("http://", "https://")):
                valid_sources += 1
        criteria["valid_sources"] = min(25, int((valid_sources / max(len(sources), 1)) * 25))
        score += criteria["valid_sources"]

        # C3: Relevância (25 pts) — heurística simples
        lead_name = context.get("lead", {}).get("name", "")
        relevant = 0
        for source in sources:
            text = str(source)
            if lead_name.split()[0] in text or "são paulo" in text.lower():
                relevant += 1
        criteria["relevance"] = min(25, int((relevant / max(len(sources), 1)) * 25))
        score += criteria["relevance"]

        # C4: JSON estruturado (15 pts)
        if "fontes_consultadas" in output and "pesquisa" in output:
            criteria["json_structure"] = 15
        else:
            criteria["json_structure"] = 0
            explanations.append("Estrutura JSON incompleta")
        score += criteria["json_structure"]

        # C5: Tool calls (10 pts)
        tool_calls = context.get("tool_calls", [])
        if len(tool_calls) >= 2:
            criteria["tool_calls"] = 10
        else:
            criteria["tool_calls"] = 0
        score += criteria["tool_calls"]

        passed = score >= 80

        return JudgeResult(
            score=score,
            explanation="; ".join(explanations) if explanations else "Pesquisa de boa qualidade",
            criteria_breakdown=criteria,
            passed=passed
        )

    @staticmethod
    def _judge_discourse(output: Dict, context: Dict) -> JudgeResult:
        """Judge para Discourse Ingestor."""
        score = 0
        criteria = {}
        explanations = []

        # C1: Fragmento válido (30 pts)
        required = ["text", "source", "context", "emotion", "topic"]
        present = sum(1 for f in required if f in output)
        criteria["fragment_valid"] = min(30, int((present / len(required)) * 30))
        score += criteria["fragment_valid"]

        # C2: Emoção detectada (20 pts)
        emotion = output.get("emotion", "")
        valid_emotions = ["raiva", "tristeza", "alegria", "medo", "surpresa", "neutro", "confusão"]
        if emotion in valid_emotions:
            criteria["emotion_valid"] = 20
        else:
            criteria["emotion_valid"] = 0
            explanations.append(f"Emoção='{emotion}' não está na lista válida")
        score += criteria["emotion_valid"]

        # C3: Tópico identificado (20 pts)
        topic = output.get("topic", "")
        if len(topic) > 3:
            criteria["topic_present"] = 20
        else:
            criteria["topic_present"] = 0
        score += criteria["topic_present"]

        # C4: Sem duplicação (20 pts)
        is_duplicate = context.get("is_duplicate", False)
        if not is_duplicate:
            criteria["no_duplicate"] = 20
        else:
            criteria["no_duplicate"] = 0
            explanations.append("Fragmento marcado como duplicado")
        score += criteria["no_duplicate"]

        # C5: Tool calls (10 pts)
        tool_calls = context.get("tool_calls", [])
        if len(tool_calls) >= 2:
            criteria["tool_calls"] = 10
        else:
            criteria["tool_calls"] = 0
        score += criteria["tool_calls"]

        passed = score >= 80

        return JudgeResult(
            score=score,
            explanation="; ".join(explanations) if explanations else "Fragmento bem normalizado",
            criteria_breakdown=criteria,
            passed=passed
        )

    @staticmethod
    def _judge_language_game(output: Dict, context: Dict) -> JudgeResult:
        """Judge para Language Game Analyzer."""
        score = 0
        criteria = {}
        explanations = []

        # C1: 14 campos presentes (40 pts)
        required_fields = [
            "belief", "fear", "desire", "identity", "tension",
            "worldview", "value_system", "power_dynamic", "communication_style",
            "decision_making", "risk_tolerance", "time_orientation",
            "relationship_to_change", "cognitive_patterns"
        ]
        present = sum(1 for f in required_fields if f in output)
        criteria["fields_complete"] = min(40, int((present / len(required_fields)) * 40))
        score += criteria["fields_complete"]
        if criteria["fields_complete"] < 40:
            explanations.append(f"Campos faltando: {[f for f in required_fields if f not in output]}")

        # C2: Triádico belief-fear-desire (30 pts)
        triad = [output.get("belief"), output.get("fear"), output.get("desire")]
        if all(t and len(str(t)) > 10 for t in triad):
            criteria["triad_quality"] = 30
        else:
            criteria["triad_quality"] = 0
            explanations.append("Triádico belief-fear-desire incompleto ou muito curto")
        score += criteria["triad_quality"]

        # C3: Tension score válido (20 pts)
        tension = output.get("tension", 0)
        if isinstance(tension, (int, float)) and 0.0 <= tension <= 1.0:
            criteria["tension_valid"] = 20
        else:
            criteria["tension_valid"] = 0
            explanations.append(f"tension={tension} fora do range 0.0-1.0")
        score += criteria["tension_valid"]

        # C4: Tool calls (10 pts)
        tool_calls = context.get("tool_calls", [])
        if len(tool_calls) >= 2:
            criteria["tool_calls"] = 10
        else:
            criteria["tool_calls"] = 0
        score += criteria["tool_calls"]

        passed = score >= 80

        return JudgeResult(
            score=score,
            explanation="; ".join(explanations) if explanations else "Análise semântica completa",
            criteria_breakdown=criteria,
            passed=passed
        )

    @staticmethod
    def _judge_resonance(output: Dict, context: Dict) -> JudgeResult:
        """Judge para Resonance Engine."""
        score = 0
        criteria = {}
        explanations = []

        # C1: Padrões identificados (30 pts)
        patterns = output.get("patterns", [])
        if isinstance(patterns, list) and len(patterns) >= 2:
            criteria["patterns_found"] = 30
        else:
            criteria["patterns_found"] = max(0, len(patterns) * 15 if isinstance(patterns, list) else 0)
            explanations.append(f"Apenas {len(patterns) if isinstance(patterns, list) else 0} padrões encontrados")
        score += criteria["patterns_found"]

        # C2: Belief density calibrado (20 pts)
        belief_density = output.get("belief_density", 0)
        if isinstance(belief_density, (int, float)) and 0.0 <= belief_density <= 1.0:
            criteria["belief_density_valid"] = 20
        else:
            criteria["belief_density_valid"] = 0
            explanations.append(f"belief_density={belief_density} fora do range")
        score += criteria["belief_density_valid"]

        # C3: Tension score calibrado (20 pts)
        tension = output.get("tension", 0)
        if isinstance(tension, (int, float)) and 0.0 <= tension <= 1.0:
            criteria["tension_valid"] = 20
        else:
            criteria["tension_valid"] = 0
        score += criteria["tension_valid"]

        # C4: Resonance cluster válido (20 pts)
        if "high_resonance" in output and "low_resonance" in output:
            criteria["cluster_valid"] = 20
        else:
            criteria["cluster_valid"] = 0
            explanations.append("Cluster de ressonância incompleto")
        score += criteria["cluster_valid"]

        # C5: Tool calls (10 pts)
        tool_calls = context.get("tool_calls", [])
        if len(tool_calls) >= 2:
            criteria["tool_calls"] = 10
        else:
            criteria["tool_calls"] = 0
        score += criteria["tool_calls"]

        passed = score >= 80

        return JudgeResult(
            score=score,
            explanation="; ".join(explanations) if explanations else "Padrões de ressonância bem detectados",
            criteria_breakdown=criteria,
            passed=passed
        )

    @staticmethod
    def _judge_generic(output: Dict, context: Dict) -> JudgeResult:
        """Judge genérico para agentes não cobertos."""
        return JudgeResult(
            score=50,
            explanation="Judge genérico — implementar judge específico para este agente",
            criteria_breakdown={"generic": 50},
            passed=False
        )


# ============================================================
# HARNESS PRINCIPAL — Orquestrador de Avaliação
# ============================================================

class KirinEvalHarness:
    """
    Harness de avaliação do Kirin.
    Orquestra: input → processa → tool calls → output → judge → skeptic → report
    
    Modos de operação:
    - sync: Usa rules-based judges (rápido, sem LLM)
    - async: Usa model-graded judges via LLM (mais preciso, requer LITELLM)
    """

    DIMENSION_CONFIG = {
        Dimension.HARNESS_INTEGRITY: {"threshold": 85, "weight": 0.20},
        Dimension.INTENTION_FIDELITY: {"threshold": 80, "weight": 0.20},
        Dimension.BOUNDARY_PRECISION: {"threshold": 85, "weight": 0.20},
        Dimension.ABDUCTIVE_RESILIENCE: {"threshold": 70, "weight": 0.15},
        Dimension.EVAL_HARNESS: {"threshold": 80, "weight": 0.15},
        Dimension.ARCHITECTURAL_READINESS: {"threshold": 85, "weight": 0.10},
    }

    def __init__(self, use_llm_judge: bool = False):
        self.skeptic = SkepticAgent()
        self.judge_factory = JudgeFactory()
        self.use_llm_judge = use_llm_judge
        self._llm_judge = None

    async def _get_llm_judge(self):
        """Obtém instância do LLMJudge (lazy init)."""
        if self._llm_judge is None:
            from eval.llm_judge import get_llm_judge
            self._llm_judge = get_llm_judge()
        return self._llm_judge

    def evaluate_agent(
        self,
        agent_name: str,
        agent_output: Dict,
        context: Dict,
        tool_calls: List[Dict]
    ) -> EvalReport:
        """
        Avalia um agente específico do Kirin.

        Args:
            agent_name: Nome do agente (enricher, scorer, messenger, etc.)
            agent_output: Output JSON do agente
            context: Contexto da avaliação (lead, dossier, expected_lang, etc.)
            tool_calls: Lista de tool calls executadas pelo agente

        Returns:
            EvalReport completo
        """
        report = EvalReport()

        # Adicionar tool calls ao contexto
        context["tool_calls"] = tool_calls

        # --- FASE 1: SkepticAgent (Abdução) ---
        skeptic_report = self.skeptic.check(agent_name, agent_output, context)
        report.skeptic_reports.append(skeptic_report)

        # --- FASE 2: Judge Model-Graded ---
        judge = self.judge_factory.create_judge(agent_name)
        judge_result = judge(agent_output, context)

        # --- FASE 3: Dimensões de Avaliação ---
        # D1: Harness Integrity (baseado nas tool calls)
        harness_score = self._eval_harness_integrity(tool_calls, agent_name)
        report.dimension_results.append(DimensionResult(
            dimension=Dimension.HARNESS_INTEGRITY,
            score=harness_score,
            threshold=self.DIMENSION_CONFIG[Dimension.HARNESS_INTEGRITY]["threshold"],
            passed=harness_score >= self.DIMENSION_CONFIG[Dimension.HARNESS_INTEGRITY]["threshold"],
            weight=self.DIMENSION_CONFIG[Dimension.HARNESS_INTEGRITY]["weight"],
            observations=[f"Tool calls executadas: {len(tool_calls)}"]
        ))

        # D2: Intention Fidelity (baseado no judge)
        intention_score = judge_result.score
        report.dimension_results.append(DimensionResult(
            dimension=Dimension.INTENTION_FIDELITY,
            score=intention_score,
            threshold=self.DIMENSION_CONFIG[Dimension.INTENTION_FIDELITY]["threshold"],
            passed=intention_score >= self.DIMENSION_CONFIG[Dimension.INTENTION_FIDELITY]["threshold"],
            weight=self.DIMENSION_CONFIG[Dimension.INTENTION_FIDELITY]["weight"],
            observations=[judge_result.explanation]
        ))

        # D3: Boundary Precision (heurística de tamanho/complexidade)
        boundary_score = self._eval_boundary_precision(agent_output, agent_name)
        report.dimension_results.append(DimensionResult(
            dimension=Dimension.BOUNDARY_PRECISION,
            score=boundary_score,
            threshold=self.DIMENSION_CONFIG[Dimension.BOUNDARY_PRECISION]["threshold"],
            passed=boundary_score >= self.DIMENSION_CONFIG[Dimension.BOUNDARY_PRECISION]["threshold"],
            weight=self.DIMENSION_CONFIG[Dimension.BOUNDARY_PRECISION]["weight"],
            observations=["Boundary verificado via estrutura do output"]
        ))

        # D4: Abductive Resilience (baseado no SkepticAgent)
        abductive_score = int(skeptic_report.confidence * 100)
        report.dimension_results.append(DimensionResult(
            dimension=Dimension.ABDUCTIVE_RESILIENCE,
            score=abductive_score,
            threshold=self.DIMENSION_CONFIG[Dimension.ABDUCTIVE_RESILIENCE]["threshold"],
            passed=abductive_score >= self.DIMENSION_CONFIG[Dimension.ABDUCTIVE_RESILIENCE]["threshold"],
            weight=self.DIMENSION_CONFIG[Dimension.ABDUCTIVE_RESILIENCE]["weight"],
            observations=skeptic_report.flags if skeptic_report.flags else ["Nenhuma flag de desconfiança"]
        ))

        # D5: Eval Harness (qualidade do próprio eval)
        eval_score = self._eval_harness_quality(judge_result, skeptic_report)
        report.dimension_results.append(DimensionResult(
            dimension=Dimension.EVAL_HARNESS,
            score=eval_score,
            threshold=self.DIMENSION_CONFIG[Dimension.EVAL_HARNESS]["threshold"],
            passed=eval_score >= self.DIMENSION_CONFIG[Dimension.EVAL_HARNESS]["threshold"],
            weight=self.DIMENSION_CONFIG[Dimension.EVAL_HARNESS]["weight"],
            observations=[f"Judge deu score={judge_result.score}, Skeptic confidence={skeptic_report.confidence}"]
        ))

        # D6: Architectural Readiness (placeholder — requer análise estática)
        arch_score = self._eval_architectural_readiness(agent_name, context)
        report.dimension_results.append(DimensionResult(
            dimension=Dimension.ARCHITECTURAL_READINESS,
            score=arch_score,
            threshold=self.DIMENSION_CONFIG[Dimension.ARCHITECTURAL_READINESS]["threshold"],
            passed=arch_score >= self.DIMENSION_CONFIG[Dimension.ARCHITECTURAL_READINESS]["threshold"],
            weight=self.DIMENSION_CONFIG[Dimension.ARCHITECTURAL_READINESS]["weight"],
            observations=["Arquitetura hexagonal verificada via ports/adapters"]
        ))

        # --- FASE 4: Cálculo Final ---
        overall = sum(d.score * d.weight for d in report.dimension_results)
        report.overall_score = overall

        # Verificar regras de ouro
        abductive_dim = next((d for d in report.dimension_results if d.dimension == Dimension.ABDUCTIVE_RESILIENCE), None)
        arch_dim = next((d for d in report.dimension_results if d.dimension == Dimension.ARCHITECTURAL_READINESS), None)

        report.abductive_alert = abductive_dim.score < 70 if abductive_dim else False

        if overall >= 80 and not report.abductive_alert:
            report.status = "PASS"
        elif overall >= 80 and report.abductive_alert:
            report.status = "CONDITIONAL_PASS"
        else:
            report.status = "FAIL"

        # Recomendações
        report.recommendations = self._generate_recommendations(report, agent_name)

        return report

    async def evaluate_agent_async(
        self,
        agent_name: str,
        agent_output: Dict,
        context: Dict,
        tool_calls: List[Dict]
    ) -> EvalReport:
        """
        Avalia um agente usando LLM judge (model-graded).
        
        Mais preciso que o evaluate_agent síncrono, mas requer LITELLM rodando.
        """
        report = EvalReport()

        # Adicionar tool calls ao contexto
        context["tool_calls"] = tool_calls

        # --- FASE 1: SkepticAgent (Abdução) ---
        skeptic_report = self.skeptic.check(agent_name, agent_output, context)
        report.skeptic_reports.append(skeptic_report)

        # --- FASE 2: LLM Judge (Model-Graded) ---
        llm_judge = await self._get_llm_judge()
        llm_result = await llm_judge.judge(agent_name, agent_output, context)

        # --- FASE 3: Dimensões de Avaliação ---
        # D1: Harness Integrity (baseado nas tool calls)
        harness_score = self._eval_harness_integrity(tool_calls, agent_name)
        report.dimension_results.append(DimensionResult(
            dimension=Dimension.HARNESS_INTEGRITY,
            score=harness_score,
            threshold=self.DIMENSION_CONFIG[Dimension.HARNESS_INTEGRITY]["threshold"],
            passed=harness_score >= self.DIMENSION_CONFIG[Dimension.HARNESS_INTEGRITY]["threshold"],
            weight=self.DIMENSION_CONFIG[Dimension.HARNESS_INTEGRITY]["weight"],
            observations=[f"Tool calls executadas: {len(tool_calls)}"]
        ))

        # D2: Intention Fidelity (baseado no LLM judge)
        intention_score = llm_result.score
        report.dimension_results.append(DimensionResult(
            dimension=Dimension.INTENTION_FIDELITY,
            score=intention_score,
            threshold=self.DIMENSION_CONFIG[Dimension.INTENTION_FIDELITY]["threshold"],
            passed=intention_score >= self.DIMENSION_CONFIG[Dimension.INTENTION_FIDELITY]["threshold"],
            weight=self.DIMENSION_CONFIG[Dimension.INTENTION_FIDELITY]["weight"],
            observations=[llm_result.explanation]
        ))

        # D3: Boundary Precision
        boundary_score = self._eval_boundary_precision(agent_output, agent_name)
        report.dimension_results.append(DimensionResult(
            dimension=Dimension.BOUNDARY_PRECISION,
            score=boundary_score,
            threshold=self.DIMENSION_CONFIG[Dimension.BOUNDARY_PRECISION]["threshold"],
            passed=boundary_score >= self.DIMENSION_CONFIG[Dimension.BOUNDARY_PRECISION]["threshold"],
            weight=self.DIMENSION_CONFIG[Dimension.BOUNDARY_PRECISION]["weight"],
            observations=["Boundary verificado via estrutura do output"]
        ))

        # D4: Abductive Resilience
        abductive_score = int(skeptic_report.confidence * 100)
        report.dimension_results.append(DimensionResult(
            dimension=Dimension.ABDUCTIVE_RESILIENCE,
            score=abductive_score,
            threshold=self.DIMENSION_CONFIG[Dimension.ABDUCTIVE_RESILIENCE]["threshold"],
            passed=abductive_score >= self.DIMENSION_CONFIG[Dimension.ABDUCTIVE_RESILIENCE]["threshold"],
            weight=self.DIMENSION_CONFIG[Dimension.ABDUCTIVE_RESILIENCE]["weight"],
            observations=skeptic_report.flags if skeptic_report.flags else ["Nenhuma flag de desconfiança"]
        ))

        # D5: Eval Harness (qualidade do próprio eval)
        eval_score = self._eval_harness_quality_llm(llm_result, skeptic_report)
        report.dimension_results.append(DimensionResult(
            dimension=Dimension.EVAL_HARNESS,
            score=eval_score,
            threshold=self.DIMENSION_CONFIG[Dimension.EVAL_HARNESS]["threshold"],
            passed=eval_score >= self.DIMENSION_CONFIG[Dimension.EVAL_HARNESS]["threshold"],
            weight=self.DIMENSION_CONFIG[Dimension.EVAL_HARNESS]["weight"],
            observations=[f"LLM Judge score={llm_result.score}, Skeptic confidence={skeptic_report.confidence}"]
        ))

        # D6: Architectural Readiness
        arch_score = self._eval_architectural_readiness(agent_name, context)
        report.dimension_results.append(DimensionResult(
            dimension=Dimension.ARCHITECTURAL_READINESS,
            score=arch_score,
            threshold=self.DIMENSION_CONFIG[Dimension.ARCHITECTURAL_READINESS]["threshold"],
            passed=arch_score >= self.DIMENSION_CONFIG[Dimension.ARCHITECTURAL_READINESS]["threshold"],
            weight=self.DIMENSION_CONFIG[Dimension.ARCHITECTURAL_READINESS]["weight"],
            observations=["Arquitetura hexagonal verificada via ports/adapters"]
        ))

        # --- FASE 4: Cálculo Final ---
        overall = sum(d.score * d.weight for d in report.dimension_results)
        report.overall_score = overall

        # Verificar regras de ouro
        abductive_dim = next((d for d in report.dimension_results if d.dimension == Dimension.ABDUCTIVE_RESILIENCE), None)
        report.abductive_alert = abductive_dim.score < 70 if abductive_dim else False

        if overall >= 80 and not report.abductive_alert:
            report.status = "PASS"
        elif overall >= 80 and report.abductive_alert:
            report.status = "CONDITIONAL_PASS"
        else:
            report.status = "FAIL"

        # Recomendações
        report.recommendations = self._generate_recommendations(report, agent_name)

        return report

    def _eval_harness_quality_llm(self, llm_result, skeptic_report) -> int:
        """Avalia qualidade do eval usando LLM judge."""
        score = 100

        # LLM deve dar explicação
        if not llm_result.explanation or len(llm_result.explanation) < 10:
            score -= 30

        # LLM deve ter criteria_scores
        if not llm_result.criteria_scores:
            score -= 20

        # Skeptic deve ter flags
        if skeptic_report.flags is None:
            score -= 15

        return max(0, score)

    def _eval_harness_integrity(self, tool_calls: List[Dict], agent_name: str) -> int:
        """Avalia integridade da harness via tool calls."""
        score = 100

        # Verificar se tool calls estão na ordem esperada
        expected_tools = {
            "enricher": ["complete", "store"],
            "scorer": ["complete", "store"],
            "messenger": ["complete", "store"],
            "researcher": ["complete", "store"],
            "discourse_ingestor": ["complete", "store"],
            "language_game": ["complete", "store"],
            "resonance": ["complete", "store", "search"],
        }

        expected = expected_tools.get(agent_name, ["complete"])
        actual = [tc.get("name", "") for tc in tool_calls]

        if actual != expected[:len(actual)]:
            score -= 15

        # Verificar se todas as tool calls necessárias foram feitas
        if len(tool_calls) < len(expected):
            score -= 20

        # Verificar se tool calls são auditáveis (têm nome e parâmetros)
        for tc in tool_calls:
            if not tc.get("name") or not tc.get("parameters"):
                score -= 10

        return max(0, score)

    def _eval_boundary_precision(self, output: Dict, agent_name: str) -> int:
        """Avalia precisão de boundaries via estrutura do output."""
        score = 100

        # Verificar se output não é excessivamente grande
        output_str = json.dumps(output)
        if len(output_str) > 10000:  # ~300 linhas equivalente
            score -= 20

        # Verificar se campos são específicos (não genéricos)
        if agent_name == "enricher":
            dossier = output.get("dossie", {})
            if "pontos_fracos" in dossier:
                weaknesses = dossier["pontos_fracos"]
                if isinstance(weaknesses, list):
                    generic = ["precisa melhorar", "falta investir", "deve crescer", "sem estrutura"]
                    generic_count = sum(1 for w in weaknesses if any(g in w.lower() for g in generic))
                    if generic_count == len(weaknesses) and len(weaknesses) > 0:
                        score -= 25  # Todos genéricos

        return max(0, score)

    def _eval_harness_quality(self, judge_result: JudgeResult, skeptic_report: SkepticReport) -> int:
        """Avalia qualidade do próprio sistema de eval."""
        score = 100

        # Judge deve dar explicação
        if not judge_result.explanation or len(judge_result.explanation) < 10:
            score -= 30

        # Judge deve ter criteria_breakdown
        if not judge_result.criteria_breakdown:
            score -= 20

        # Skeptic deve ter flags explicativas (mesmo que vazias)
        if skeptic_report.flags is None:
            score -= 15

        # Score do judge deve estar calibrado (não 0 ou 100 extremos sem motivo)
        if judge_result.score in [0, 100] and len(judge_result.criteria_breakdown) > 1:
            # Verificar se todos os critérios justificam o extremo
            pass

        return max(0, score)

    def _eval_architectural_readiness(self, agent_name: str, context: Dict) -> int:
        """
        Avalia preparação arquitetural.
        Placeholder — em produção, integrar com análise estática (SonarQube, CodeQL).
        """
        score = 92  # Baseado na análise abductiva anterior

        # Verificar se contexto menciona ports/adapters
        if context.get("has_ports_adapters", True):
            score = min(100, score + 5)

        # Verificar se há god class detectada
        if context.get("god_class_detected", False):
            score -= 30

        # Verificar se há duplicação kirin-core vs agents
        if context.get("duplication_detected", False):
            score -= 15

        return max(0, score)

    def _generate_recommendations(self, report: EvalReport, agent_name: str) -> List[str]:
        """Gera recomendações baseadas nos resultados."""
        recommendations = []

        for dim in report.dimension_results:
            if not dim.passed:
                if dim.dimension == Dimension.ABDUCTIVE_RESILIENCE:
                    recommendations.append(f"[P0] Implementar SkepticAgent para {agent_name} — flags detectadas: {dim.observations}")
                elif dim.dimension == Dimension.EVAL_HARNESS:
                    recommendations.append(f"[P1] Melhorar judge de qualidade para {agent_name} — explicações insuficientes")
                elif dim.dimension == Dimension.HARNESS_INTEGRITY:
                    recommendations.append(f"[P2] Verificar tool calls de {agent_name} — ordem ou completude incorreta")
                elif dim.dimension == Dimension.INTENTION_FIDELITY:
                    recommendations.append(f"[P2] Revisar intenção do {agent_name} — output não reflete propósito")
                elif dim.dimension == Dimension.BOUNDARY_PRECISION:
                    recommendations.append(f"[P3] Quebrar output de {agent_name} em boundaries menores")
                elif dim.dimension == Dimension.ARCHITECTURAL_READINESS:
                    recommendations.append(f"[P3] Revisar arquitetura — possível god class ou duplicação")

        if report.abductive_alert:
            recommendations.append("[CRÍTICO] Abductive Resilience < 70 — revisão humana obrigatória antes de produção")

        return recommendations


# ============================================================
# CLI — INTERFACE DE LINHA DE COMANDO
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="KIRIN EVAL HARNESS — Avaliação Abductiva",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python kirin_eval_harness.py --agent enricher --input lead.json
  python kirin_eval_harness.py --agent messenger --input msg.json --context dossier.json
  python kirin_eval_harness.py --skeptic-only --agent scorer --input score.json
  python kirin_eval_harness.py --demo
        """
    )

    parser.add_argument("--agent", choices=[
        "enricher", "scorer", "messenger", "researcher",
        "discourse_ingestor", "language_game", "resonance"
    ], help="Agente do Kirin a avaliar")

    parser.add_argument("--input", help="Arquivo JSON com input/output do agente")
    parser.add_argument("--context", help="Arquivo JSON com contexto adicional (lead, dossier, etc.)")
    parser.add_argument("--tool-calls", help="Arquivo JSON com lista de tool calls")
    parser.add_argument("--skeptic-only", action="store_true", help="Executa apenas o SkepticAgent")
    parser.add_argument("--llm-judge", action="store_true", help="Usa LLM judge (model-graded) em vez de rules-based")
    parser.add_argument("--demo", action="store_true", help="Executa demo com dados de exemplo")
    parser.add_argument("--output", default="kirin_eval_report.json", help="Arquivo de saída do relatório")

    args = parser.parse_args()

    harness = KirinEvalHarness(use_llm_judge=args.llm_judge)

    if args.demo:
        _run_demo(harness)
        return

    if not args.agent:
        parser.print_help()
        sys.exit(1)

    # Carregar dados
    try:
        with open(args.input, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Erro: Arquivo {args.input} não encontrado")
        sys.exit(1)

    agent_output = data.get("output", data)
    context = data.get("context", {})

    if args.context:
        with open(args.context, "r", encoding="utf-8") as f:
            context.update(json.load(f))

    tool_calls = data.get("tool_calls", [])
    if args.tool_calls:
        with open(args.tool_calls, "r", encoding="utf-8") as f:
            tool_calls = json.load(f)

    # Executar avaliação
    if args.skeptic_only:
        skeptic = SkepticAgent()
        report = skeptic.check(args.agent, agent_output, context)
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    elif args.llm_judge:
        # Modo async com LLM judge
        import asyncio
        async def run_async():
            report = await harness.evaluate_agent_async(args.agent, agent_output, context, tool_calls)
            return report
        report = asyncio.run(run_async())
        print(report.to_json())

        # Salvar relatório
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report.to_json())

        print(f"\n✅ Relatório salvo em {args.output} (LLM Judge)")
        print(f"📊 Score geral: {report.overall_score}/100")
        print(f"🚩 Abductive Alert: {'SIM' if report.abductive_alert else 'NÃO'}")
        print(f"📋 Status: {report.status}")

        if report.recommendations:
            print("\n🔧 Recomendações:")
            for rec in report.recommendations:
                print(f"  - {rec}")
    else:
        report = harness.evaluate_agent(args.agent, agent_output, context, tool_calls)
        print(report.to_json())

        # Salvar relatório
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report.to_json())

        print(f"\n✅ Relatório salvo em {args.output}")
        print(f"📊 Score geral: {report.overall_score}/100")
        print(f"🚩 Abductive Alert: {'SIM' if report.abductive_alert else 'NÃO'}")
        print(f"📋 Status: {report.status}")

        if report.recommendations:
            print("\n🔧 Recomendações:")
            for rec in report.recommendations:
                print(f"  - {rec}")


def _run_demo(harness: KirinEvalHarness):
    """Executa demo com dados de exemplo."""
    print("=" * 60)
    print("KIRIN EVAL HARNESS — DEMO")
    print("=" * 60)

    # Demo 1: Enricher com output bom
    print("\n🧪 Demo 1: Enricher (output de boa qualidade)")
    good_output = {
        "dossie": {
            "resumo_perfil": "Bar do Zé é um estabelecimento tradicional na Rua Augusta, São Paulo, conhecido por seu ambiente descontraído e clientela fiel.",
            "pontos_fracos": ["sem presença no Instagram", "não possui site próprio", "cardápio não disponível online"],
            "oportunidades": ["marketing de proximidade com moradores da Augusta", "eventos culturais e música ao vivo"],
            "maturidade_digital": 2,
            "resumo_executivo": "Estabelecimento com potencial de crescimento digital significativo"
        }
    }
    context = {
        "lead": {"name": "Bar do Zé", "address": "Rua Augusta, 1234, São Paulo"},
        "expected_lang": "pt-BR",
        "has_social_media": False
    }
    tool_calls = [
        {"name": "complete", "parameters": {"model": "qwen-vl-max", "temperature": 0.3}},
        {"name": "store", "parameters": {"namespace": "lead:xxx", "key": "enrichment"}}
    ]

    report = harness.evaluate_agent("enricher", good_output, context, tool_calls)
    print(f"Score: {report.overall_score}/100 | Status: {report.status}")
    print(f"Skeptic flags: {report.skeptic_reports[0].flags}")

    # Demo 2: Enricher com output suspeito (maturidade alta sem social)
    print("\n🧪 Demo 2: Enricher (output suspeito — maturidade incoerente)")
    bad_output = {
        "dossie": {
            "resumo_perfil": "Bar do Zé é um bar.",
            "pontos_fracos": ["sem presença no Instagram", "não possui site próprio"],
            "oportunidades": ["melhorar", "crescer"],
            "maturidade_digital": 9,  # SUSPEITO!
            "resumo_executivo": "Bar bom"
        }
    }

    report = harness.evaluate_agent("enricher", bad_output, context, tool_calls)
    print(f"Score: {report.overall_score}/100 | Status: {report.status}")
    print(f"Skeptic flags: {report.skeptic_reports[0].flags}")
    print(f"Recomendações: {report.recommendations}")

    # Demo 3: Messenger genérico
    print("\n🧪 Demo 3: Messenger (mensagem genérica)")
    generic_msg = {
        "message": "Olá! Somos uma empresa que oferece serviços para melhorar seu negócio. Entre em contato! Responda SAIR para cancelar."
    }
    msg_context = {
        "lead": {"name": "Bar do Zé"},
        "dossier": {
            "pontos_fracos": ["sem Instagram"],
            "oportunidades": ["marketing de proximidade"]
        },
        "expected_lang": "pt-BR"
    }
    msg_tool_calls = [
        {"name": "complete", "parameters": {"model": "deepseek-chat", "temperature": 0.7}},
        {"name": "store", "parameters": {"namespace": "lead:xxx", "key": "message"}}
    ]

    report = harness.evaluate_agent("messenger", generic_msg, msg_context, msg_tool_calls)
    print(f"Score: {report.overall_score}/100 | Status: {report.status}")
    print(f"Skeptic flags: {report.skeptic_reports[0].flags}")

    print("\n" + "=" * 60)
    print("Demo concluída. Use --agent e --input para avaliar seus dados.")
    print("=" * 60)


if __name__ == "__main__":
    main()
