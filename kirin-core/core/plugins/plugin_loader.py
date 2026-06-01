from core.governance.policy_engine import PolicyEngine


class PluginLoader:
    def __init__(self, policy: PolicyEngine | None = None) -> None:
        self._loaded: dict[str, str] = {}
        self._policy = policy

    async def load(self, name: str, version: str) -> None:
        if name in self._loaded:
            return
        await self._validate_mcp_schema(name, version)
        self._loaded[name] = version

    async def invoke_tool(
        self, agent_id: str, tenant_id: str, plugin: str, tool: str, args: dict
    ) -> dict:
        if self._policy:
            await self._policy.check_tool_permission(agent_id, tenant_id, plugin, tool)
        if plugin not in self._loaded:
            raise ValueError(f"Plugin '{plugin}' não carregado")
        try:
            return await self._dispatch(plugin, tool, args)
        except Exception as exc:
            return {"error": str(exc), "plugin": plugin, "tool": tool}

    async def _validate_mcp_schema(self, name: str, version: str) -> None:
        pass

    async def _dispatch(self, plugin: str, tool: str, args: dict) -> dict:
        dispatchers = {
            "crm": self._call_crm,
            "whatsapp": self._call_whatsapp,
            "vectordb": self._call_vectordb,
        }
        fn = dispatchers.get(plugin)
        if fn is None:
            raise ValueError(f"Plugin desconhecido: {plugin}")
        return await fn(tool, args)

    async def _call_crm(self, tool: str, args: dict) -> dict:
        return {"status": "stub"}

    async def _call_whatsapp(self, tool: str, args: dict) -> dict:
        return {"status": "stub"}

    async def _call_vectordb(self, tool: str, args: dict) -> dict:
        return {"status": "stub"}
