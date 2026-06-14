import os
import re
from dataclasses import dataclass
from typing import Optional

import httpx


@dataclass(frozen=True)
class WhatsAppMessage:
    phone: str
    text: str
    session: str = "default"


@dataclass(frozen=True)
class WhatsAppResponse:
    success: bool
    message_id: Optional[str]
    gateway: str
    error: Optional[str] = None


async def send_whatsapp(message: WhatsAppMessage) -> WhatsAppResponse:
    gateway_type = os.environ.get("WHATSAPP_GATEWAY", "evolution").lower()
    if gateway_type == "openwa":
        return await _send_openwa(message)
    return await _send_evolution(message)


async def _send_evolution(message: WhatsAppMessage) -> WhatsAppResponse:
    base_url = os.environ.get("EVOLUTION_URL")
    api_key = os.environ.get("EVOLUTION_API_KEY")
    instance_id = os.environ.get("EVOLUTION_INSTANCE_ID")
    if not base_url or not api_key or not instance_id:
        return WhatsAppResponse(success=False, message_id=None, gateway="evolution", error="Missing EVOLUTION_* env vars")
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{base_url}/message/sendText/{instance_id}",
                headers={"apikey": api_key},
                json={"number": re.sub(r"\D", "", message.phone), "text": message.text},
            )
        if resp.status_code == 200:
            data = resp.json()
            return WhatsAppResponse(success=True, message_id=data.get("key", {}).get("id"), gateway="evolution")
        return WhatsAppResponse(success=False, message_id=None, gateway="evolution", error=f"HTTP {resp.status_code}")
    except Exception as e:
        return WhatsAppResponse(success=False, message_id=None, gateway="evolution", error=str(e))


async def _send_openwa(message: WhatsAppMessage) -> WhatsAppResponse:
    base_url = os.environ.get("OPENWA_URL")
    api_key = os.environ.get("OPENWA_API_KEY")
    if not base_url or not api_key:
        return WhatsAppResponse(success=False, message_id=None, gateway="openwa", error="Missing OPENWA_* env vars")
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{base_url}/send-message",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"phone": re.sub(r"\D", "", message.phone), "message": message.text},
            )
        if resp.status_code == 200:
            data = resp.json()
            return WhatsAppResponse(success=True, message_id=data.get("id"), gateway="openwa")
        return WhatsAppResponse(success=False, message_id=None, gateway="openwa", error=f"HTTP {resp.status_code}")
    except Exception as e:
        return WhatsAppResponse(success=False, message_id=None, gateway="openwa", error=str(e))


def _clean_phone(phone: str) -> Optional[str]:
    cleaned = re.sub(r"\D", "", phone)
    return cleaned if len(cleaned) >= 10 else None
