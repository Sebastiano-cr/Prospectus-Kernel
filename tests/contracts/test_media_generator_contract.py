"""
Testes de contrato para IMediaGenerator.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from agents.ports.media_generator import IMediaGenerator, MediaRequest, MediaResponse, MediaType


class TestMediaGeneratorContract:
    """Testes de contrato para qualquer implementação de IMediaGenerator."""

    @pytest.fixture
    def generator(self) -> IMediaGenerator:
        """Deve ser substituído por cada adapter nos testes."""
        raise NotImplementedError("Subclass must provide generator fixture")

    @pytest.mark.asyncio
    async def test_generate_returns_response(self, generator: IMediaGenerator):
        request = MediaRequest(
            prompt="A serene mountain lake at sunrise",
            media_type=MediaType.IMAGE,
            params={"aspect_ratio": "16:9"}
        )
        result = await generator.generate(request, api_key="test-key")

        assert isinstance(result, MediaResponse)
        assert result.success is True or result.error is not None

    @pytest.mark.asyncio
    async def test_health_check(self, generator: IMediaGenerator):
        result = await generator.health_check()
        assert isinstance(result, bool)


class TestMuapiContract(TestMediaGeneratorContract):
    """Testes de contrato para MuapiAdapter."""

    @pytest.fixture
    def generator(self):
        from agents.adapters.muapi_adapter import MuapiAdapter
        return MuapiAdapter()

    @pytest.mark.asyncio
    async def test_generate_returns_response(self, generator: IMediaGenerator):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"request_id": "test-123"}

        mock_poll_response = MagicMock()
        mock_poll_response.status_code = 200
        mock_poll_response.json.return_value = {
            "status": "completed",
            "output": {"url": "https://example.com/image.png"},
        }

        with patch("agents.adapters.muapi_adapter.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.get.return_value = mock_poll_response
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            request = MediaRequest(
                prompt="A cat wearing a hat",
                media_type=MediaType.IMAGE,
                params={"model_id": "flux-dev"},
            )
            result = await generator.generate(request, api_key="test-key")

        assert isinstance(result, MediaResponse)
        assert result.success is True
        assert result.output_url == "https://example.com/image.png"

    @pytest.mark.asyncio
    async def test_model_id_resolution(self, generator: IMediaGenerator):
        from agents.muapi_models_pkg.muapi_models import get_model_by_id
        model = get_model_by_id("flux-dev")
        assert model is not None
        assert model.endpoint == "flux-dev-image"
        assert model.category == "t2i"

    @pytest.mark.asyncio
    async def test_all_categories_have_models(self):
        from agents.muapi_models_pkg.muapi_models import get_models_by_category
        for cat in ("t2i", "i2i", "t2v", "i2v", "v2v", "lipsync", "audio"):
            models = get_models_by_category(cat)
            assert len(models) > 0, f"No models for category {cat}"
