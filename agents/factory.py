import os
from typing import Optional
from .ports.llm_client import ILLMClient
from .ports.whatsapp_gateway import IWhatsAppGateway


class ServiceFactory:
    _llm_client: Optional[ILLMClient] = None
    _whatsapp_gateway: Optional[IWhatsAppGateway] = None

    @classmethod
    def get_llm_client(cls) -> ILLMClient:
        if cls._llm_client is None:
            from .adapters.litellm_adapter import LiteLLMAdapter
            cls._llm_client = LiteLLMAdapter()
        return cls._llm_client

    @classmethod
    def set_llm_client(cls, client: ILLMClient) -> None:
        cls._llm_client = client

    @classmethod
    def get_whatsapp_gateway(cls) -> IWhatsAppGateway:
        if cls._whatsapp_gateway is None:
            gateway_type = os.getenv("WHATSAPP_GATEWAY", "evolution").lower()
            if gateway_type == "openwa":
                from .adapters.openwa_adapter import OpenWAAdapter
                cls._whatsapp_gateway = OpenWAAdapter()
            else:
                from .adapters.evolution_api_adapter import EvolutionAPIAdapter
                cls._whatsapp_gateway = EvolutionAPIAdapter()
        return cls._whatsapp_gateway

    @classmethod
    def set_whatsapp_gateway(cls, gateway: IWhatsAppGateway) -> None:
        cls._whatsapp_gateway = gateway

    @classmethod
    def reset(cls) -> None:
        cls._llm_client = None
        cls._whatsapp_gateway = None
