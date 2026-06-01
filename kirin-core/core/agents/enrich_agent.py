from typing import Any
from core.agents.base_agent import BaseAgent


class EnrichAgent(BaseAgent):
    _context_key = "lead"
    _action = "enrich"
    _data_key = "lead"
    _endpoint = "/enrich"
    _memory_update_key = "dossie"

    async def _execute(self, decision: dict) -> Any:
        result = await self._http_post(self._endpoint, decision["lead"])
        decision["memory_updates"] = [{self._memory_update_key: result}]
        return result
