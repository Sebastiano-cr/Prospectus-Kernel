"""
Adapter MCP Scraper -- Implementa IScraper delegando para o MCP server.

O MCP server (mcp-server/server.py) expõe tools de scraping via HTTP.
Este adapter encapsula essas chamadas atrás da porta IScraper.
"""
import httpx
import logging
from typing import Dict, Any, Optional
from ..ports.scraper import IScraper, ScrapedData

logger = logging.getLogger(__name__)

# MCP server tools disponíveis
AVAILABLE_TOOLS = ("search_google_maps", "get_instagram_profile")


class MCPScraperAdapter(IScraper):
    """
    Adapter que delega scraping para o MCP server via HTTP.

    Tools suportados:
      - search_google_maps(query, location?, ...) -> Google Maps data
      - get_instagram_profile(username) -> Instagram profile data
    """

    def __init__(self, base_url: str = "http://localhost:3100"):
        self.base_url = base_url.rstrip("/")

    @property
    def source(self) -> str:
        return "mcp"

    async def scrape(self, query: str, params: Dict[str, Any] = None) -> ScrapedData:
        """
        Executa um tool de scraping via MCP server.

        params deve conter:
          - tool_name: str (default: "search_google_maps")
          - argumentos específicos do tool
        """
        params = params or {}
        tool_name = params.pop("tool_name", "search_google_maps")

        if tool_name not in AVAILABLE_TOOLS:
            return ScrapedData(
                source=self.source,
                data={},
                success=False,
                error=f"Unknown tool: {tool_name}. Available: {AVAILABLE_TOOLS}",
            )

        arguments = {"query": query, **params}

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{self.base_url}/tools/{tool_name}",
                    json={"arguments": arguments},
                )

            if resp.status_code == 200:
                data = resp.json().get("result", {})
                return ScrapedData(
                    source=self.source,
                    data=data,
                    success=True,
                )
            else:
                error_detail = resp.text[:200]
                logger.warning(
                    f"MCP tool {tool_name} returned {resp.status_code}: {error_detail}"
                )
                return ScrapedData(
                    source=self.source,
                    data={},
                    success=False,
                    error=f"HTTP {resp.status_code}: {error_detail}",
                )

        except httpx.TimeoutException:
            logger.warning(f"MCP tool {tool_name} timed out")
            return ScrapedData(
                source=self.source,
                data={},
                success=False,
                error="MCP server timeout",
            )
        except httpx.ConnectError:
            logger.warning("MCP server unreachable")
            return ScrapedData(
                source=self.source,
                data={},
                success=False,
                error="MCP server unreachable",
            )
        except Exception as e:
            logger.warning(f"MCP scrape failed: {e}")
            return ScrapedData(
                source=self.source,
                data={},
                success=False,
                error=str(e),
            )

    async def health_check(self) -> bool:
        """Verifica se o MCP server está operacional."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/health")
                return resp.status_code == 200
        except Exception:
            return False
