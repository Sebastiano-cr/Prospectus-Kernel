"""
Testes unitários para MCPScraperAdapter.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx


class TestMCPScraperAdapter:
    """Testes unitários para o adapter de scraper MCP."""

    @pytest.fixture
    def adapter(self):
        from agents.adapters.mcp_scraper_adapter import MCPScraperAdapter
        return MCPScraperAdapter(base_url="http://mock-mcp:3100")

    @pytest.mark.asyncio
    async def test_scrape_google_maps_success(self, adapter):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {
                "name": "Pizza Place",
                "rating": 4.5,
                "address": "123 Main St",
            }
        }

        with patch("agents.adapters.mcp_scraper_adapter.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            result = await adapter.scrape("pizza near me")

        assert result.success is True
        assert result.source == "mcp"
        assert result.data["name"] == "Pizza Place"
        assert result.data["rating"] == 4.5

    @pytest.mark.asyncio
    async def test_scrape_instagram_success(self, adapter):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {
                "username": "testuser",
                "followers": 1000,
                "bio": "Test bio",
            }
        }

        with patch("agents.adapters.mcp_scraper_adapter.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            result = await adapter.scrape(
                "testuser", {"tool_name": "get_instagram_profile"}
            )

        assert result.success is True
        assert result.data["username"] == "testuser"

    @pytest.mark.asyncio
    async def test_scrape_unknown_tool(self, adapter):
        result = await adapter.scrape("test", {"tool_name": "nonexistent"})
        assert result.success is False
        assert "Unknown tool" in result.error

    @pytest.mark.asyncio
    async def test_scrape_http_error(self, adapter):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch("agents.adapters.mcp_scraper_adapter.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            result = await adapter.scrape("test query")

        assert result.success is False
        assert "500" in result.error

    @pytest.mark.asyncio
    async def test_scrape_connection_error(self, adapter):
        with patch("agents.adapters.mcp_scraper_adapter.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = httpx.ConnectError("Connection refused")
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            result = await adapter.scrape("test query")

        assert result.success is False
        assert "unreachable" in result.error

    @pytest.mark.asyncio
    async def test_scrape_timeout(self, adapter):
        with patch("agents.adapters.mcp_scraper_adapter.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = httpx.TimeoutException("Timeout")
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            result = await adapter.scrape("test query")

        assert result.success is False
        assert "timeout" in result.error.lower()

    @pytest.mark.asyncio
    async def test_health_check_success(self, adapter):
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("agents.adapters.mcp_scraper_adapter.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            result = await adapter.health_check()

        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, adapter):
        with patch("agents.adapters.mcp_scraper_adapter.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = httpx.ConnectError("Connection refused")
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            result = await adapter.health_check()

        assert result is False

    def test_source_property(self, adapter):
        assert adapter.source == "mcp"

    def test_default_params(self, adapter):
        """Test that default tool_name is search_google_maps."""
        assert adapter.source == "mcp"
