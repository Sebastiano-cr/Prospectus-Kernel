"""
Testes de contrato para ServiceFactory.
"""
import pytest
from agents.factory import ServiceFactory
from agents.ports.llm_client import ILLMClient, LLMMessage, LLMResponse


class MockLLMClient(ILLMClient):
    """Mock para testes de factory."""

    async def complete(self, messages, model, temperature=0.7, max_tokens=None, response_format=None):
        return LLMResponse(content="mock response", model=model)

    async def embed(self, texts, model):
        return [[0.1] * 384 for _ in texts]

    async def health_check(self):
        return True


class TestServiceFactoryContract:
    """Testes de contrato para ServiceFactory."""

    def setup_method(self):
        ServiceFactory.reset()

    def teardown_method(self):
        ServiceFactory.reset()

    def test_get_llm_client_returns_default(self):
        client = ServiceFactory.get_llm_client()
        assert isinstance(client, ILLMClient)

    def test_set_llm_client_overrides(self):
        mock = MockLLMClient()
        ServiceFactory.set_llm_client(mock)
        assert ServiceFactory.get_llm_client() is mock

    def test_reset_clears_all(self):
        mock = MockLLMClient()
        ServiceFactory.set_llm_client(mock)
        ServiceFactory.reset()
        assert ServiceFactory.get_llm_client() is not mock

    @pytest.mark.asyncio
    async def test_factory_client_works(self):
        client = ServiceFactory.get_llm_client()
        response = await client.complete(
            messages=[LLMMessage(role="user", content="test")],
            model="test-model"
        )
        assert response.content is not None
