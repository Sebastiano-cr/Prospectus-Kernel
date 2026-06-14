"""
PTBRLocaleAdapter — Implementação completa do LocalePort para português brasileiro.

Todas as strings foram extraídas do código existente (agentes, eval, templates).
Zero mudança de comportamento — apenas realocação para a camada de locale.
"""
from typing import Any, Dict, List
from ..port import LocalePort
from ..errors import PromptNotFoundError

import os
import logging

logger = logging.getLogger(__name__)

_PROMPT_DIR = os.path.join(os.path.dirname(__file__), "..", "prompts", "pt-BR")
_JSON_ONLY_SUFFIX = "Responda APENAS com o JSON válido, sem texto adicional."


# ─── Field Names (Schema Mapping) ──────────────────────────────────────

_FIELD_MAP: Dict[str, str] = {
    # Dossier / enricher
    "profile_summary":     "resumo_perfil",
    "weaknesses":          "pontos_fracos",
    "opportunities":       "oportunidades",
    "digital_maturity":    "maturidade_digital",
    "dossier":             "dossie",
    "sources_consulted":   "fontes_consultadas",
    "research":            "pesquisa",
    # Score
    "score":               "score",
    "score_justification": "score_justification",
    "score_category":      "faixa",
    # Lead pipeline
    "status":              "status",
    "whatsapp_status":     "whatsapp_status",
    "delivery_status":     "delivery_status",
    "generated_message":   "generated_message",
}


# ─── Status do Pipeline ────────────────────────────────────────────────

_STATUS_MAP: Dict[str, str] = {
    "new":              "novo",
    "initial_contact":  "contato_inicial",
    "scheduling":       "agendamento",
    "enriched":         "enriquecido",
    "qualified":        "qualificado",
    "researched":       "pesquisado",
    "message_sent":     "mensagem_enviada",
    "replied":          "respondeu",
    "sold":             "vendido",
    "transferred":      "repassado",
    "discarded":        "descartado",
    # WhatsApp delivery
    "sent":             "enviado",
    "failed":           "falha",
    "invalid_phone":    "telefone_inválido",
    "daily_limit":      "limite_diario",
    "gateway_error":    "erro_gateway",
    "blocked":          "bloqueado",
}


# ─── Score Ranges ─────────────────────────────────────────────────────

_SCORE_RANGES: Dict[str, tuple] = {
    "hot":  (70, 100),
    "warm": (40, 69),
    "cold": (0, 39),
}

_SCORE_CATEGORIES: Dict[str, str] = {
    "hot":  "quente",
    "warm": "morno",
    "cold": "frio",
}


# ─── Fallbacks ─────────────────────────────────────────────────────────

_FALLBACKS: Dict[str, str] = {
    "unknown_establishment":      "Estabelecimento desconhecido",
    "address_not_provided":       "Endereço não informado",
    "phone_not_provided":         "Telefone não informado",
    "website_not_provided":       "Site não informado",
    "instagram_not_provided":     "Instagram não informado",
    "profile_not_available":      "Perfil não disponível",
    "no_weaknesses":             "Nenhum ponto fraco identificado",
    "no_opportunities":          "Nenhuma oportunidade identificada",
    "enrichment_failed":          "Enriquecimento falhou",
    "enrichment_failed_detail":   "Não foi possível gerar dossiê devido a falha no enriquecimento",
    "not_available":              "Não disponível",
    "insufficient_data":          "Informações insuficientes para análise detalhada",
    "opt_out_message":            "\n\nResponda SAIR para não receber mais contatos.",
    "medium_maturity":            "médio",
    "high_maturity":              "alto",
    "low_maturity":               "baixo",
    "default_weakness":           "oportunidades de melhoria no marketing digital",
    "default_area_services":      "serviços locais",
    "default_area_online":        "presença online",
    "default_area_social":        "engajamento em redes sociais",
    "default_weakness_fallback":  "presença digital poderia ser fortalecida",
    # Server errors
    "internal_error":             "Erro interno do servidor",
    "api_key_not_configured":     "API_KEY não configurada. Defina a variável de ambiente API_KEY.",
    "invalid_api_key":            "API key inválida",
    "enrichment_error":           "Erro interno no enriquecimento",
    "scoring_error":              "Erro interno na pontuação",
    "message_error":              "Erro interno na geração de mensagem",
    "research_error":             "Erro interno na pesquisa",
    "crm_error":                  "Erro interno na sincronização CRM",
    "discourse_error":            "Erro interno na extração de discurso",
    "resonance_error":            "Erro interno na análise de ressonância",
    "resonance_lookup_error":     "Erro interno na busca de ressonância",
    "prospect_error":             "Erro interno na geração de prospect",
    "signal_error":               "Erro interno no registro de sinal",
    "rate_limit_exceeded":        "Limite de requisições excedido. Máximo de {limit} requisições por minuto.",
    "not_configured":             "não configurada",
}


# ─── SkepticAgent Markers ─────────────────────────────────────────────

_MARKERS: Dict[str, List[str]] = {
    "generic_phrases": [
        "somos uma empresa", "oferecemos serviços", "melhorar seu negócio",
        "sua empresa", "seu negócio", "nossos serviços",
    ],
    "social_absence": [
        "sem instagram", "sem facebook", "sem linkedin", "sem site",
        "presença digital fraca", "não tem site", "não tem rede social",
    ],
    "emotion_anger":   ["ódio", "nojo", "inferno", "detesto", "raiva", "puto"],
    "emotion_sadness": ["choro", "lágrima", "depressão", "triste", "solidão"],
    "emotion_joy":     ["feliz", "alegre", "contente", "maravilhoso", "incrível"],
    "emotion_fear":    ["medo", "terror", "pânico", "assustado", "preocupado"],
}

_LANGUAGE_MARKERS: Dict[str, List[str]] = {
    "pt": ["o ", "a ", "e ", "de ", "para ", "com ", "do ", "da "],
    "en": ["the ", "and ", "is ", "to ", "of ", "for ", "with "],
}


# ─── Adapter ──────────────────────────────────────────────────────────

class PTBRLocaleAdapter(LocalePort):
    """Implementação completa do LocalePort para português brasileiro."""

    language_code = "pt-BR"
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
            raise PromptNotFoundError(prompt_type, "pt-BR")
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
        return _SCORE_CATEGORIES["cold"]

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

    # ── Parsing ──────────────────────────────────────────────────────

    def get_parser_keywords(self, section: str) -> List[str]:
        _keywords = {
            "profile_summary":  ["resumo", "perfil", "profile"],
            "weaknesses":       ["pontos fracos", "ponto fraco", "weakness", "fraqueza", "fraquezas", "weak"],
            "opportunities":    ["oportunidade", "oportunidades", "opportunity", "opportunities"],
            "digital_maturity": ["maturidade", "digital", "maturity"],
        }
        return _keywords.get(section, [section])

    # ── Utilitários ───────────────────────────────────────────────────

    def get_json_only_suffix(self) -> str:
        return _JSON_ONLY_SUFFIX
