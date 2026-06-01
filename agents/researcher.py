"""
Researcher Agent for the Kirin platform.
Uses Moonshot Kimi K2 via ILLMClient port to research leads and find sources.
"""
import asyncio
import json
from typing import Dict, Any, List, Optional
import os
import logging
from . import runtime
from .factory import ServiceFactory
from .ports.llm_client import LLMMessage, LLMError

logger = logging.getLogger(__name__)

# Configuration
RESEARCH_TIMEOUT = 120.0  # 2 minutes as per requirements
MAX_RETRIES = 2
RETRY_DELAY = 5.0
KIMI_MAX_PARALLEL = int(os.getenv("KIMI_MAX_PARALLEL", "3"))


async def research_lead(lead: Dict[str, Any], litellm_url: str = None, api_key: str = None) -> Dict[str, Any]:
    """
    Research lead using Moonshot Kimi K2 via ILLMClient port.
    """
    llm = ServiceFactory.get_llm_client()
    prompt = _build_research_prompt(lead)
    messages = [LLMMessage(role="user", content=prompt)]

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = await llm.complete(
                messages=messages,
                model="moonshot-v1-128k",
                temperature=0.3,
                max_tokens=1000,
                response_format="json"
            )

            try:
                research_data = json.loads(response.content)
            except json.JSONDecodeError:
                research_data = {
                    "fontes_consultadas": [],
                    "error": "parse_failed"
                }

            if "fontes_consultadas" not in research_data:
                research_data["fontes_consultadas"] = []

            if not isinstance(research_data["fontes_consultadas"], list):
                research_data["fontes_consultadas"] = []

            researched_lead = lead.copy()
            researched_lead.update({
                "pesquisa": research_data,
                "status": "pesquisado"
            })

            await _store_research_in_memory(lead, research_data)

            return researched_lead

        except LLMError as e:
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)
                continue
            return _mark_research_failed(lead, f"LLM error: {str(e)}")
        except Exception as e:
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)
                continue
            return _mark_research_failed(lead, f"Research error: {str(e)}")

    return _mark_research_failed(lead, "Unknown research error")


def _build_research_prompt(lead: Dict[str, Any]) -> str:
    """
    Build prompt for the research model.
    """
    name = lead.get("name", "Estabelecimento desconhecido")
    address = lead.get("address", "Endereço não informado")
    dossie = lead.get("dossie", {})
    resumo_perfil = dossie.get("resumo_perfil", "Perfil não disponível")
    pontos_fracos = dossie.get("pontos_fracos", [])
    oportunidades = dossie.get("oportunidades", [])

    prompt = f"""
    Você é um pesquisador especializado em inteligência de mercado para negócios locais.
    Pesquise informações adicionais sobre o seguinte estabelecimento para complementar o dossiê existente:

    ESTABELECIMENTO:
    - Nome: {name}
    - Endereço: {address}

    DOSSiÊ EXISTENTE:
    - Resumo do perfil: {resumo_perfil}
    - Pontos fracos: {', '.join(pontos_fracos) if pontos_fracos else 'Nenhum identificado'}
    - Oportunidades: {', '.join(oportunidades) if oportunidades else 'Nenhuma identificada'}

    Sua tarefa é encontrar fontes externas confiáveis que possam validar ou complementar estas informações.
    Pesquise por:
    - Notícias recentes sobre o estabelecimento
    - Menções em blogs ou sites especializados
    - Informações sobre os proprietários ou gestores
    - Dados sobre desempenho financeiro ou de mercado (se disponível)
    - Avaliações em sites especializados além do Google Maps

    Retorne seus resultados em formato JSON com o seguinte campo obrigatório:
    - fontes_consultadas: Lista de fontes consultadas (pode estar vazia se nada for encontrado)
      Cada fonte deve ser um objeto com:
      - tipo: Tipo da fonte (ex: "noticia", "blog", "rede_social", "site_especializado")
      - titulo: Título ou descrição da fonte
      - url: URL da fonte (se disponível)
      - relevancia: Breve descrição da relevância da fonte para o estabelecimento
      - data_consulta: Data da consulta no formato ISO (YYYY-MM-DD)

    Se não conseguir encontrar fontes ou ocorrer erro no parsing, retorne:
    {{"fontes_consultadas": [], "error": "parse_failed"}}

    Responda APENAS com o JSON válido, sem texto adicional.
    """

    return prompt.strip()


def _mark_research_failed(lead: Dict[str, Any], error_reason: str) -> Dict[str, Any]:
    """
    Mark lead as research failed.
    """
    failed_lead = lead.copy()
    failed_lead.update({
        "pesquisa": {
            "fontes_consultadas": [],
            "error": error_reason
        },
        "status": "pesquisado",
        "research_failed": True,
        "research_error": error_reason
    })

    return failed_lead


async def _store_research_in_memory(lead: Dict[str, Any], research_data: Dict[str, Any]) -> None:
    """
    Store research result in memory managers if available.
    """
    try:
        lead_id = lead.get("id") or lead.get("google_maps_id")
        if not lead_id:
            logger.debug("No lead identifier found, skipping memory storage for research")
            return

        postgres_mem = runtime.get_postgres_memory()

        if postgres_mem:
            await postgres_mem.store_lead_memory(lead_id, "pesquisa", research_data)

    except Exception as e:
        logger.warning(f"Failed to store research in memory for lead {lead.get('id')}: {e}")
