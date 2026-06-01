"""
Adapter Evolution API -- Implementa IWhatsAppGateway para Evolution API.
"""
import httpx
import os
from ..ports.whatsapp_gateway import IWhatsAppGateway, WhatsAppMessage, WhatsAppResponse


class EvolutionAPIAdapter(IWhatsAppGateway):
    """Adapter para Evolution API."""

    def __init__(self):
        self.base_url = os.getenv("EVOLUTION_URL")
        self.api_key = os.getenv("EVOLUTION_API_KEY")
        self.instance_id = os.getenv("EVOLUTION_INSTANCE_ID")

    @property
    def name(self) -> str:
        return "evolution"

    async def send_text(self, message: WhatsAppMessage) -> WhatsAppResponse:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.base_url}/message/sendText/{self.instance_id}",
                    headers={"apikey": self.api_key},
                    json={"number": message.phone, "text": message.text}
                )

            if resp.status_code == 200:
                data = resp.json()
                return WhatsAppResponse(
                    success=True,
                    message_id=data.get("key", {}).get("id"),
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
                resp = await client.get(f"{self.base_url}/instance/fetchInstances")
                return resp.status_code == 200
        except Exception:
            return False
