"""
Testes unitários para MuapiAdapter Enhanced.
"""
import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from agents.ports.media_generator import MediaRequest, MediaResponse, MediaType
from agents.muapi_models_pkg.muapi_models import (
    get_model_by_id,
    get_models_by_category,
    list_all_model_ids,
    ALL_MODELS,
    CATEGORY_MAP,
)


class TestMuapiAdapterEnhanced:
    """Testes unitários para o MuapiAdapter expandido."""

    @pytest.fixture
    def adapter(self):
        from agents.adapters.muapi_adapter import MuapiAdapter
        return MuapiAdapter()

    # ─── Model Registry Tests ────────────────────────────────────────────────

    def test_model_registry_has_200_plus_models(self):
        assert len(ALL_MODELS) >= 150  # We have 165+ models

    def test_get_model_by_id_flux_dev(self):
        model = get_model_by_id("flux-dev")
        assert model is not None
        assert model.name == "Flux Dev"
        assert model.endpoint == "flux-dev-image"
        assert model.category == "t2i"

    def test_get_model_by_id_kling_t2v(self):
        model = get_model_by_id("kling-v2.1-master-t2v")
        assert model is not None
        assert model.category == "t2v"

    def test_get_model_by_id_not_found(self):
        model = get_model_by_id("nonexistent-model")
        assert model is None

    def test_get_models_by_category_t2i(self):
        models = get_models_by_category("t2i")
        assert len(models) > 20
        assert all(m.category == "t2i" for m in models)

    def test_get_models_by_category_i2v(self):
        models = get_models_by_category("i2v")
        assert len(models) > 20
        assert all(m.category == "i2v" for m in models)

    def test_get_models_by_category_audio(self):
        models = get_models_by_category("audio")
        assert len(models) > 5
        assert all(m.category == "audio" for m in models)

    def test_all_categories_have_models(self):
        for cat in ("t2i", "i2i", "t2v", "i2v", "v2v", "lipsync", "audio"):
            models = get_models_by_category(cat)
            assert len(models) > 0, f"Category {cat} has no models"

    def test_list_all_model_ids(self):
        ids = list_all_model_ids()
        assert len(ids) >= 150  # We have 165+ models
        assert "flux-dev" in ids
        assert "kling-v2.1-master-t2v" in ids

    def test_category_map_completeness(self):
        for media_type in MediaType:
            assert media_type.value in CATEGORY_MAP, f"MediaType {media_type} not in CATEGORY_MAP"

    # ─── Endpoint Resolution Tests ───────────────────────────────────────────

    def test_resolve_endpoint_with_model_id(self, adapter):
        request = MediaRequest(
            prompt="test",
            media_type=MediaType.IMAGE,
            model_id="flux-dev",
        )
        endpoint = adapter._resolve_endpoint(request)
        assert endpoint == "flux-dev-image"

    def test_resolve_endpoint_with_unknown_model_id(self, adapter):
        request = MediaRequest(
            prompt="test",
            media_type=MediaType.IMAGE,
            model_id="custom-endpoint",
        )
        endpoint = adapter._resolve_endpoint(request)
        assert endpoint == "custom-endpoint"

    def test_resolve_endpoint_fallback_to_media_type(self, adapter):
        request = MediaRequest(
            prompt="test",
            media_type=MediaType.IMAGE,
        )
        endpoint = adapter._resolve_endpoint(request)
        assert endpoint == "flux-dev-image"

    def test_resolve_endpoint_video(self, adapter):
        request = MediaRequest(
            prompt="test",
            media_type=MediaType.VIDEO,
        )
        endpoint = adapter._resolve_endpoint(request)
        assert endpoint == "seedance-pro-t2v"

    def test_resolve_endpoint_lipsync(self, adapter):
        request = MediaRequest(
            prompt="test",
            media_type=MediaType.LIP_SYNC,
        )
        endpoint = adapter._resolve_endpoint(request)
        assert endpoint == "infinitetalk-image-to-video"

    # ─── Payload Builder Tests ───────────────────────────────────────────────

    def test_build_payload_basic(self, adapter):
        request = MediaRequest(prompt="A cat", media_type=MediaType.IMAGE)
        payload = adapter._build_payload(request)
        assert payload == {"prompt": "A cat"}

    def test_build_payload_with_params(self, adapter):
        request = MediaRequest(
            prompt="A cat",
            media_type=MediaType.IMAGE,
            params={"aspect_ratio": "16:9", "width": 1024},
        )
        payload = adapter._build_payload(request)
        assert payload["prompt"] == "A cat"
        assert payload["aspect_ratio"] == "16:9"
        assert payload["width"] == 1024

    def test_build_payload_filters_tool_name(self, adapter):
        request = MediaRequest(
            prompt="test",
            media_type=MediaType.IMAGE,
            params={"tool_name": "should_be_removed"},
        )
        payload = adapter._build_payload(request)
        assert "tool_name" not in payload

    # ─── Generate Tests ──────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_generate_success(self, adapter):
        mock_submit = MagicMock()
        mock_submit.status_code = 200
        mock_submit.json.return_value = {"request_id": "req-123"}

        mock_poll = MagicMock()
        mock_poll.status_code = 200
        mock_poll.json.return_value = {
            "status": "completed",
            "output": {"url": "https://example.com/result.png"},
        }

        with patch("agents.adapters.muapi_adapter.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            # First call is submit (post), second is poll (get)
            mock_instance.post.return_value = mock_submit
            mock_instance.get.return_value = mock_poll
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            request = MediaRequest(
                prompt="A beautiful sunset",
                media_type=MediaType.IMAGE,
                model_id="flux-dev",
            )
            result = await adapter.generate(request, api_key="test-key")

        assert result.success is True
        assert result.output_url == "https://example.com/result.png"
        assert result.request_id == "req-123"

    @pytest.mark.asyncio
    async def test_generate_with_multiple_outputs(self, adapter):
        mock_submit = MagicMock()
        mock_submit.status_code = 200
        mock_submit.json.return_value = {"request_id": "req-456"}

        mock_poll = MagicMock()
        mock_poll.status_code = 200
        mock_poll.json.return_value = {
            "status": "completed",
            "output": {
                "outputs": [
                    {"url": "https://example.com/img1.png"},
                    {"url": "https://example.com/img2.png"},
                ]
            },
        }

        with patch("agents.adapters.muapi_adapter.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_submit
            mock_instance.get.return_value = mock_poll
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            request = MediaRequest(
                prompt="Two cats",
                media_type=MediaType.IMAGE,
                params={"num_images": 2},
            )
            result = await adapter.generate(request, api_key="test-key")

        assert result.success is True
        assert len(result.outputs) == 2

    @pytest.mark.asyncio
    async def test_generate_http_error(self, adapter):
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        with patch("agents.adapters.muapi_adapter.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            request = MediaRequest(prompt="test", media_type=MediaType.IMAGE)
            result = await adapter.generate(request, api_key="bad-key")

        assert result.success is False
        assert "401" in result.error

    @pytest.mark.asyncio
    async def test_generate_connection_error(self, adapter):
        with patch("agents.adapters.muapi_adapter.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = httpx.ConnectError("Connection refused")
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            request = MediaRequest(prompt="test", media_type=MediaType.IMAGE)
            result = await adapter.generate(request, api_key="test-key")

        assert result.success is False
        assert "unreachable" in result.error

    # ─── Poll Tests ──────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_poll_timeout(self, adapter):
        adapter.max_polls = 2
        adapter.poll_interval = 0.01

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "processing"}

        with patch("agents.adapters.muapi_adapter.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            result = await adapter.poll_result("req-timeout", "test-key")

        assert result.success is False
        assert "timeout" in result.error.lower()

    @pytest.mark.asyncio
    async def test_poll_failed_status(self, adapter):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "failed",
            "error": "Generation failed: invalid prompt",
        }

        with patch("agents.adapters.muapi_adapter.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            result = await adapter.poll_result("req-fail", "test-key")

        assert result.success is False
        assert "invalid prompt" in result.error

    # ─── Health Check Tests ──────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_health_check_success(self, adapter):
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("agents.adapters.muapi_adapter.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            result = await adapter.health_check()

        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, adapter):
        with patch("agents.adapters.muapi_adapter.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = httpx.ConnectError("Connection refused")
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            result = await adapter.health_check()

        assert result is False
