"""
Messenger Agent for the Kirin platform.
Handles message generation via ILLMClient and sending via IWhatsAppGateway.
"""
import asyncio
import json
import random
import re
import time
import logging
import os
from typing import Dict, Any, Optional
from agents.pure_functions import truncate_message, can_send_message_sync
from . import runtime
from .factory import ServiceFactory
from .ports.llm_client import LLMMessage, LLMError
from .ports.whatsapp_gateway import WhatsAppMessage, WhatsAppResponse

from datetime import datetime

logger = logging.getLogger(__name__)


async def check_daily_limit() -> bool:
    """Check if daily message limit has been reached."""
    redis_mem = ServiceFactory.get_redis_memory()
    if not redis_mem or not redis_mem._redis:
        return True  # If Redis not available, allow
    today = datetime.now().strftime("%Y-%m-%d")
    key = f"kirin:daily_messages:{today}"
    count = await redis_mem._redis.get(key)
    return int(count or 0) < DAILY_MESSAGE_LIMIT


async def increment_daily_counter() -> None:
    """Increment daily message counter in Redis."""
    redis_mem = ServiceFactory.get_redis_memory()
    if not redis_mem or not redis_mem._redis:
        return
    today = datetime.now().strftime("%Y-%m-%d")
    key = f"kirin:daily_messages:{today}"
    pipe = redis_mem._redis.pipeline()
    pipe.incr(key)
    pipe.expire(key, 86400)
    await pipe.execute()

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


async def generate_message(lead: Dict[str, Any], litellm_url: str = None, api_key: str = None) -> Optional[str]:
    """
    Generate a WhatsApp message for a lead using DeepSeek via ILLMClient port.
    """
    llm = ServiceFactory.get_llm_client()

    if not can_send_message_sync(lead):
        lead["status"] = "descartado"
        return None

    score = lead.get("score", 0)
    if score < 20:
        lead["status"] = "descartado"
        return None

    faixa = lead.get("faixa")
    if not faixa:
        from agents.pure_functions import classify_faixa
        faixa = classify_faixa(score)
        lead["faixa"] = faixa

    memory_template_hint = ""
    try:
        from integrations.agentmemory_client import smart_search
        dossie = lead.get("dossie", {})
        query = f"template mensagem whatsapp {faixa} {dossie.get('resumo_perfil', '')[:100]} reply"
        results = await smart_search(query, limit=2)
        if results:
            snippets = [r.get("content", r.get("observation", "")) for r in results if r]
            memory_template_hint = "\n".join(s for s in snippets if s)
    except Exception:
        pass

    prompt = _build_message_prompt(lead, faixa, memory_template_hint)
    messages = [LLMMessage(role="user", content=prompt)]

    try:
        response = await llm.complete(
            messages=messages,
            model="deepseek-chat",
            temperature=0.7,
            max_tokens=500
        )

        content = response.content.strip()
        message = truncate_message(content, MESSAGE_MAX_LENGTH)
        message += "\n\nResponda SAIR para não receber mais contatos."
        message = truncate_message(message, MESSAGE_MAX_LENGTH)

        try:
            from integrations.agentmemory_client import observe as _observe
            await _observe(lead.get("id", "unknown"), {
                "agent": "messenger",
                "faixa": lead.get("faixa"),
                "score": lead.get("score"),
                "message_preview": message[:100],
                "source": "llm_new",
                "has_memory_hint": bool(memory_template_hint),
            })
        except Exception:
            pass

        await _store_message_in_memory(lead, message)
        return message

    except Exception:
        return _generate_template_message(lead, faixa)


def _build_message_prompt(lead: Dict[str, Any], faixa: str, memory_template_hint: str = "") -> str:
    """Build prompt for message generation."""
    name = lead.get("name", "Estabelecimento")
    dossie = lead.get("dossie", {})
    pontos_fracos = dossie.get("pontos_fracos", [])
    weakness = pontos_fracos[0] if pontos_fracos and pontos_fracos[0] else "oportunidades de melhoria no marketing digital"

    area = "serviços locais"
    if lead.get("website"):
        area = "presença online"
    elif lead.get("instagram_username"):
        area = "engajamento em redes sociais"

    template_block = ""
    if memory_template_hint:
        template_block = f"""
    REFERÊNCIA DE MENSAGENS COM ALTA TAXA DE RESPOSTA (adapte, não copie):
{memory_template_hint}
"""

    prompt = f"""
    Você é um especialista em marketing mensurável para negócios locais.
    Crie uma mensagem pessoal e profissional para enviar via WhatsApp ao seguinte estabelecimento:
{template_block}
    ESTABELECIMENTO:
    - Nome: {name}
    - Faixa: {faixa.upper()} (score: {lead.get('score', 0)}/100)
    - Pontos fracos identificados: {weakness}

    DIRETRIZES:
    - Mensagem em português brasileiro
    - Tom profissional mas acessível
    - Máximo de 300 caracteres
    - Incluir o nome do estabelecimento
    - Mentionar pelo menos um ponto fraco do dossiê
    - Terminar com chamada para ação suave
    - NÃO incluir linguagem promocional excessiva ou spam

    Responda APENAS com a mensagem, sem formatação adicional ou explicações.
    """

    return prompt.strip()


def _generate_template_message(lead: Dict[str, Any], faixa: str) -> str:
    """
    Generate message using predefined templates as fallback.
    """
    name = lead.get("name", "Estabelecimento")
    dossie = lead.get("dossie", {})
    pontos_fracos = dossie.get("pontos_fracos", [])
    if pontos_fracos and pontos_fracos[0]:
        weakness = pontos_fracos[0]
    else:
        weakness = "presença digital poderia ser fortalecida"

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
    message += "\n\nResponda SAIR para não receber mais contatos."
    message = truncate_message(message, MESSAGE_MAX_LENGTH)

    return message


async def send_whatsapp_message(
    lead: Dict[str, Any],
    message: str,
    evolution_url: str = None,
    evolution_key: str = None,
    evolution_instance_id: str = None,
    daily_count: Dict[str, int] = None,
    last_send_time: Dict[str, float] = None
) -> Dict[str, Any]:
    """Dispatcher: routes to the configured WhatsApp gateway via IWhatsAppGateway port."""
    # Check daily message limit
    if not await check_daily_limit():
        logger.warning("Daily message limit reached, skipping send")
        return {**lead, "whatsapp_status": "limite_diario", "delivery_status": "bloqueado"}
    
    gateway = ServiceFactory.get_whatsapp_gateway()

    phone_clean = re.sub(r'\D', '', lead.get("phone", ""))
    if not phone_clean or len(phone_clean) < 10:
        return {**lead, "whatsapp_status": "telefone_inválido", "delivery_status": "falha"}

    msg = WhatsAppMessage(
        phone=phone_clean,
        text=message,
        session="default"
    )

    result: WhatsAppResponse = await gateway.send_text(msg)

    if result.success:
        from datetime import datetime
        # Increment daily counter
        await increment_daily_counter()
        return {
            **lead,
            "whatsapp_status": "enviado",
            "delivery_status": "enviado",
            "message_sent_at": datetime.now().isoformat(),
            "message_id": result.message_id,
            "status": "mensagem_enviada",
            "gateway": result.gateway
        }
    else:
        return {
            **lead,
            "whatsapp_status": "erro_gateway",
            "delivery_status": "falha",
            "gateway": result.gateway,
            "error_detail": result.error
        }


async def _store_message_in_memory(lead: Dict[str, Any], message: str) -> None:
    """
    Store generated message in memory managers if available.
    """
    try:
        lead_id = lead.get("id") or lead.get("google_maps_id")
        if not lead_id:
            logger.debug("No lead identifier found, skipping memory storage for generated message")
            return

        postgres_mem = runtime.get_postgres_memory()

        if postgres_mem:
            await postgres_mem.store_lead_memory(lead_id, "generated_message", {"message": message})

    except Exception as e:
        logger.warning(f"Failed to store generated message in memory for lead {lead.get('id')}: {e}")


async def _store_sent_message_in_memory(lead: Dict[str, Any], message: str, send_result: Dict[str, Any]) -> None:
    """
    Store sent message result in memory managers if available.
    """
    try:
        lead_id = lead.get("id") or lead.get("google_maps_id")
        if not lead_id:
            logger.debug("No lead identifier found, skipping memory storage for sent message")
            return

        postgres_mem = runtime.get_postgres_memory()

        if postgres_mem:
            await postgres_mem.store_lead_memory(lead_id, "sent_message", {
                "message": message,
                "send_result": send_result,
                "timestamp": lead.get("message_sent_at")
            })

    except Exception as e:
        logger.warning(f"Failed to store sent message in memory for lead {lead.get('id')}: {e}")
