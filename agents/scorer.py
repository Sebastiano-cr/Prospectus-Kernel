"""
Scorer Agent for the Kirin platform.
Uses DeepSeek via ILLMClient port to score leads based on dossiê information.
"""
import asyncio
import json
import re
import logging
from typing import Dict, Any, Optional
from agents.pure_functions import normalize_score, truncate_dossie_for_scoring
from . import runtime
from .llm_client import LLMMessage, LLMError, llm_complete
from src.locale import get_locale, LocalePort
from agents.skeptic import check_agent_output

logger = logging.getLogger(__name__)

# Timeout for scoring (60 seconds as per requirements)
SCORING_TIMEOUT = 60.0
# Max retry attempts for 5xx errors
MAX_RETRIES = 2
# Retry delay in seconds
RETRY_DELAY = 5.0
# Delay for rate limit (429) errors
RATE_LIMIT_DELAY = 60.0


async def score_lead(
    dossie: Dict[str, Any],
    litellm_url: str = None,
    api_key: str = None,
    locale: Optional[LocalePort] = None,
) -> Dict[str, Any]:
    locale = locale or get_locale("pt-BR")

    dossie_trimmed = truncate_dossie_for_scoring(dossie)
    prompt = _build_scoring_prompt(dossie_trimmed, locale)

    messages = [LLMMessage(role="user", content=prompt)]

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = await llm_complete(
                messages=messages,
                model="deepseek-chat",
                temperature=0.3,
                max_tokens=500,
                response_format="json"
            )

            try:
                scoring_data = json.loads(response.content)
            except json.JSONDecodeError:
                scoring_data = _parse_scoring_text(response.content)

            score_result = _validate_and_structure_score(scoring_data, locale)

            scored_lead = dossie.copy()
            scored_lead.update({
                "score": score_result["score"],
                "score_justification": score_result["justification"],
                "faixa": score_result["faixa"],
                "status": locale.get_status_label("qualified"),
            })

            report = check_agent_output("scorer", score_result, {
                "dossier": dossie,
            }, locale)
            if not report.passed:
                scored_lead["skeptic_report"] = report.to_dict()

            await _store_scoring_in_memory(dossie, score_result)

            return scored_lead

        except LLMError as e:
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)
                continue
            return _scoring_fallback(dossie, f"LLM error: {str(e)}", locale)
        except Exception as e:
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)
                continue
            return _scoring_fallback(dossie, f"Scoring error: {str(e)}", locale)

    return _scoring_fallback(dossie, "Unknown scoring error", locale)


def _build_scoring_prompt(dossie: Dict[str, Any], locale: Optional[LocalePort] = None) -> str:
    locale = locale or get_locale("pt-BR")
    profile_summary = dossie.get("resumo_perfil", locale.get_fallback("profile_not_available"))
    weaknesses = dossie.get("pontos_fracos", [])
    opportunities = dossie.get("oportunidades", [])
    digital_maturity = dossie.get("maturidade_digital", locale.get_fallback("medium_maturity"))

    weaknesses_str = "\n".join(f"- {w}" for w in weaknesses) if weaknesses else locale.get_fallback("no_weaknesses")
    opportunities_str = "\n".join(f"- {o}" for o in opportunities) if opportunities else locale.get_fallback("no_opportunities")

    cold = locale.get_score_category(20)
    warm = locale.get_score_category(50)
    hot = locale.get_score_category(80)

    return locale.get_prompt("scorer",
        memory_block="",
        profile_summary=profile_summary,
        weaknesses_str=weaknesses_str,
        opportunities_str=opportunities_str,
        digital_maturity=digital_maturity,
        cold=cold,
        warm=warm,
        hot=hot,
        json_only_suffix=locale.get_json_only_suffix(),
    )


def _parse_scoring_text(text: str) -> Dict[str, Any]:
    result = {
        "score": 50,
        "justification": "Pontuação padrão devido à dificuldade de interpretar a resposta.",
        "faixa": "morno",
    }

    score_match = re.search(r'(\d+)', text)
    if score_match:
        try:
            score = int(score_match.group(1))
            result["score"] = max(0, min(100, score))
        except ValueError:
            pass

    sentences = re.findall(r'[^.!?]+[.!?]', text)
    if sentences:
        justification = ' '.join(sentences[:5]).strip()
        if justification:
            result["justification"] = justification

    return result


def _validate_and_structure_score(data: Dict[str, Any], locale: Optional[LocalePort] = None) -> Dict[str, Any]:
    locale = locale or get_locale("pt-BR")
    raw_score = data.get("score", 50)
    try:
        score = int(raw_score)
    except (ValueError, TypeError):
        score = 50

    score = normalize_score(score)
    justification = str(data.get("justification", locale.get_fallback("profile_not_available")))

    return {
        "score": score,
        "justification": justification,
        "faixa": locale.get_score_category(score),
    }


def _scoring_fallback(dossie: Dict[str, Any], error_reason: str, locale: Optional[LocalePort] = None) -> Dict[str, Any]:
    locale = locale or get_locale("pt-BR")
    score = _calculate_fallback_score(dossie)
    justification = (
        f"Pontuação calculada automaticamente devido a: {error_reason}. "
        f"Análise baseada em maturidade digital ({dossie.get('maturidade_digital', locale.get_fallback('medium_maturity'))}) "
        f"e disponibilidade de informações."
    )
    faixa = locale.get_score_category(score)

    scored_lead = dossie.copy()
    scored_lead.update({
        "score": score,
        "score_justification": justification,
        "faixa": faixa,
        "status": locale.get_status_label("qualified"),
        "scoring_fallback": True,
        "scoring_error": error_reason,
    })

    return scored_lead


def _calculate_fallback_score(dossie: Dict[str, Any]) -> int:
    score = 50

    maturidade = dossie.get("maturidade_digital", "médio")
    if maturidade == "alto":
        score += 20
    elif maturidade == "baixo":
        score -= 20

    pontos_fracos = dossie.get("pontos_fracos", [])
    if len(pontos_fracos) > 3:
        score -= 15
    elif len(pontos_fracos) > 1:
        score -= 10

    oportunidades = dossie.get("oportunidades", [])
    if len(oportunidades) > 3:
        score += 15
    elif len(oportunidades) > 1:
        score += 10

    return max(0, min(100, score))


async def _store_scoring_in_memory(dossie: Dict[str, Any], score_result: Dict[str, Any]) -> None:
    try:
        lead_id = dossie.get("id")
        if not lead_id:
            return
        store = runtime.get_store()
        if store:
            await store.store_lead_memory(lead_id, "scoring", score_result)
    except Exception as e:
        logger.warning(f"Failed to store scoring for lead {lead_id}: {e}")
