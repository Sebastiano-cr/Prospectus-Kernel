"""
Testes de contrato para IScraper.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from agents.ports.scraper import IScraper, ScrapedData


class TestScraperContract:
    """Testes de contrato para qualquer implementação de IScraper."""

    @pytest.fixture
    def scraper(self) -> IScraper:
        """Deve ser substituído por cada adapter nos testes."""
        raise NotImplementedError("Subclass must provide scraper fixture")

    @pytest.mark.asyncio
    async def test_scrape_returns_data(self, scraper: IScraper):
        result = await scraper.scrape("test query")

        assert isinstance(result, ScrapedData)
        assert result.source == scraper.source

    @pytest.mark.asyncio
    async def test_health_check(self, scraper: IScraper):
        result = await scraper.health_check()
        assert isinstance(result, bool)


class TestMCPScraperContract(TestScraperContract):
    """Testes de contrato para MCPScraperAdapter com mock."""

    @pytest.fixture
    def scraper(self):
        from agents.adapters.mcp_scraper_adapter import MCPScraperAdapter
        return MCPScraperAdapter(base_url="http://mock-mcp:3100")

    @pytest.mark.asyncio
    async def test_scrape_returns_data(self, scraper: IScraper):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {"name": "Test Place", "rating": 4.5}
        }

        with patch("agents.adapters.mcp_scraper_adapter.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            result = await scraper.scrape("test query")

        assert isinstance(result, ScrapedData)
        assert result.success is True
        assert result.source == "mcp"
        assert result.data == {"name": "Test Place", "rating": 4.5}

    @pytest.mark.asyncio
    async def test_scrape_unknown_tool(self, scraper: IScraper):
        result = await scraper.scrape("test", {"tool_name": "nonexistent_tool"})
        assert result.success is False
        assert "Unknown tool" in result.error

    @pytest.mark.asyncio
    async def test_scrape_connection_error(self, scraper: IScraper):
        import httpx
        with patch("agents.adapters.mcp_scraper_adapter.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = httpx.ConnectError("Connection refused")
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            result = await scraper.scrape("test query")

        assert result.success is False
        assert "unreachable" in result.error

    @pytest.mark.asyncio
    async def test_health_check_success(self, scraper: IScraper):
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("agents.adapters.mcp_scraper_adapter.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            result = await scraper.health_check()

        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, scraper: IScraper):
        import httpx
        with patch("agents.adapters.mcp_scraper_adapter.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = httpx.ConnectError("Connection refused")
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            result = await scraper.health_check()

        assert result is False
