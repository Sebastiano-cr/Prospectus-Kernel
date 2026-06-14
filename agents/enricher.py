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
from .llm_client import LLMMessage, LLMError, llm_complete
from src.locale import get_locale, LocalePort
from agents.skeptic import check_agent_output

logger = logging.getLogger(__name__)

# Timeout for enrichment (60 seconds as per requirements)
ENRICHMENT_TIMEOUT = 60.0
# Max retry attempts
MAX_RETRIES = 2
# Retry delay in seconds
RETRY_DELAY = 5.0


async def enrich_lead(
    lead: Dict[str, Any],
    litellm_url: str = None,
    api_key: str = None,
    locale: Optional[LocalePort] = None,
) -> Dict[str, Any]:
    locale = locale or get_locale("pt-BR")
    prompt = _build_enrichment_prompt(lead, locale)

    messages = [LLMMessage(role="user", content=prompt)]

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = await llm_complete(
                messages=messages,
                model="qwen-vl-max",
                temperature=0.3,
                max_tokens=1000,
                response_format="json"
            )

            try:
                enrichment_data = json.loads(response.content)
            except json.JSONDecodeError:
                enrichment_data = _parse_enrichment_text(response.content, locale)

            dossie = _validate_and_structure_dossie(enrichment_data)

            enriched_lead = lead.copy()
            enriched_lead.update({
                "dossie": dossie,
                "enrichment_success": True,
                "enrichment_failed": False,
                "status": "enriquecido"
            })

            report = check_agent_output("enricher", {"dossie": dossie}, {
                "lead": lead,
                "has_social_media": bool(lead.get("instagram_username") or lead.get("website")),
                "dossier": dossie,
            }, locale)
            if not report.passed:
                enriched_lead["skeptic_report"] = report.to_dict()

            await _store_enrichment_in_memory(lead, dossie)

            return enriched_lead

        except LLMError as e:
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)
                continue
            return _mark_enrichment_failed(lead, f"LLM error: {str(e)}", locale)
        except Exception as e:
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)
                continue
            return _mark_enrichment_failed(lead, f"Enrichment error: {str(e)}", locale)

    return _mark_enrichment_failed(lead, "Unknown enrichment error", locale)


def _build_enrichment_prompt(lead: Dict[str, Any], locale: LocalePort) -> str:
    context = dict(lead)
    context.setdefault("name", locale.get_fallback("unknown_establishment"))
    context.setdefault("address", locale.get_fallback("address_not_provided"))
    context.setdefault("phone", locale.get_fallback("phone_not_provided"))
    context.setdefault("website", locale.get_fallback("website_not_provided"))
    context.setdefault("instagram_username", locale.get_fallback("instagram_not_provided"))
    context.setdefault("google_maps_data", {})
    context.setdefault("instagram_data", {})

    context["google_maps_data"] = json.dumps(context["google_maps_data"], indent=2) if context.get("google_maps_data") else locale.get_fallback("not_available")
    context["instagram_data"] = json.dumps(context["instagram_data"], indent=2) if context.get("instagram_data") else locale.get_fallback("not_available")

    field_names = locale.get_field_names([
        "profile_summary", "weaknesses", "opportunities", "digital_maturity",
    ])
    context["field_profile_summary"] = field_names["profile_summary"]
    context["field_weaknesses"] = field_names["weaknesses"]
    context["field_opportunities"] = field_names["opportunities"]
    context["field_digital_maturity"] = field_names["digital_maturity"]
    context["maturity_high"] = locale.get_fallback("high_maturity")
    context["maturity_medium"] = locale.get_fallback("medium_maturity")
    context["maturity_low"] = locale.get_fallback("low_maturity")
    context["json_only_suffix"] = locale.get_json_only_suffix()

    return locale.get_prompt("enricher", **context)


def _parse_enrichment_text(text: str, locale: Optional[LocalePort] = None) -> Dict[str, Any]:
    locale = locale or get_locale("pt-BR")
    fn = locale.get_field_name
    pf = locale.get_parser_keywords

    profile_key = fn("profile_summary")
    weaknesses_key = fn("weaknesses")
    opportunities_key = fn("opportunities")
    maturity_key = fn("digital_maturity")

    result = {
        profile_key: "",
        weaknesses_key: [],
        opportunities_key: [],
        maturity_key: "médio",
    }

    def _extract_after_colon(line: str) -> Optional[str]:
        if ":" in line:
            after = line.split(":", 1)[1].strip()
            return after if after else None
        return None

    def _add_to_profile(content: str) -> None:
        if result[profile_key]:
            result[profile_key] += " " + content
        else:
            result[profile_key] = content

    def _add_to_list(lst_key: str, item: str) -> None:
        if item.startswith(("-", "•", "*")):
            item = item[1:].strip()
        elif item[0].isdigit() and ". " in item[:5]:
            item = item.split(". ", 1)[1].strip()
        if item:
            result[lst_key].append(item)

    lines = text.split('\n')
    current_section = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        lower_line = line.lower()
        colon_content = _extract_after_colon(line)

        if any(k in lower_line for k in pf("profile_summary")):
            current_section = profile_key
            if colon_content:
                _add_to_profile(colon_content)
            continue
        elif any(k in lower_line for k in pf("weaknesses")):
            current_section = weaknesses_key
            if colon_content:
                _add_to_list(weaknesses_key, colon_content)
            continue
        elif any(k in lower_line for k in pf("opportunities")):
            current_section = opportunities_key
            if colon_content:
                _add_to_list(opportunities_key, colon_content)
            continue
        elif any(k in lower_line for k in pf("digital_maturity")):
            current_section = maturity_key
            if colon_content:
                cc = colon_content.lower()
                if locale.get_fallback("low_maturity") in cc:
                    result[maturity_key] = "baixo"
                elif locale.get_fallback("high_maturity") in cc:
                    result[maturity_key] = "alto"
                else:
                    result[maturity_key] = "médio"
            continue

        if current_section == profile_key:
            _add_to_profile(line)
        elif current_section == weaknesses_key:
            _add_to_list(weaknesses_key, line)
        elif current_section == opportunities_key:
            _add_to_list(opportunities_key, line)
        elif current_section == maturity_key:
            if locale.get_fallback("low_maturity") in lower_line:
                result[maturity_key] = "baixo"
            elif locale.get_fallback("high_maturity") in lower_line:
                result[maturity_key] = "alto"
            else:
                result[maturity_key] = "médio"

    if not result[weaknesses_key]:
        result[weaknesses_key] = [locale.get_fallback("insufficient_data")]

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


def _mark_enrichment_failed(lead: Dict[str, Any], error_reason: str, locale: Optional[LocalePort] = None) -> Dict[str, Any]:
    locale = locale or get_locale("pt-BR")
    failed_lead = lead.copy()
    fn = locale.get_field_name
    failed_lead.update({
        "dossie": {
            fn("profile_summary"): locale.get_fallback("enrichment_failed"),
            fn("weaknesses"): [locale.get_fallback("enrichment_failed_detail")],
            fn("opportunities"): [],
            fn("digital_maturity"): locale.get_fallback("low_maturity"),
        },
        "enrichment_success": False,
        "enrichment_failed": True,
        "enrichment_error": error_reason,
        "status": "enriquecido"
    })

    return failed_lead


async def _store_enrichment_in_memory(lead: Dict[str, Any], dossie: Dict[str, Any]) -> None:
    try:
        lead_id = lead.get("id") or lead.get("google_maps_id")
        if not lead_id:
            return
        store = runtime.get_store()
        if store:
            await store.store_lead_memory(lead_id, "dossie", dossie)
    except Exception as e:
        logger.warning(f"Failed to store enrichment for lead {lead.get('id')}: {e}")
