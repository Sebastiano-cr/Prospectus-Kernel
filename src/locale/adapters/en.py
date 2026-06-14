"""
ENLocaleAdapter — Implementação completa do LocalePort para inglês.

Field names mantêm as chaves portuguesas (resumo_perfil, etc.) para compatibilidade
JSON entre todos os locales. Texto de prompts, fallbacks, status e marcadores em inglês.
"""
from typing import Any, Dict, List
from ..port import LocalePort
from ..errors import PromptNotFoundError

import os
import logging

logger = logging.getLogger(__name__)

_PROMPT_DIR = os.path.join(os.path.dirname(__file__), "..", "prompts", "en")

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
    "new": "new",
    "enriched": "enriched",
    "scored": "scored",
    "researched": "researched",
    "message_generated": "message_generated",
    "message_sent": "message_sent",
    "message_failed": "message_failed",
    "converted": "converted",
    "lost": "lost",
    "blocked": "blocked",
}

_SCORE_RANGES: Dict[str, tuple] = {
    "cold": (0, 39),
    "warm": (40, 69),
    "hot": (70, 100),
}

_SCORE_CATEGORIES: Dict[str, str] = {
    "cold": "cold",
    "warm": "warm",
    "hot": "hot",
}

_FALLBACKS: Dict[str, str] = {
    "unknown_establishment": "Unknown establishment",
    "address_not_provided": "Address not provided",
    "phone_not_provided": "Phone not provided",
    "website_not_provided": "Website not provided",
    "instagram_not_provided": "Instagram not provided",
    "profile_not_available": "Profile not available",
    "no_weaknesses": "No weaknesses identified",
    "no_opportunities": "No opportunities identified",
    "enrichment_failed": "Enrichment failed",
    "enrichment_failed_detail": "Could not generate dossier due to enrichment failure",
    "not_available": "Not available",
    "insufficient_data": "Insufficient data for detailed analysis",
    "opt_out_message": "\n\nReply STOP to stop receiving messages.",
    "medium_maturity": "medium",
    "high_maturity": "high",
    "low_maturity": "low",
    "default_weakness": "opportunities for improvement in digital marketing",
    "default_area_services": "local services",
    "default_area_online": "online presence",
    "default_area_social": "social media engagement",
    "default_weakness_fallback": "digital presence could be strengthened",
    "internal_error": "Internal server error",
    "api_key_not_configured": "API_KEY not configured. Set the API_KEY environment variable.",
    "invalid_api_key": "Invalid API key",
    "enrichment_error": "Internal enrichment error",
    "scoring_error": "Internal scoring error",
    "message_error": "Internal message generation error",
    "research_error": "Internal research error",
    "crm_error": "Internal CRM sync error",
    "discourse_error": "Internal discourse extraction error",
    "resonance_error": "Internal resonance analysis error",
    "resonance_lookup_error": "Internal resonance lookup error",
    "prospect_error": "Internal prospect generation error",
    "signal_error": "Internal signal recording error",
    "rate_limit_exceeded": "Rate limit exceeded. Maximum of {limit} requests per minute.",
    "not_configured": "not configured",
}

_MARKERS: Dict[str, List[str]] = {
    "generic_phrases": [
        "we help businesses", "we are a company", "our platform",
        "we offer solutions", "we specialize", "we provide services",
        "schedule a demo", "book a call", "learn more",
        "this is a great opportunity", "don't miss out",
    ],
    "social_absence": [
        "no instagram", "no facebook", "no linkedin", "no website",
        "weak digital presence", "doesn't have a website", "no social media",
    ],
    "emotion_anger":   ["hate", "disgust", "terrible", "horrible", "angry", "furious"],
    "emotion_sadness": ["cry", "tears", "depressed", "sad", "lonely", "heartbreaking"],
    "emotion_joy":     ["happy", "joyful", "delighted", "wonderful", "amazing", "excellent"],
    "emotion_fear":    ["fear", "terror", "panic", "scared", "worried", "afraid"],
}

_LANGUAGE_MARKERS: Dict[str, List[str]] = {
    "en": ["the ", "and ", "is ", "to ", "of ", "for ", "with ", "in ", "a "],
    "pt": ["o ", "a ", "e ", "de ", "para ", "com ", "do ", "da "],
}

_PARSER_KEYWORDS: Dict[str, List[str]] = {
    "profile_summary":   ["profile", "summary", "resumo", "perfil"],
    "weaknesses":        ["weakness", "weaknesses", "pontos fracos", "fraqueza"],
    "opportunities":     ["opportunit", "oportunidade"],
    "digital_maturity":  ["digital", "maturity", "madurez", "maturidade"],
}


class ENLocaleAdapter(LocalePort):
    """Complete implementation of LocalePort for English."""

    language_code = "en"
    _prompt_cache: Dict[str, str] = {}

    # ── Prompts ───────────────────────────────────────────────────────

    def get_prompt(self, prompt_type: str, /, **context: Any) -> str:
        template = self._load_prompt(prompt_type)
        return template.format(**context)

    def _load_prompt(self, prompt_type: str) -> str:
        cached = self._prompt_cache.get(prompt_type)
        if cached is not None:
            return cached
        filename = os.path.join(_PROMPT_DIR, f"{prompt_type}.prompt.md")
        if not os.path.isfile(filename):
            raise PromptNotFoundError(prompt_type, "en")
        with open(filename, "r", encoding="utf-8") as f:
            content = f.read()
        self._prompt_cache[prompt_type] = content
        return content

    # ── Schema fields ─────────────────────────────────────────────────

    def get_field_name(self, canonical_key: str) -> str:
        return _FIELD_MAP.get(canonical_key, canonical_key)

    def get_field_names(self, canonical_keys: List[str]) -> Dict[str, str]:
        return {k: self.get_field_name(k) for k in canonical_keys}

    # ── Score ─────────────────────────────────────────────────────────

    def get_score_category(self, score: int) -> str:
        for category, (lo, hi) in _SCORE_RANGES.items():
            if lo <= score <= hi:
                return _SCORE_CATEGORIES[category]
        return "cold"

    def get_score_ranges(self) -> Dict[str, tuple]:
        return dict(_SCORE_RANGES)

    # ── Status ────────────────────────────────────────────────────────

    def get_status_label(self, status_key: str) -> str:
        return _STATUS_MAP.get(status_key, status_key)

    def get_statuses(self) -> Dict[str, str]:
        return dict(_STATUS_MAP)

    # ── Fallbacks ─────────────────────────────────────────────────────

    def get_fallback(self, key: str) -> str:
        return _FALLBACKS.get(key, key)

    # ── SkepticAgent ──────────────────────────────────────────────────

    def get_markers(self, marker_type: str) -> List[str]:
        return _MARKERS.get(marker_type, [])

    def get_language_markers(self) -> Dict[str, List[str]]:
        return dict(_LANGUAGE_MARKERS)

    # ── Parsing keywords ──────────────────────────────────────────────

    def get_parser_keywords(self, section: str) -> List[str]:
        return _PARSER_KEYWORDS.get(section, [section])

    # ── Utils ─────────────────────────────────────────────────────────

    def get_json_only_suffix(self) -> str:
        return "\n\nRespond ONLY with valid JSON, no additional text."
