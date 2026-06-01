"""
Service Factory -- Injeção de Dependência para o Kirin.

Cria e gerencia instâncias de adapters. O core NUNCA importa
implementações concretas diretamente -- apenas usa esta factory.
"""
import os
from typing import Optional
from .ports.llm_client import ILLMClient
from .ports.whatsapp_gateway import IWhatsAppGateway
from .ports.memory_manager import IMemoryManager
from .ports.media_generator import IMediaGenerator
from .ports.scraper import IScraper


class ServiceFactory:
    """Factory para criar e injetar dependências."""

    _llm_client: Optional[ILLMClient] = None
    _whatsapp_gateway: Optional[IWhatsAppGateway] = None
    _memory_manager: Optional[IMemoryManager] = None
    _media_generator: Optional[IMediaGenerator] = None
    _scraper: Optional[IScraper] = None

    @classmethod
    def get_llm_client(cls) -> ILLMClient:
        if cls._llm_client is None:
            from .adapters.litellm_adapter import LiteLLMAdapter
            cls._llm_client = LiteLLMAdapter()
        return cls._llm_client

    @classmethod
    def set_llm_client(cls, client: ILLMClient) -> None:
        """Permite injetar um cliente LLM customizado (para testes)."""
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
        """Permite injetar um gateway WhatsApp customizado (para testes)."""
        cls._whatsapp_gateway = gateway

    @classmethod
    def get_media_generator(cls) -> IMediaGenerator:
        if cls._media_generator is None:
            from .adapters.muapi_adapter import MuapiAdapter
            cls._media_generator = MuapiAdapter()
        return cls._media_generator

    @classmethod
    def set_media_generator(cls, generator: IMediaGenerator) -> None:
        """Permite injetar um gerador de mídia customizado (para testes)."""
        cls._media_generator = generator

    @classmethod
    def get_scraper(cls) -> IScraper:
        if cls._scraper is None:
            scraper_type = os.getenv("SCRAPER_TYPE", "mcp").lower()
            if scraper_type == "mcp":
                from .adapters.mcp_scraper_adapter import MCPScraperAdapter
                cls._scraper = MCPScraperAdapter()
            else:
                from .adapters.mcp_scraper_adapter import MCPScraperAdapter
                cls._scraper = MCPScraperAdapter()
        return cls._scraper

    @classmethod
    def set_scraper(cls, scraper: IScraper) -> None:
        """Permite injetar um scraper customizado (para testes)."""
        cls._scraper = scraper

    @classmethod
    def reset(cls) -> None:
        """Reseta todas as instâncias (para testes)."""
        cls._llm_client = None
        cls._whatsapp_gateway = None
        cls._memory_manager = None
        cls._media_generator = None
        cls._scraper = None
