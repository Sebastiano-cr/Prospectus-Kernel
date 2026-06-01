"""
Porta IMemoryManager -- Interface invariante para gerenciamento de memória.

Invariantes:
  - I-MEM-1: store/retrieve operam com namespace+key
  - I-MEM-2: cache_set/cache_get são para dados de curta duração (TTL)
  - I-MEM-3: search_similar aceita query_vector e retorna resultados com score
  - I-MEM-4: Esta interface NÃO expõe clientes de banco de dados internos
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass


@dataclass
class MemoryResult:
    """Resultado de uma busca de memória."""
    data: Dict[str, Any]
    score: Optional[float] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class IMemoryManager(ABC):
    """
    Porta invariante para gerenciamento de memória.

    Unifica PostgreSQL, Qdrant e Redis atrás de uma única interface.
    """

    # --- Storage (PostgreSQL-backed) ---
    @abstractmethod
    async def store(self, namespace: str, key: str, data: Dict[str, Any]) -> bool:
        """Armazena dados estruturados."""
        ...

    @abstractmethod
    async def retrieve(self, namespace: str, key: str) -> Optional[Dict[str, Any]]:
        """Recupera dados estruturados."""
        ...

    @abstractmethod
    async def delete(self, namespace: str, key: str) -> bool:
        """Remove dados estruturados."""
        ...

    # --- Search (Qdrant-backed) ---
    @abstractmethod
    async def search_similar(
        self,
        query_vector: List[float],
        namespace: str,
        limit: int = 10,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[MemoryResult]:
        """Busca por similaridade vetorial."""
        ...

    # --- Cache (Redis-backed) ---
    @abstractmethod
    async def cache_set(self, key: str, value: Any, ttl_seconds: int = 3600) -> bool:
        """Armazena valor em cache com TTL."""
        ...

    @abstractmethod
    async def cache_get(self, key: str) -> Optional[Any]:
        """Recupera valor do cache."""
        ...

    @abstractmethod
    async def cache_delete(self, key: str) -> bool:
        """Remove valor do cache."""
        ...

    # --- Lifecycle ---
    @abstractmethod
    async def initialize(self) -> None:
        """Inicializa conexões e recursos."""
        ...

    @abstractmethod
    async def shutdown(self) -> None:
        """Libera recursos e fecha conexões."""
        ...
