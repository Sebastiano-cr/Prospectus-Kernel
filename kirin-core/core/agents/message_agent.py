from core.agents.base_agent import BaseAgent


class MessageAgent(BaseAgent):
    _context_key = "lead"
    _action = "generate_message"
    _data_key = "lead"
    _endpoint = "/generate_message"
    _memory_update_key = "generated_message"

    async def _execute(self, decision: dict) -> dict:
        result = await self._http_post(self._endpoint, decision["lead"])
        decision["memory_updates"] = [{self._memory_update_key: result}]
        return result
