"""
Porta IScraper -- Interface invariante para scraping de dados externos.

Invariantes:
  - I-SCRAPER-1: scrape() aceita query e retorna ScrapedData
  - I-SCRAPER-2: source é fixo por implementação
  - I-SCRAPER-3: Erros de scraping NÃO propagam
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass(frozen=True)
class ScrapedData:
    """Dados extraídos de uma fonte externa."""
    source: str
    data: Dict[str, Any]
    success: bool
    error: Optional[str] = None


class IScraper(ABC):
    """
    Porta invariante para scraping de dados externos.

    Cada fonte (Google Maps, Instagram, websites) implementa esta interface.
    """

    @abstractmethod
    async def scrape(self, query: str, params: Dict[str, Any] = None) -> ScrapedData:
        """Extrai dados de uma fonte externa."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Verifica se o scraper está operacional."""
        ...

    @property
    @abstractmethod
    def source(self) -> str:
        """Nome da fonte de dados."""
        ...
