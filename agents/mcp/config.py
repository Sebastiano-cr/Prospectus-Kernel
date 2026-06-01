"""
MCP Configuration -- Configuração dos servidores MCP do Kirin.
"""
from .orchestrator import MCPServerConfig

MCP_SERVERS = [
    MCPServerConfig(
        name="scraper",
        command="python",
        args=["-m", "mcp_server.server"],
        env={"PLAYWRIGHT_BROWSERS_PATH": "/home/vector/.cache/ms-playwright"}
    ),
    MCPServerConfig(
        name="agentmemory",
        command="npx",
        args=["-y", "@agentmemory/agentmemory"],
    ),
    MCPServerConfig(
        name="chrome-devtools",
        command="npx",
        args=["-y", "chrome-devtools-mcp@latest"],
    ),
    MCPServerConfig(
        name="whisper",
        url="http://whisper-service:8080/mcp",
    ),
    MCPServerConfig(
        name="moneyprinter",
        url="http://moneyprinter:8080/mcp",
    ),
]
