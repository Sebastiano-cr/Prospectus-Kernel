"""
Testes de integração para ServiceFactory.
"""
import pytest
from unittest.mock import patch, MagicMock


class TestServiceFactoryIntegration:
    """Testes de integração do ServiceFactory."""

    def setup_method(self):
        from agents.factory import ServiceFactory
        ServiceFactory.reset()

    def teardown_method(self):
        from agents.factory import ServiceFactory
        ServiceFactory.reset()

    # ─── Scraper Tests ───────────────────────────────────────────────────────

    def test_get_scraper_returns_mcp_default(self):
        from agents.factory import ServiceFactory
        from agents.adapters.mcp_scraper_adapter import MCPScraperAdapter

        scraper = ServiceFactory.get_scraper()
        assert isinstance(scraper, MCPScraperAdapter)

    def test_set_scraper_override(self):
        from agents.factory import ServiceFactory
        from agents.ports.scraper import IScraper, ScrapedData

        class MockScraper(IScraper):
            @property
            def source(self):
                return "mock"

            async def scrape(self, query, params=None):
                return ScrapedData(source="mock", data={}, success=True)

            async def health_check(self):
                return True

        mock = MockScraper()
        ServiceFactory.set_scraper(mock)
        assert ServiceFactory.get_scraper() is mock

    def test_reset_clears_scraper(self):
        from agents.factory import ServiceFactory

        scraper1 = ServiceFactory.get_scraper()
        ServiceFactory.reset()
        scraper2 = ServiceFactory.get_scraper()
        assert scraper1 is not scraper2

    # ─── Media Generator Tests ───────────────────────────────────────────────

    def test_get_media_generator_returns_muapi(self):
        from agents.factory import ServiceFactory
        from agents.adapters.muapi_adapter import MuapiAdapter

        gen = ServiceFactory.get_media_generator()
        assert isinstance(gen, MuapiAdapter)

    def test_set_media_generator_override(self):
        from agents.factory import ServiceFactory
        from agents.ports.media_generator import IMediaGenerator, MediaRequest, MediaResponse

        class MockGenerator(IMediaGenerator):
            async def generate(self, request, api_key):
                return MediaResponse(success=True)
            async def poll_result(self, request_id, api_key):
                return MediaResponse(success=True)
            async def health_check(self):
                return True

        mock = MockGenerator()
        ServiceFactory.set_media_generator(mock)
        assert ServiceFactory.get_media_generator() is mock

    # ─── LLM Client Tests ────────────────────────────────────────────────────

    def test_get_llm_client_returns_litellm(self):
        from agents.factory import ServiceFactory
        from agents.adapters.litellm_adapter import LiteLLMAdapter

        client = ServiceFactory.get_llm_client()
        assert isinstance(client, LiteLLMAdapter)

    def test_set_llm_client_override(self):
        from agents.factory import ServiceFactory
        from agents.ports.llm_client import ILLMClient, LLMResponse, LLMMessage

        class MockLLM(ILLMClient):
            async def complete(self, messages, model="deepseek-chat", **kwargs):
                return LLMResponse(success=True, content="test", model=model)
            async def embed(self, texts, model):
                return [[0.1] * 1536 for _ in texts]
            async def health_check(self):
                return True

        mock = MockLLM()
        ServiceFactory.set_llm_client(mock)
        assert ServiceFactory.get_llm_client() is mock

    # ─── WhatsApp Gateway Tests ──────────────────────────────────────────────

    def test_get_whatsapp_gateway_returns_evolution(self):
        from agents.factory import ServiceFactory
        from agents.adapters.evolution_api_adapter import EvolutionAPIAdapter

        gw = ServiceFactory.get_whatsapp_gateway()
        assert isinstance(gw, EvolutionAPIAdapter)

    def test_set_whatsapp_gateway_override(self):
        from agents.factory import ServiceFactory
        from agents.ports.whatsapp_gateway import IWhatsAppGateway, WhatsAppMessage, WhatsAppResponse

        class MockGateway(IWhatsAppGateway):
            async def send_text(self, message: WhatsAppMessage) -> WhatsAppResponse:
                return WhatsAppResponse(success=True, message_id="msg-123", gateway="mock")
            async def health_check(self):
                return True
            @property
            def name(self):
                return "mock"

        mock = MockGateway()
        ServiceFactory.set_whatsapp_gateway(mock)
        assert ServiceFactory.get_whatsapp_gateway() is mock

    # ─── Reset Tests ─────────────────────────────────────────────────────────

    def test_reset_clears_all(self):
        from agents.factory import ServiceFactory

        # Get all instances
        ServiceFactory.get_llm_client()
        ServiceFactory.get_whatsapp_gateway()
        ServiceFactory.get_media_generator()
        ServiceFactory.get_scraper()

        ServiceFactory.reset()

        # All should be None (lazy init creates new ones)
        assert ServiceFactory._llm_client is None
        assert ServiceFactory._whatsapp_gateway is None
        assert ServiceFactory._media_generator is None
        assert ServiceFactory._scraper is None

    # ─── Env Var Tests ───────────────────────────────────────────────────────

    def test_scraper_type_env_var(self):
        from agents.factory import ServiceFactory

        with patch.dict("os.environ", {"SCRAPER_TYPE": "mcp"}):
            ServiceFactory.reset()
            scraper = ServiceFactory.get_scraper()
            from agents.adapters.mcp_scraper_adapter import MCPScraperAdapter
            assert isinstance(scraper, MCPScraperAdapter)
