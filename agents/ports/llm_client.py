"""
Porta ILLMClient -- Interface invariante para comunicação com LLMs.

Invariantes:
  - I-LLM-1: complete() aceita lista de LLMMessage e retorna LLMResponse
  - I-LLM-2: O retry é responsabilidade do caller ou adapter, NUNCA desta interface
  - I-LLM-3: O campo model é obrigatório (não há "default model" nesta camada)
"""
from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass, field


@dataclass(frozen=True)
class LLMMessage:
    """Mensagem no formato padrão de chat completion."""
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass(frozen=True)
class LLMResponse:
    """Resposta padronizada de qualquer LLM."""
    content: str
    model: str
    usage: dict = field(default_factory=dict)
    finish_reason: str = "stop"


class LLMError(Exception):
    """Exceção base para erros de LLM."""
    def __init__(self, message: str, model: str = None, status_code: int = None):
        super().__init__(message)
        self.model = model
        self.status_code = status_code


class ILLMClient(ABC):
    """
    Porta invariante para clientes LLM.

    Qualquer provedor (LiteLLM, OpenAI, DeepSeek, Ollama) implementa esta
    interface. O Kirin Core depende apenas desta abstração.
    """

    @abstractmethod
    async def complete(
        self,
        messages: List[LLMMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        response_format: Optional[str] = None,
    ) -> LLMResponse:
        """
        Gera uma completion.

        Args:
            messages: Lista ordenada de mensagens
            model: Identificador do modelo
            temperature: Temperatura de amostragem
            max_tokens: Limite máximo de tokens
            response_format: "json" para JSON, None para texto livre

        Returns:
            LLMResponse com o conteúdo gerado
        """
        ...

    @abstractmethod
    async def embed(self, texts: List[str], model: str) -> List[List[float]]:
        """
        Gera embeddings para uma lista de textos.

        Args:
            texts: Lista de textos para embeddar
            model: Identificador do modelo de embedding

        Returns:
            Lista de vetores
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Verifica se o serviço LLM está operacional."""
        ...
