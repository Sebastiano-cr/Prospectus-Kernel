"""
Enricher Agent for the Kirin platform.
Uses Qwen VL Max via ILLMClient port to enrich lead data with dossiê information.
"""
import asyncio
import json
from typing import Dict, Any, Optional
import logging
from .pure_functions import truncate_message
from . import runtime
from .factory import ServiceFactory
from .ports.llm_client import LLMMessage, LLMError

logger = logging.getLogger(__name__)

# Timeout for enrichment (60 seconds as per requirements)
ENRICHMENT_TIMEOUT = 60.0
# Max retry attempts
MAX_RETRIES = 2
# Retry delay in seconds
RETRY_DELAY = 5.0


async def enrich_lead(lead: Dict[str, Any], litellm_url: str = None, api_key: str = None) -> Dict[str, Any]:
    """
    Enrich lead data using Qwen VL Max via ILLMClient port.

    Args:
        lead: Lead dictionary containing basic information
        litellm_url: Deprecated -- kept for backward compatibility
        api_key: Deprecated -- kept for backward compatibility

    Returns:
        Enriched lead dictionary with dossiê information
    """
    llm = ServiceFactory.get_llm_client()
    prompt = _build_enrichment_prompt(lead)

    messages = [LLMMessage(role="user", content=prompt)]

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = await llm.complete(
                messages=messages,
                model="qwen-vl-max",
                temperature=0.3,
                max_tokens=1000,
                response_format="json"
            )

            try:
                enrichment_data = json.loads(response.content)
            except json.JSONDecodeError:
                enrichment_data = _parse_enrichment_text(response.content)

            dossie = _validate_and_structure_dossie(enrichment_data)

            enriched_lead = lead.copy()
            enriched_lead.update({
                "dossie": dossie,
                "enrichment_success": True,
                "enrichment_failed": False,
                "status": "enriquecido"
            })

            await _store_enrichment_in_memory(lead, dossie)

            return enriched_lead

        except LLMError as e:
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)
                continue
            return _mark_enrichment_failed(lead, f"LLM error: {str(e)}")
        except Exception as e:
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)
                continue
            return _mark_enrichment_failed(lead, f"Enrichment error: {str(e)}")

    return _mark_enrichment_failed(lead, "Unknown enrichment error")


def _build_enrichment_prompt(lead: Dict[str, Any]) -> str:
    """
    Build prompt for the enrichment model.
    """
    name = lead.get("name", "Estabelecimento desconhecido")
    address = lead.get("address", "Endereço não informado")
    phone = lead.get("phone", "Telefone não informado")
    website = lead.get("website", "Site não informado")
    instagram_username = lead.get("instagram_username", "Instagram não informado")
    google_maps_data = lead.get("google_maps_data", {})
    instagram_data = lead.get("instagram_data", {})

    prompt = f"""
    Você é um especialista em inteligência comercial. Analise as informações do seguinte estabelecimento e gere um dossiê completo:

    ESTABELECIMENTO:
    - Nome: {name}
    - Endereço: {address}
    - Telefone: {phone}
    - Website: {website}
    - Instagram: {instagram_username}

    DADOS DO GOOGLE MAPS:
    {json.dumps(google_maps_data, indent=2) if google_maps_data else "Não disponível"}

    DADOS DO INSTAGRAM:
    {json.dumps(instagram_data, indent=2) if instagram_data else "Não disponível"}

    Com base nessas informações, gere um dossiê em formato JSON com os seguintes campos:
    - resumo_perfil: Um parágrafo resumindo o perfil do estabelecimento
    - pontos_fracos: Lista de pontos fracos (mínimo 1 item)
    - oportunidades: Lista de oportunidades de melhoria
    - maturidade_digital: Avaliação da maturidade digital ("alto", "médio" ou "baixo")

    Se o estabelecimento não tiver website nem Instagram, defina maturidade_digital como "baixo".

    Responda APENAS com o JSON válido, sem texto adicional.
    """

    return prompt.strip()


def _parse_enrichment_text(text: str) -> Dict[str, Any]:
    """
    Parse enrichment information from text response when JSON is not valid.
    """
    result = {
        "resumo_perfil": "",
        "pontos_fracos": [],
        "oportunidades": [],
        "maturidade_digital": "médio"
    }

    lines = text.split('\n')
    current_section = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        lower_line = line.lower()

        if "resumo" in lower_line or "perfil" in lower_line:
            current_section = "resumo_perfil"
            continue
        elif "ponto fraco" in lower_line or "weakness" in lower_line or "fraqueza" in lower_line:
            current_section = "pontos_fracos"
            continue
        elif "oportunidade" in lower_line or "opportunity" in lower_line:
            current_section = "oportunidades"
            continue
        elif "maturidade" in lower_line or "digital" in lower_line:
            current_section = "maturidade_digital"
            continue

        if current_section == "resumo_perfil":
            if result["resumo_perfil"]:
                result["resumo_perfil"] += " " + line
            else:
                result["resumo_perfil"] = line
        elif current_section == "pontos_fracos":
            if line.startswith('-') or line.startswith('•') or line.startswith('*'):
                item = line[1:].strip()
                if item:
                    result["pontos_fracos"].append(item)
            elif line[0].isdigit() and '. ' in line[:5]:
                item = line.split('. ', 1)[1].strip()
                if item:
                    result["pontos_fracos"].append(item)
            else:
                result["pontos_fracos"].append(line)
        elif current_section == "oportunidades":
            if line.startswith('-') or line.startswith('•') or line.startswith('*'):
                item = line[1:].strip()
                if item:
                    result["oportunidades"].append(item)
            elif line[0].isdigit() and '. ' in line[:5]:
                item = line.split('. ', 1)[1].strip()
                if item:
                    result["oportunidades"].append(item)
            else:
                result["oportunidades"].append(line)
        elif current_section == "maturidade_digital":
            if "alto" in lower_line:
                result["maturidade_digital"] = "alto"
            elif "baixo" in lower_line:
                result["maturidade_digital"] = "baixo"
            else:
                result["maturidade_digital"] = "médio"

    if not result["pontos_fracos"]:
        result["pontos_fracos"] = ["Informações insuficientes para análise detalhada"]

    return result


def _validate_and_structure_dossie(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and structure the dossiê data.
    """
    dossie = {
        "resumo_perfil": str(data.get("resumo_perfil", "")),
        "pontos_fracos": list(data.get("pontos_fracos", [])) if isinstance(data.get("pontos_fracos"), list) else [str(data.get("pontos_fracos", ""))],
        "oportunidades": list(data.get("oportunidades", [])) if isinstance(data.get("oportunidades"), list) else [str(data.get("oportunidades", ""))],
        "maturidade_digital": str(data.get("maturidade_digital", "médio")).lower()
    }

    if dossie["maturidade_digital"] not in ["alto", "médio", "baixo"]:
        dossie["maturidade_digital"] = "médio"

    if not dossie["pontos_fracos"]:
        dossie["pontos_fracos"] = ["Não foram identificados pontos fracos específicos"]

    dossie["resumo_perfil"] = truncate_message(dossie["resumo_perfil"], 500)

    return dossie


def _mark_enrichment_failed(lead: Dict[str, Any], error_reason: str) -> Dict[str, Any]:
    """
    Mark lead as enrichment failed.
    """
    failed_lead = lead.copy()
    failed_lead.update({
        "dossie": {
            "resumo_perfil": "Enriquecimento falhou",
            "pontos_fracos": ["Não foi possível gerar dossiê devido a falha no enriquecimento"],
            "oportunidades": [],
            "maturidade_digital": "baixo"
        },
        "enrichment_success": False,
        "enrichment_failed": True,
        "enrichment_error": error_reason,
        "status": "enriquecido"
    })

    return failed_lead


async def _store_enrichment_in_memory(lead: Dict[str, Any], dossie: Dict[str, Any]) -> None:
    """
    Store enrichment result in memory managers if available.
    """
    try:
        lead_id = lead.get("id") or lead.get("google_maps_id")
        if not lead_id:
            logger.debug("No lead identifier found, skipping memory storage for enrichment")
            return

        postgres_mem = runtime.get_postgres_memory()
        qdrant_mem = runtime.get_qdrant_memory()

        if postgres_mem:
            await postgres_mem.store_lead_memory(lead_id, "dossie", dossie)

    except Exception as e:
        logger.warning(f"Failed to store enrichment in memory for lead {lead.get('id')}: {e}")
