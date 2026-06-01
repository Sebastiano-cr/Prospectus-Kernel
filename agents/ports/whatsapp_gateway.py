"""
Porta IWhatsAppGateway -- Interface invariante para envio de mensagens WhatsApp.

Invariantes:
  - I-WA-1: send_text() aceita WhatsAppMessage e retorna WhatsAppResponse
  - I-WA-2: O gateway name é fixo por implementação
  - I-WA-3: A validação de telefone é responsabilidade do adapter
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class WhatsAppMessage:
    """Mensagem a ser enviada via WhatsApp."""
    phone: str
    text: str
    session: str = "default"


@dataclass(frozen=True)
class WhatsAppResponse:
    """Resposta padronizada de envio WhatsApp."""
    success: bool
    message_id: Optional[str]
    gateway: str
    error: Optional[str] = None


class IWhatsAppGateway(ABC):
    """
    Porta invariante para gateways WhatsApp.

    Cada gateway (Evolution API, OpenWA, etc.) implementa esta interface.
    """

    @abstractmethod
    async def send_text(self, message: WhatsAppMessage) -> WhatsAppResponse:
        """Envia uma mensagem de texto via WhatsApp."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Verifica se o gateway está operacional."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Nome identificador do gateway."""
        ...
