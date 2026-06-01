"""
Adapter OpenWA -- Implementa IWhatsAppGateway para OpenWA.
"""
import httpx
import os
from ..ports.whatsapp_gateway import IWhatsAppGateway, WhatsAppMessage, WhatsAppResponse


class OpenWAAdapter(IWhatsAppGateway):
    """Adapter para OpenWA."""

    def __init__(self):
        self.base_url = os.getenv("OPENWA_URL")
        self.api_key = os.getenv("OPENWA_API_KEY")

    @property
    def name(self) -> str:
        return "openwa"

    async def send_text(self, message: WhatsAppMessage) -> WhatsAppResponse:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.base_url}/api/sessions/{message.session}/messages/send-text",
                    headers={"X-API-Key": self.api_key},
                    json={"chatId": f"{message.phone}@c.us", "text": message.text}
                )

            if resp.status_code == 200:
                data = resp.json()
                return WhatsAppResponse(
                    success=True,
                    message_id=data.get("id"),
                    gateway=self.name
                )
            return WhatsAppResponse(
                success=False,
                message_id=None,
                gateway=self.name,
                error=f"HTTP {resp.status_code}"
            )
        except Exception as e:
            return WhatsAppResponse(
                success=False,
                message_id=None,
                gateway=self.name,
                error=str(e)
            )

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/api/sessions")
                return resp.status_code == 200
        except Exception:
            return False
