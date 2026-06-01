"""
Testes de contrato para IWhatsAppGateway.
Cada adapter deve ser testado com estes mesmos testes.
"""
import pytest
from agents.ports.whatsapp_gateway import IWhatsAppGateway, WhatsAppMessage


class TestWhatsAppGatewayContract:
    """Testes de contrato para qualquer implementação de IWhatsAppGateway."""

    @pytest.fixture
    def gateway(self) -> IWhatsAppGateway:
        """Deve ser substituído por cada adapter nos testes."""
        raise NotImplementedError("Subclass must provide gateway fixture")

    @pytest.mark.asyncio
    async def test_send_text_success(self, gateway: IWhatsAppGateway):
        msg = WhatsAppMessage(phone="5511999999999", text="Test message")
        result = await gateway.send_text(msg)

        assert result.success is True
        assert result.gateway == gateway.name

    @pytest.mark.asyncio
    async def test_send_text_invalid_phone(self, gateway: IWhatsAppGateway):
        msg = WhatsAppMessage(phone="123", text="Test message")
        result = await gateway.send_text(msg)

        assert result.success is False
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_health_check(self, gateway: IWhatsAppGateway):
        result = await gateway.health_check()
        assert isinstance(result, bool)


class TestEvolutionAPIContract(TestWhatsAppGatewayContract):
    """Testes de contrato para EvolutionAPIAdapter."""

    @pytest.fixture
    def gateway(self):
        from agents.adapters.evolution_api_adapter import EvolutionAPIAdapter
        return EvolutionAPIAdapter()


class TestOpenWAContract(TestWhatsAppGatewayContract):
    """Testes de contrato para OpenWAAdapter."""

    @pytest.fixture
    def gateway(self):
        from agents.adapters.openwa_adapter import OpenWAAdapter
        return OpenWAAdapter()
