from core.agents.base_agent import BaseAgent


class ResearchAgent(BaseAgent):
    _context_key = "lead"
    _action = "research"
    _data_key = "lead"
    _endpoint = "/research"
    _memory_update_key = "pesquisa"

    async def _execute(self, decision: dict) -> dict:
        result = await self._http_post(self._endpoint, decision["lead"], timeout=120.0)
        decision["memory_updates"] = [{self._memory_update_key: result}]
        return result
