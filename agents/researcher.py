"""
Researcher Agent for the Prospectus-Kernel platform.
Uses Moonshot Kimi K2 via ILLMClient port to research leads and find sources.
"""
import asyncio
import json
from typing import Dict, Any, Optional
import os
import logging
from . import runtime
from .llm_client import LLMMessage, LLMError, llm_complete
from src.locale import get_locale, LocalePort
from agents.skeptic import check_agent_output

logger = logging.getLogger(__name__)

# Configuration
RESEARCH_TIMEOUT = 120.0  # 2 minutes as per requirements
MAX_RETRIES = 2
RETRY_DELAY = 5.0
KIMI_MAX_PARALLEL = int(os.getenv("KIMI_MAX_PARALLEL", "3"))


async def research_lead(
    lead: Dict[str, Any],
    litellm_url: str = None,
    api_key: str = None,
    locale: Optional[LocalePort] = None,
) -> Dict[str, Any]:
    locale = locale or get_locale("pt-BR")
    prompt = _build_research_prompt(lead, locale)
    messages = [LLMMessage(role="user", content=prompt)]

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = await llm_complete(
                messages=messages,
                model="moonshot-v1-128k",
                temperature=0.3,
                max_tokens=1000,
                response_format="json"
            )

            try:
                research_data = json.loads(response.content)
            except json.JSONDecodeError:
                research_data = {"fontes_consultadas": [], "error": "parse_failed"}

            if "fontes_consultadas" not in research_data:
                research_data["fontes_consultadas"] = []

            if not isinstance(research_data["fontes_consultadas"], list):
                research_data["fontes_consultadas"] = []

            researched_lead = lead.copy()
            researched_lead.update({
                "pesquisa": research_data,
                "status": locale.get_status_label("researched"),
            })

            report = check_agent_output("researcher", research_data, {
                "lead": lead,
            }, locale)
            if not report.passed:
                researched_lead["skeptic_report"] = report.to_dict()

            await _store_research_in_memory(lead, research_data)

            return researched_lead

        except LLMError as e:
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)
                continue
            return _mark_research_failed(lead, f"LLM error: {str(e)}", locale)
        except Exception as e:
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)
                continue
            return _mark_research_failed(lead, f"Research error: {str(e)}", locale)

    return _mark_research_failed(lead, "Unknown research error", locale)


def _build_research_prompt(lead: Dict[str, Any], locale: Optional[LocalePort] = None) -> str:
    locale = locale or get_locale("pt-BR")
    name = lead.get("name", locale.get_fallback("unknown_establishment"))
    address = lead.get("address", locale.get_fallback("address_not_provided"))
    dossie = lead.get("dossie", {})
    profile_summary = dossie.get("resumo_perfil", locale.get_fallback("profile_not_available"))
    weaknesses = dossie.get("pontos_fracos", [])
    opportunities = dossie.get("oportunidades", [])
    field_sources = locale.get_field_name("sources_consulted")

    weaknesses_str = ", ".join(weaknesses) if weaknesses else locale.get_fallback("no_weaknesses")
    opportunities_str = ", ".join(opportunities) if opportunities else locale.get_fallback("no_opportunities")

    return locale.get_prompt("researcher",
        name=name,
        address=address,
        profile_summary=profile_summary,
        weaknesses_str=weaknesses_str,
        opportunities_str=opportunities_str,
        field_sources=field_sources,
        json_only_suffix=locale.get_json_only_suffix(),
    )


def _mark_research_failed(
    lead: Dict[str, Any],
    error_reason: str,
    locale: Optional[LocalePort] = None,
) -> Dict[str, Any]:
    locale = locale or get_locale("pt-BR")
    failed_lead = lead.copy()
    failed_lead.update({
        "pesquisa": {
            "fontes_consultadas": [],
            "error": error_reason,
        },
        "status": locale.get_status_label("researched"),
        "research_failed": True,
        "research_error": error_reason,
    })

    return failed_lead


async def _store_research_in_memory(lead: Dict[str, Any], research_data: Dict[str, Any]) -> None:
    try:
        lead_id = lead.get("id") or lead.get("google_maps_id")
        if not lead_id:
            logger.debug("No lead identifier found, skipping memory storage for research")
            return

        store = runtime.get_store()
        if store:
            await store.store_lead_memory(lead_id, "pesquisa", research_data)

    except Exception as e:
        logger.warning(f"Failed to store research in memory for lead {lead.get('id')}: {e}")
