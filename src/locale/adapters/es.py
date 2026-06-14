"""
ESLocaleAdapter — LocalePort para espanhol.
"""
from typing import Any, Dict, List
from ..port import LocalePort
from ..errors import PromptNotFoundError

import os
import logging

logger = logging.getLogger(__name__)

_PROMPT_DIR = os.path.join(os.path.dirname(__file__), "..", "prompts", "es")
_JSON_ONLY_SUFFIX = "Responda SOLAMENTE con el JSON válido, sin texto adicional."


_FIELD_MAP: Dict[str, str] = {
    "profile_summary":     "resumo_perfil",
    "weaknesses":          "pontos_fracos",
    "opportunities":       "oportunidades",
    "digital_maturity":    "maturidade_digital",
    "dossier":             "dossie",
    "sources_consulted":   "fontes_consultadas",
    "research":            "pesquisa",
    "score":               "score",
    "score_justification": "score_justification",
    "score_category":      "faixa",
    "status":              "status",
    "whatsapp_status":     "whatsapp_status",
    "delivery_status":     "delivery_status",
    "generated_message":   "generated_message",
}

_STATUS_MAP: Dict[str, str] = {
    "new":              "nuevo",
    "initial_contact":  "contacto_inicial",
    "scheduling":       "agendamiento",
    "enriched":         "enriquecido",
    "qualified":        "calificado",
    "researched":       "investigado",
    "message_sent":     "mensaje_enviado",
    "replied":          "respondió",
    "sold":             "vendido",
    "transferred":      "transferido",
    "discarded":        "descartado",
    "sent":             "enviado",
    "failed":           "fallo",
    "invalid_phone":    "teléfono_inválido",
    "daily_limit":      "límite_diario",
    "gateway_error":    "error_gateway",
    "blocked":          "bloqueado",
}

_SCORE_RANGES: Dict[str, tuple] = {
    "hot":  (70, 100),
    "warm": (40, 69),
    "cold": (0, 39),
}

_SCORE_CATEGORIES: Dict[str, str] = {
    "hot":  "caliente",
    "warm": "tibio",
    "cold": "frío",
}

_FALLBACKS: Dict[str, str] = {
    "unknown_establishment":      "Establecimiento desconocido",
    "address_not_provided":       "Dirección no proporcionada",
    "phone_not_provided":         "Teléfono no proporcionado",
    "website_not_provided":       "Sitio web no proporcionado",
    "instagram_not_provided":     "Instagram no proporcionado",
    "profile_not_available":      "Perfil no disponible",
    "no_weaknesses":             "Ningún punto débil identificado",
    "no_opportunities":          "Ninguna oportunidad identificada",
    "enrichment_failed":          "Enriquecimiento falló",
    "enrichment_failed_detail":   "No fue posible generar el dossier debido a una falla en el enriquecimiento",
    "not_available":              "No disponible",
    "insufficient_data":          "Información insuficiente para análisis detallado",
    "opt_out_message":            "\n\nResponda SALIR para no recibir más contactos.",
    "medium_maturity":            "medio",
    "high_maturity":              "alto",
    "low_maturity":               "bajo",
    "default_weakness":           "oportunidades de mejora en marketing digital",
    "default_area_services":      "servicios locales",
    "default_area_online":        "presencia en línea",
    "default_area_social":        "participación en redes sociales",
    "default_weakness_fallback":  "la presencia digital podría fortalecerse",
    "internal_error":             "Error interno del servidor",
    "api_key_not_configured":     "API_KEY no configurada. Defina la variable de entorno API_KEY.",
    "invalid_api_key":            "API key inválida",
    "enrichment_error":           "Error interno en el enriquecimiento",
    "scoring_error":              "Error interno en la puntuación",
    "message_error":              "Error interno en la generación del mensaje",
    "research_error":             "Error interno en la investigación",
    "crm_error":                  "Error interno en la sincronización CRM",
    "discourse_error":            "Error interno en la extracción de discurso",
    "resonance_error":            "Error interno en el análisis de resonancia",
    "resonance_lookup_error":     "Error interno en la búsqueda de resonancia",
    "prospect_error":             "Error interno en la generación de prospecto",
    "signal_error":               "Error interno en el registro de señal",
    "rate_limit_exceeded":        "Límite de solicitudes excedido. Máximo de {limit} solicitudes por minuto.",
    "not_configured":             "no configurada",
}

_MARKERS: Dict[str, List[str]] = {
    "generic_phrases": [
        "somos una empresa", "ofrecemos servicios", "mejorar su negocio",
        "su empresa", "su negocio", "nuestros servicios",
    ],
    "social_absence": [
        "sin instagram", "sin facebook", "sin linkedin", "sin sitio web",
        "presencia digital débil", "no tiene sitio web", "no tiene red social",
    ],
    "emotion_anger":   ["odio", "asco", "infierno", "detesto", "rabia", "enojado"],
    "emotion_sadness": ["llanto", "lágrima", "depresión", "triste", "soledad"],
    "emotion_joy":     ["feliz", "alegre", "contento", "maravilloso", "increíble"],
    "emotion_fear":    ["miedo", "terror", "pánico", "asustado", "preocupado"],
}

_LANGUAGE_MARKERS: Dict[str, List[str]] = {
    "es": ["el ", "la ", "y ", "de ", "para ", "con ", "del ", "las "],
    "en": ["the ", "and ", "is ", "to ", "of ", "for ", "with "],
}


class ESLocaleAdapter(LocalePort):

    language_code = "es"
    _prompt_cache: Dict[str, str] = {}

    def get_prompt(self, prompt_type: str, /, **context: Any) -> str:
        template = self._load_prompt(prompt_type)
        return template.format(**context)

    def _load_prompt(self, prompt_type: str) -> str:
        cached = self._prompt_cache.get(prompt_type)
        if cached is not None:
            return cached
        filename = os.path.join(_PROMPT_DIR, f"{prompt_type}.prompt.md")
        if not os.path.isfile(filename):
            raise PromptNotFoundError(prompt_type, "es")
        with open(filename, "r", encoding="utf-8") as f:
            content = f.read()
        self._prompt_cache[prompt_type] = content
        return content

    def get_field_name(self, canonical_key: str) -> str:
        return _FIELD_MAP.get(canonical_key, canonical_key)

    def get_field_names(self, canonical_keys: List[str]) -> Dict[str, str]:
        return {k: self.get_field_name(k) for k in canonical_keys}

    def get_score_category(self, score: int) -> str:
        for category, (lo, hi) in _SCORE_RANGES.items():
            if lo <= score <= hi:
                return _SCORE_CATEGORIES[category]
        return _SCORE_CATEGORIES["cold"]

    def get_score_ranges(self) -> Dict[str, tuple]:
        return dict(_SCORE_RANGES)

    def get_status_label(self, status_key: str) -> str:
        return _STATUS_MAP.get(status_key, status_key)

    def get_statuses(self) -> Dict[str, str]:
        return dict(_STATUS_MAP)

    def get_fallback(self, key: str) -> str:
        return _FALLBACKS.get(key, key)

    def get_markers(self, marker_type: str) -> List[str]:
        return _MARKERS.get(marker_type, [])

    def get_language_markers(self) -> Dict[str, List[str]]:
        return dict(_LANGUAGE_MARKERS)

    def get_parser_keywords(self, section: str) -> List[str]:
        _keywords = {
            "profile_summary":  ["resumen", "perfil", "profile"],
            "weaknesses":       ["puntos débiles", "punto débil", "debilidad", "debilidades", "weak"],
            "opportunities":    ["oportunidad", "oportunidades", "opportunity", "opportunities"],
            "digital_maturity": ["madurez", "digital", "maturity"],
        }
        return _keywords.get(section, [section])

    def get_json_only_suffix(self) -> str:
        return _JSON_ONLY_SUFFIX
