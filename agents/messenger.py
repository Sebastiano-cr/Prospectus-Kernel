"""
Messenger Agent for the Kirin platform.
Handles message generation via ILLMClient and sending via IWhatsAppGateway.
"""
import re
import logging
from typing import Dict, Any, Optional
from agents.pure_functions import truncate_message, can_send_message_sync
from . import runtime
from .llm_client import LLMMessage, llm_complete
from .whatsapp_client import send_whatsapp, WhatsAppMessage, WhatsAppResponse
from src.locale import get_locale, LocalePort
from agents.skeptic import check_agent_output

from datetime import datetime

logger = logging.getLogger(__name__)


async def check_daily_limit() -> bool:
    store = runtime.get_store()
    if not store:
        return True
    today = datetime.now().strftime("%Y-%m-%d")
    key = f"kirin:daily_messages:{today}"
    cached = await store.cache_get(key)
    count = cached if isinstance(cached, int) else 0
    return count < DAILY_MESSAGE_LIMIT


async def increment_daily_counter() -> None:
    store = runtime.get_store()
    if not store:
        return
    today = datetime.now().strftime("%Y-%m-%d")
    key = f"kirin:daily_messages:{today}"
    cached = await store.cache_get(key)
    count = (cached if isinstance(cached, int) else 0) + 1
    await store.cache_set(key, count, ttl_seconds=86400)

# Configuration
MESSAGE_MAX_LENGTH = 300
MIN_SEND_INTERVAL = 30  # seconds
MAX_SEND_INTERVAL = 120  # seconds
DAILY_MESSAGE_LIMIT = 200
DAILY_PAUSE_START_HOUR = 9  # 9:00 AM

# Template messages by faixa
MESSAGE_TEMPLATES = {
    "quente": """
Olá {name}! Vi que vocês são especialistas em {area} e têm ótimas avaliações no Google Maps.
Percebi que {weakness} poderia estar limitando seu alcance online.
Temos soluções específicas para negócios como o seu que podem aumentar seus leads em até 40%.
Que tal uma conversa rápida de 15 minutos nesta semana para mostrar como?
""",
    "morno": """
Oi {name}! Nossa análise mostrou que vocês têm um bom fundamento em {area},
mas {weakness} pode estar afetando sua capacidade de atrair novos clientes digitalmente.
Temos ajudado estabelecimentos similares a melhorarem sua presença online com resultados mensuráveis.
Podemos trocar uma ideia sobre como isso funcionaria para vocês?
""",
    "frio": """
Olá {name}! Enquanto pesquisava por {area} na região, encontrei o estabelecimento de vocês.
Notei que {weakness} poderia ser uma oportunidade de melhoria para atrair mais clientes.
Trabalhamos com soluções práticas para negócios locais que desejam fortalecer sua presença digital.
Se fizer sentido, posso compartilhar alguns insights que têm funcionado bem para outros estabelecimentos.
"""
}


async def generate_message(
    lead: Dict[str, Any],
    litellm_url: str = None,
    api_key: str = None,
    locale: Optional[LocalePort] = None,
) -> Optional[str]:
    locale = locale or get_locale("pt-BR")

    if not can_send_message_sync(lead):
        lead["status"] = locale.get_status_label("discarded")
        return None

    score = lead.get("score", 0)
    if score < 20:
        lead["status"] = locale.get_status_label("discarded")
        return None

    faixa = lead.get("faixa")
    if not faixa:
        faixa = locale.get_score_category(score)
        lead["faixa"] = faixa

    prompt = _build_message_prompt(lead, faixa, locale)
    messages = [LLMMessage(role="user", content=prompt)]

    try:
        response = await llm_complete(
            messages=messages,
            model="deepseek-chat",
            temperature=0.7,
            max_tokens=500
        )

        content = response.content.strip()
        message = truncate_message(content, MESSAGE_MAX_LENGTH)
        message += locale.get_fallback("opt_out_message")
        message = truncate_message(message, MESSAGE_MAX_LENGTH)

        report = check_agent_output("messenger", {"message": message}, {
            "lead": lead,
        }, locale)
        if not report.passed:
            lead["skeptic_report"] = report.to_dict()

        await _store_message_in_memory(lead, message)
        return message

    except Exception:
        return _generate_template_message(lead, faixa, locale)


def _build_message_prompt(lead: Dict[str, Any], faixa: str, locale: Optional[LocalePort] = None) -> str:
    locale = locale or get_locale("pt-BR")
    name = lead.get("name", locale.get_fallback("unknown_establishment"))
    dossie = lead.get("dossie", {})
    pontos_fracos = dossie.get("pontos_fracos", [])
    weakness = pontos_fracos[0] if pontos_fracos and pontos_fracos[0] else locale.get_fallback("default_weakness")

    return locale.get_prompt("messenger",
        template_block="",
        name=name,
        faixa_upper=faixa.upper(),
        score=lead.get("score", 0),
        weakness=weakness,
    )


def _generate_template_message(lead: Dict[str, Any], faixa: str, locale: Optional[LocalePort] = None) -> str:
    locale = locale or get_locale("pt-BR")
    name = lead.get("name", locale.get_fallback("unknown_establishment"))
    dossie = lead.get("dossie", {})
    pontos_fracos = dossie.get("pontos_fracos", [])
    if pontos_fracos and pontos_fracos[0]:
        weakness = pontos_fracos[0]
    else:
        weakness = locale.get_fallback("default_weakness_fallback")

    area = "seus serviços"
    if lead.get("website"):
        area = "sua presença online"
    elif lead.get("instagram_username"):
        area = "seus redes sociais"
    elif lead.get("phone"):
        area = "seus contatos"

    template = MESSAGE_TEMPLATES.get(faixa, MESSAGE_TEMPLATES["morno"])

    message = template.format(
        name=name,
        area=area,
        weakness=weakness.lower()
    )

    message = " ".join(message.split())
    message = truncate_message(message, MESSAGE_MAX_LENGTH)
    message += locale.get_fallback("opt_out_message")
    message = truncate_message(message, MESSAGE_MAX_LENGTH)

    return message


async def send_whatsapp_message(
    lead: Dict[str, Any],
    message: str,
    evolution_url: str = None,
    evolution_key: str = None,
    evolution_instance_id: str = None,
    daily_count: Dict[str, int] = None,
    last_send_time: Dict[str, float] = None,
    locale: Optional[LocalePort] = None,
) -> Dict[str, Any]:
    locale = locale or get_locale("pt-BR")
    """Dispatcher: routes to the configured WhatsApp gateway."""
    if not await check_daily_limit():
        logger.warning("Daily message limit reached, skipping send")
        return {
            **lead,
            "whatsapp_status": locale.get_status_label("daily_limit"),
            "delivery_status": locale.get_status_label("blocked"),
        }

    phone_clean = re.sub(r'\D', '', lead.get("phone", ""))
    if not phone_clean or len(phone_clean) < 10:
        return {
            **lead,
            "whatsapp_status": locale.get_status_label("invalid_phone"),
            "delivery_status": locale.get_status_label("failed"),
        }

    msg = WhatsAppMessage(
        phone=phone_clean,
        text=message,
        session="default"
    )

    result: WhatsAppResponse = await send_whatsapp(msg)

    if result.success:
        from datetime import datetime
        await increment_daily_counter()
        return {
            **lead,
            "whatsapp_status": locale.get_status_label("sent"),
            "delivery_status": locale.get_status_label("sent"),
            "message_sent_at": datetime.now().isoformat(),
            "message_id": result.message_id,
            "status": locale.get_status_label("message_sent"),
            "gateway": result.gateway
        }
    else:
        return {
            **lead,
            "whatsapp_status": locale.get_status_label("gateway_error"),
            "delivery_status": locale.get_status_label("failed"),
            "gateway": result.gateway,
            "error_detail": result.error
        }


async def _store_message_in_memory(lead: Dict[str, Any], message: str) -> None:
    try:
        lead_id = lead.get("id") or lead.get("google_maps_id")
        if not lead_id:
            return
        store = runtime.get_store()
        if store:
            await store.store_lead_memory(lead_id, "generated_message", {"message": message})
    except Exception as e:
        logger.warning(f"Failed to store generated message for lead {lead.get('id')}: {e}")


async def _store_sent_message_in_memory(lead: Dict[str, Any], message: str, send_result: Dict[str, Any]) -> None:
    try:
        lead_id = lead.get("id") or lead.get("google_maps_id")
        if not lead_id:
            return
        store = runtime.get_store()
        if store:
            await store.store_lead_memory(lead_id, "sent_message", {
                "message": message,
                "send_result": send_result,
                "timestamp": lead.get("message_sent_at"),
            })
    except Exception as e:
        logger.warning(f"Failed to store sent message for lead {lead.get('id')}: {e}")
