"""
Scorer Agent for the Kirin platform.
Uses DeepSeek via ILLMClient port to score leads based on dossiê information.
"""
import asyncio
import json
import re
import logging
from typing import Dict, Any, Optional
from agents.pure_functions import normalize_score, classify_faixa, truncate_dossie_for_scoring
from . import runtime
from .factory import ServiceFactory
from .ports.llm_client import LLMMessage, LLMError

logger = logging.getLogger(__name__)

# Timeout for scoring (60 seconds as per requirements)
SCORING_TIMEOUT = 60.0
# Max retry attempts for 5xx errors
MAX_RETRIES = 2
# Retry delay in seconds
RETRY_DELAY = 5.0
# Delay for rate limit (429) errors
RATE_LIMIT_DELAY = 60.0


async def score_lead(dossie: Dict[str, Any], litellm_url: str = None, api_key: str = None) -> Dict[str, Any]:
    """
    Score lead using DeepSeek via ILLMClient port.
    """
    llm = ServiceFactory.get_llm_client()

    memory_context = ""
    try:
        from integrations.agentmemory_client import smart_search, observe
        query = f"{dossie.get('resumo_perfil', '')} {dossie.get('maturidade_digital', '')}"
        results = await smart_search(query, limit=3)
        if results:
            snippets = [r.get("content", r.get("observation", "")) for r in results if r]
            memory_context = "\n".join(f"- {s}" for s in snippets if s)
    except Exception:
        pass

    dossie_trimmed = truncate_dossie_for_scoring(dossie)
    prompt = _build_scoring_prompt(dossie_trimmed, memory_context)

    messages = [LLMMessage(role="user", content=prompt)]

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = await llm.complete(
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

            score_result = _validate_and_structure_score(scoring_data)

            scored_lead = dossie.copy()
            scored_lead.update({
                "score": score_result["score"],
                "score_justification": score_result["justification"],
                "faixa": score_result["faixa"],
                "status": "qualificado"
            })

            try:
                await observe(
                    dossie.get("id", "unknown"),
                    {
                        "agent": "scorer",
                        "resumo": dossie.get("resumo_perfil", "")[:200],
                        "maturidade_digital": dossie.get("maturidade_digital"),
                        "score": score_result["score"],
                        "faixa": score_result["faixa"],
                    }
                )
            except Exception:
                pass

            await _store_scoring_in_memory(dossie, score_result)

            return scored_lead

        except LLMError as e:
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)
                continue
            return _scoring_fallback(dossie, f"LLM error: {str(e)}")
        except Exception as e:
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)
                continue
            return _scoring_fallback(dossie, f"Scoring error: {str(e)}")

    return _scoring_fallback(dossie, "Unknown scoring error")


def _build_scoring_prompt(dossie: Dict[str, Any], memory_context: str = "") -> str:
    """Build prompt for the scoring model."""
    resumo_perfil = dossie.get("resumo_perfil", "Perfil não disponível")
    pontos_fracos = dossie.get("pontos_fracos", [])
    oportunidades = dossie.get("oportunidades", [])
    maturidade_digital = dossie.get("maturidade_digital", "médio")

    pontos_fracos_str = "\n".join([f"- {p}" for p in pontos_fracos]) if pontos_fracos else "Nenhum ponto fraco identificado"
    oportunidades_str = "\n".join([f"- {o}" for o in oportunidades]) if oportunidades else "Nenhuma oportunidade identificada"

    memory_block = ""
    if memory_context:
        memory_block = f"""
    CONTEXTO DE LEADS SIMILARES PROCESSADOS ANTERIORMENTE:
{memory_context}
    (Use como referência para calibrar o score, mas avalie o dossiê atual de forma independente.)
"""

    prompt = f"""
    Você é um especialista em scoring de leads comerciais. Avalie o dossiê do seguinte estabelecimento e atribua uma pontuação de 0 a 100:
{memory_block}
    DOSSiÊ:
    - Resumo do perfil: {resumo_perfil}
    - Pontos fracos:
    {pontos_fracos_str}
    - Oportunidades:
    {oportunidades_str}
    - Maturidade digital: {maturidade_digital}

    Com base nessas informações, attribue uma pontuação de 0 a 100 onde:
    - 0-39: Lead frio (baixa probabilidade de conversão)
    - 40-69: Lead morno (média probabilidade de conversão)
    - 70-100: Lead quente (alta probabilidade de conversão)

    Forneça sua resposta em formato JSON com os seguintes campos:
    - score: Número inteiro entre 0 e 100
    - justification: Justificativa da pontuação com 3-5 frases
    - faixa: Classificação em "frio", "morno" ou "quente" (baseada na pontuação)

    Responda APENAS com o JSON válido, sem texto adicional.
    """

    return prompt.strip()


def _parse_scoring_text(text: str) -> Dict[str, Any]:
    """
    Parse scoring information from text response when JSON is not valid.
    """
    result = {
        "score": 50,
        "justification": "Pontuação padrão devido à dificuldade de interpretar a resposta.",
        "faixa": "morno"
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

    result["faixa"] = classify_faixa(result["score"])

    return result


def _validate_and_structure_score(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and structure the score data.
    """
    raw_score = data.get("score", 50)
    try:
        score = int(raw_score)
    except (ValueError, TypeError):
        score = 50

    score = normalize_score(score)
    justification = str(data.get("justification", "Justificativa não fornecida."))
    faixa = classify_faixa(score)

    provided_faixa = str(data.get("faixa", "")).lower()
    if provided_faixa in ["frio", "morno", "quente"]:
        faixa = provided_faixa
    else:
        faixa = classify_faixa(score)

    return {
        "score": score,
        "justification": justification,
        "faixa": faixa
    }


def _scoring_fallback(dossie: Dict[str, Any], error_reason: str) -> Dict[str, Any]:
    """
    Provide fallback scoring when LLM is unavailable.
    """
    score = _calculate_fallback_score(dossie)
    justification = f"Pontuação calculada automaticamente devido a: {error_reason}. "
    justification += f"Análise baseada em maturidade digital ({dossie.get('maturidade_digital', 'médio')}) e disponibilidade de informações."
    faixa = classify_faixa(score)

    scored_lead = dossie.copy()
    scored_lead.update({
        "score": score,
        "score_justification": justification,
        "faixa": faixa,
        "status": "qualificado",
        "scoring_fallback": True,
        "scoring_error": error_reason
    })

    return scored_lead


def _calculate_fallback_score(dossie: Dict[str, Any]) -> int:
    """
    Calculate a fallback score based on dossiê characteristics.
    """
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
    """
    Store scoring result in memory managers if available.
    """
    try:
        lead_id = dossie.get("id")
        if not lead_id:
            logger.debug("No lead identifier found in dossie, skipping memory storage for scoring")
            return

        postgres_mem = runtime.get_postgres_memory()

        if postgres_mem:
            await postgres_mem.store_lead_memory(lead_id, "scoring", score_result)

    except Exception as e:
        logger.warning(f"Failed to store scoring in memory for lead {lead_id}: {e}")
