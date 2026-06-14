"""
SkepticAgent — Mecanismo de Desconfiança para o Kirin.

O SkepticAgent é um agente cético que roda APÓS cada LLM call e "cheira" inconsistências.
Ele não substitui o eval — ele é o filtro abductivo que o eval determinístico não pode ser.

Baseado em: Augusto Galego (Groomy, Harness, Evals) + Abdução Sistêmica
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from src.locale import get_locale, LocalePort

logger = logging.getLogger(__name__)


@dataclass
class SkepticReport:
    """Relatório do SkepticAgent — o "cheiro" de desconfiança."""
    passed: bool
    flags: List[str] = field(default_factory=list)
    confidence: float = 1.0
    agent_name: str = ""

    def to_dict(self) -> Dict:
        return {
            "passed": self.passed,
            "flags": self.flags,
            "confidence": round(self.confidence, 2),
            "agent_name": self.agent_name,
            "flag_count": len(self.flags)
        }


class SkepticAgent:
    """
    Agente cético que "cheira" inconsistências nos outputs dos LLMs.
    
    Heurísticas de Desconfiança:
        H1: Score vs. Dossier mismatch
        H2: Mensagem muito genérica
        H3: Fonte inexistente
        H4: Idioma desviado
        H5: Tamanho suspeito
        H6: Maturidade incoerente
        H7: Emoção inconsistente
    """

    def __init__(self):
        self.heuristics = {
            "H1": self._check_score_vs_dossier,
            "H2": self._check_generic_message,
            "H3": self._check_fake_sources,
            "H4": self._check_language_deviation,
            "H5": self._check_suspicious_length,
            "H6": self._check_maturity_incoherence,
            "H7": self._check_emotion_inconsistency,
        }

    def check(
        self,
        agent_name: str,
        output: Dict[str, Any],
        context: Dict[str, Any],
        locale: Optional[LocalePort] = None,
    ) -> SkepticReport:
        flags = []

        for heuristic_id, heuristic_fn in self.heuristics.items():
            try:
                result = heuristic_fn(agent_name, output, context, locale)
                if result:
                    flags.append(f"{heuristic_id}: {result}")
                    logger.warning(f"SkepticAgent flagged {heuristic_id} for {agent_name}: {result}")
            except Exception as e:
                flags.append(f"{heuristic_id}: ERRO na heurística — {str(e)}")
                logger.error(f"SkepticAgent error in {heuristic_id}: {e}")

        confidence = max(0.0, 1.0 - (len(flags) * 0.15))

        report = SkepticReport(
            passed=len(flags) == 0,
            flags=flags,
            confidence=confidence,
            agent_name=agent_name
        )

        if flags:
            logger.info(f"SkepticAgent: {len(flags)} flags for {agent_name}, confidence={confidence:.2f}")

        return report

    # --- Heurísticas ---

    def _check_score_vs_dossier(self, agent_name: str, output: Dict, context: Dict, locale: Optional[LocalePort] = None) -> Optional[str]:
        locale = locale or get_locale("pt-BR")
        if agent_name != "scorer":
            return None

        score = output.get("score", 0)
        dossier = context.get("dossier", {})
        weaknesses_field = locale.get_field_name("weaknesses")

        if score > 80 and weaknesses_field in dossier:
            weaknesses = dossier[weaknesses_field]
            if isinstance(weaknesses, list) and len(weaknesses) > 3:
                return f"Score={score} (alto) mas {len(weaknesses)} {weaknesses_field} — mismatch"
        return None

    def _check_generic_message(self, agent_name: str, output: Dict, context: Dict, locale: Optional[LocalePort] = None) -> Optional[str]:
        locale = locale or get_locale("pt-BR")
        if agent_name != "messenger":
            return None

        message = output.get("message", "")
        lead_name = context.get("lead", {}).get("name", "")

        generic_phrases = locale.get_markers("generic_phrases")

        generic_count = sum(1 for phrase in generic_phrases if phrase.lower() in message.lower())

        if generic_count >= 3 and lead_name not in message:
            return f"Mensagem genérica ({generic_count} frases genéricas) e não menciona '{lead_name}'"
        return None

    def _check_fake_sources(self, agent_name: str, output: Dict, context: Dict, locale: Optional[LocalePort] = None) -> Optional[str]:
        locale = locale or get_locale("pt-BR")
        if agent_name != "researcher":
            return None

        sources_field = locale.get_field_name("sources_consulted")
        sources = output.get(sources_field, [])
        suspicious = []

        for source in sources:
            url = source.get("url", "") if isinstance(source, dict) else str(source)
            if not url.startswith(("http://", "https://")):
                suspicious.append(url)
            elif any(bad in url.lower() for bad in ["example.com", "localhost", "test"]):
                suspicious.append(url)

        if suspicious:
            return f"Fontes suspeitas: {suspicious[:3]}"
        return None

    def _check_language_deviation(self, agent_name: str, output: Dict, context: Dict, locale: Optional[LocalePort] = None) -> Optional[str]:
        locale = locale or get_locale("pt-BR")
        if agent_name not in ["messenger", "enricher", "language_game"]:
            return None

        expected_lang = context.get("expected_lang", locale.language_code)
        if expected_lang != locale.language_code:
            return None

        text = str(output)
        lang_markers = locale.get_language_markers()
        en_markers = lang_markers.get("en", ["the ", "and ", "is ", "to ", "of ", "for ", "with "])
        pt_markers = lang_markers.get("pt", ["o ", "a ", "e ", "de ", "para ", "com ", "do ", "da "])

        en_count = sum(1 for marker in en_markers if marker in text.lower())
        pt_count = sum(1 for marker in pt_markers if marker in text.lower())

        if en_count > pt_count * 0.5:
            return f"Output parece estar em inglês ({en_count} markers EN vs {pt_count} markers PT)"
        return None

    def _check_suspicious_length(self, agent_name: str, output: Dict, context: Dict, locale: Optional[LocalePort] = None) -> Optional[str]:
        locale = locale or get_locale("pt-BR")
        if agent_name == "messenger":
            message = output.get("message", "")
            if len(message) == 300:
                return "Mensagem EXATAMENTE no limite de 300 chars — suspeito de corte forçado"
            if len(message) < 50:
                return f"Mensagem muito curta ({len(message)} chars) — possível falha na geração"

        if agent_name == "enricher":
            dossier = output.get("dossie", {})
            profile_field = locale.get_field_name("profile_summary")
            resumo = dossier.get(profile_field, "")
            if len(resumo) < 20:
                return f"Resumo do perfil muito curto ({len(resumo)} chars) — possível alucinação ou falha"

        return None

    def _check_maturity_incoherence(self, agent_name: str, output: Dict, context: Dict, locale: Optional[LocalePort] = None) -> Optional[str]:
        locale = locale or get_locale("pt-BR")
        if agent_name != "enricher":
            return None

        dossier = output.get("dossie", {})
        maturidade = str(dossier.get(locale.get_field_name("digital_maturity"), "médio")).lower()

        has_social = context.get("has_social_media", True)
        weaknesses_field = locale.get_field_name("weaknesses")
        pontos_fracos = dossier.get(weaknesses_field, [])

        is_high = locale.get_fallback("high_maturity") in maturidade

        no_social_indicators = locale.get_markers("social_absence")

        has_no_social = any(
            indicator in str(pf).lower()
            for pf in (pontos_fracos if isinstance(pontos_fracos, list) else [])
            for indicator in no_social_indicators
        )

        if is_high and (has_no_social or not has_social):
            return f"Maturidade='{maturidade}' (alta) mas {weaknesses_field} indicam ausência de presença digital"
        return None

    def _check_emotion_inconsistency(self, agent_name: str, output: Dict, context: Dict, locale: Optional[LocalePort] = None) -> Optional[str]:
        locale = locale or get_locale("pt-BR")
        if agent_name != "discourse_ingestor":
            return None

        emotion = output.get("emotion", "")
        text = output.get("text", "")

        emotion_markers = {
            "raiva": locale.get_markers("emotion_anger"),
            "tristeza": locale.get_markers("emotion_sadness"),
            "alegria": locale.get_markers("emotion_joy"),
            "medo": locale.get_markers("emotion_fear"),
        }

        if emotion in emotion_markers:
            markers = emotion_markers[emotion]
            found = sum(1 for marker in markers if marker in text.lower())
            if found == 0:
                return f"Emoção='{emotion}' mas nenhum marker encontrado no texto"

        return None


_skeptic_instance: Optional[SkepticAgent] = None


def get_skeptic() -> SkepticAgent:
    global _skeptic_instance
    if _skeptic_instance is None:
        _skeptic_instance = SkepticAgent()
    return _skeptic_instance


def check_agent_output(
    agent_name: str,
    output: Dict[str, Any],
    context: Dict[str, Any],
    locale: Optional[LocalePort] = None,
) -> SkepticReport:
    skeptic = get_skeptic()
    return skeptic.check(agent_name, output, context, locale)
