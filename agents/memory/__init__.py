"""
Memory package for the Kirin cognitive runtime.
"""
from .base import BaseMemoryManager
from .embedding_router import (
    EmbeddingStrategy,
    SentenceTransformersStrategy,
    OpenAITextEmbeddingStrategy,
    LiteLLMEmbeddingStrategy,
    GraphRAGStrategy,
    MultimodalVisionStrategy,
    EmbeddingRouter,
    create_default_router,
)

__all__ = [
    "BaseMemoryManager",
    "EmbeddingStrategy",
    "SentenceTransformersStrategy",
    "OpenAITextEmbeddingStrategy",
    "LiteLLMEmbeddingStrategy",
    "GraphRAGStrategy",
    "MultimodalVisionStrategy",
    "EmbeddingRouter",
    "create_default_router",
]
