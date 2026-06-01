"""
MCP Orchestrator -- Gerencia conexões com servidores MCP.

O MCP é o invariante universal de comunicação para ferramentas.
Todas as ferramentas externas viram servidores MCP, e o Kirin
as acessa via este orquestrador genérico.
"""
import asyncio
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class MCPServerConfig:
    """Configuração de um servidor MCP."""
    name: str
    command: Optional[str] = None
    args: List[str] = field(default_factory=list)
    env: Optional[Dict[str, str]] = None
    url: Optional[str] = None


class MCPOrchestrator:
    """Orquestrador genérico para servidores MCP."""

    def __init__(self):
        self.servers: Dict[str, MCPServerConfig] = {}
        self.sessions: Dict[str, Any] = {}

    def register_server(self, config: MCPServerConfig) -> None:
        """Registra um servidor MCP."""
        self.servers[config.name] = config

    async def connect_all(self) -> None:
        """Conecta a todos os servidores registrados."""
        for name, config in self.servers.items():
            try:
                await self._connect_server(name, config)
                logger.info(f"MCP server '{name}' connected")
            except Exception as e:
                logger.error(f"Failed to connect MCP server '{name}': {e}")

    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Chama uma ferramenta em um servidor MCP específico."""
        if server_name not in self.sessions:
            raise RuntimeError(f"MCP server '{server_name}' not connected")

        session = self.sessions[server_name]
        result = await session.call_tool(tool_name, arguments)
        return result

    async def list_tools(self, server_name: str) -> List[Dict[str, Any]]:
        """Lista ferramentas disponíveis em um servidor."""
        if server_name not in self.sessions:
            return []

        session = self.sessions[server_name]
        tools = await session.list_tools()
        return [{"name": t.name, "description": t.description} for t in tools]

    async def disconnect_all(self) -> None:
        """Desconecta de todos os servidores."""
        for name, session in self.sessions.items():
            try:
                await session.close()
            except Exception as e:
                logger.error(f"Error disconnecting '{name}': {e}")
        self.sessions.clear()

    async def _connect_server(self, name: str, config: MCPServerConfig) -> None:
        """Conecta a um servidor MCP individual."""
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        if config.url:
            from mcp.client.streamable_http import streamablehttp_client
            transport = await streamablehttp_client(config.url)
        else:
            server_params = StdioServerParameters(
                command=config.command,
                args=config.args,
                env=config.env
            )
            transport = await stdio_client(server_params)

        read, write = transport[0], transport[1]
        session = ClientSession(read, write)
        await session.initialize()

        self.sessions[name] = session
