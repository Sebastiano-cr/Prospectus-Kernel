"""
Kirin Ports -- Interfaces Invariantes.

Este pacote define as interfaces abstratas (Ports) que o Kirin Core usa
para se comunicar com serviços externos. Nenhuma implementação concreta
reside aqui -- apenas contratos.

Princípios:
  - Dependency Inversion Principle (Robert C. Martin)
  - Hexagonal Architecture / Ports & Adapters (Alistair Cockburn)
  - Model Context Protocol (Anthropic/Google/Microsoft)

Invariantes:
  - I-PORT-1: Uma vez definida, a interface NÃO muda (apenas extensão compatível)
  - I-PORT-2: Todo adapter deve passar nos testes de contrato do port correspondente
  - I-PORT-3: O core NUNCA importa implementações concretas
"""
from .llm_client import ILLMClient, LLMMessage, LLMResponse, LLMError
from .whatsapp_gateway import IWhatsAppGateway, WhatsAppMessage, WhatsAppResponse
from .memory_manager import IMemoryManager, MemoryResult
from .media_generator import IMediaGenerator, MediaRequest, MediaResponse, MediaType
from .scraper import IScraper, ScrapedData

__all__ = [
    "ILLMClient", "LLMMessage", "LLMResponse", "LLMError",
    "IWhatsAppGateway", "WhatsAppMessage", "WhatsAppResponse",
    "IMemoryManager", "MemoryResult",
    "IMediaGenerator", "MediaRequest", "MediaResponse", "MediaType",
    "IScraper", "ScrapedData",
]
