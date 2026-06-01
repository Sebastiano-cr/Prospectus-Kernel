"""
Testes de contrato para ILLMClient.
Cada adapter deve ser testado com estes mesmos testes.
"""
import pytest
from agents.ports.llm_client import ILLMClient, LLMMessage


class TestLLMClientContract:
    """Testes de contrato para qualquer implementação de ILLMClient."""

    @pytest.fixture
    def client(self) -> ILLMClient:
        """Deve ser substituído por cada adapter nos testes."""
        raise NotImplementedError("Subclass must provide client fixture")

    @pytest.mark.asyncio
    async def test_complete_returns_valid_response(self, client: ILLMClient):
        messages = [LLMMessage(role="user", content="Say hello")]
        response = await client.complete(messages, model="deepseek-chat")

        assert response.content is not None
        assert len(response.content) > 0
        assert response.model is not None

    @pytest.mark.asyncio
    async def test_complete_with_json_format(self, client: ILLMClient):
        messages = [LLMMessage(role="user", content='Return {"key": "value"}')]
        response = await client.complete(
            messages,
            model="deepseek-chat",
            response_format="json"
        )

        import json
        data = json.loads(response.content)
        assert "key" in data

    @pytest.mark.asyncio
    async def test_health_check(self, client: ILLMClient):
        result = await client.health_check()
        assert isinstance(result, bool)


class TestLiteLLMContract(TestLLMClientContract):
    """Testes de contrato para LiteLLMAdapter."""

    @pytest.fixture
    def client(self):
        from agents.adapters.litellm_adapter import LiteLLMAdapter
        return LiteLLMAdapter()
