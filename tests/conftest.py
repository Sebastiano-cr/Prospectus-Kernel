"""
Fixtures compartilhadas para testes do Prospectus-Kernel.

Fornece mocks para LiteLLM, memory managers e dados de lead,
permitindo testar a lógica dos agentes sem dependências externas.
"""
import pytest
from typing import Any, Dict


class MockResponse:
    """Simula uma resposta HTTP para httpx."""
    def __init__(self, status_code: int, json_data: Any):
        self.status_code = status_code
        self._json_data = json_data

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


@pytest.fixture
def mock_litellm_enrich() -> MockResponse:
    """Mock para a resposta do LiteLLM no enricher."""
    content = (
        '{\n'
        '  "resumo_perfil": "Restaurante tradicional com comida caseira",\n'
        '  "pontos_fracos": ["Nao possui website", "Pouca presenca digital"],\n'
        '  "oportunidades": ["Criar site", "Delivery online"],\n'
        '  "maturidade_digital": "baixo"\n'
        '}'
    )
    return MockResponse(200, {
        "choices": [{
            "message": {"content": content}
        }]
    })


@pytest.fixture
def sample_lead() -> Dict[str, Any]:
    """Lead de exemplo para testes."""
    return {
        "name": "Restaurante Teste",
        "address": "Rua Exemplo, 123",
        "phone": "+55 11 99999-9999",
        "website": "",
        "instagram_username": "",
        "rating": 4.2,
        "google_maps_url": "https://maps.google.com/?cid=teste123",
    }


@pytest.fixture
def sample_dossie() -> Dict[str, Any]:
    """Dossiê de exemplo para testes do scorer e messenger."""
    return {
        "resumo_perfil": "Restaurante tradicional com comida caseira e ambiente familiar",
        "pontos_fracos": [
            "Nao possui website",
            "Pouca presenca nas redes sociais",
            "Nao aceita pedidos online",
        ],
        "oportunidades": [
            "Criar website",
            "Implementar delivery",
            "Reforcar Instagram",
        ],
        "maturidade_digital": "baixo",
    }


@pytest.fixture
def sample_scored_lead(sample_dossie) -> Dict[str, Any]:
    """Lead com score para testes do messenger."""
    return {
        "name": "Restaurante Teste",
        "score": 65,
        "faixa": "morno",
        "status": "qualificado",
        "dossie": sample_dossie,
        "website": "",
        "instagram_username": "",
    }



