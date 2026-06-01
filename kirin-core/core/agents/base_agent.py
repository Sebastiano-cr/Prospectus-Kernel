from __future__ import annotations
from abc import ABC
from enum import Enum
from typing import Any
import httpx
import os
from pydantic import BaseModel, field_validator

MVP_AGENTS_URL = os.environ.get("MVP_AGENTS_URL", "http://agents:8000")


class AgentState(str, Enum):
    IDLE = "IDLE"
    INIT = "INIT"
    OBSERVING = "OBSERVING"
    DECIDING = "DECIDING"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED_INIT = "FAILED_INIT"
    FAILED_OBSERVE = "FAILED_OBSERVE"
    FAILED_DECIDE = "FAILED_DECIDE"
    FAILED_EXECUTE = "FAILED_EXECUTE"
    RECOVERING = "RECOVERING"


STATE_ORDER: dict[AgentState, int] = {
    AgentState.IDLE: 0,
    AgentState.INIT: 1,
    AgentState.OBSERVING: 2,
    AgentState.DECIDING: 3,
    AgentState.EXECUTING: 4,
    AgentState.COMPLETED: 5,
    AgentState.FAILED_INIT: 2,
    AgentState.FAILED_OBSERVE: 3,
    AgentState.FAILED_DECIDE: 4,
    AgentState.FAILED_EXECUTE: 5,
    AgentState.RECOVERING: 4,
}


class InvokeRequest(BaseModel):
    goal: str
    context: dict
    memory_id: str
    mode: str = "autonomous"
    deterministic: bool = False
    tenant_id: str = "default"

    @field_validator("goal")
    @classmethod
    def goal_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("goal não pode ser vazio")
        return v


class InvokeResponse(BaseModel):
    result: Any
    memory_updates: list[dict]
    deterministic: bool
    agent_id: str
    memory_id: str
    status: AgentState


class BaseAgent(ABC):
    _context_key: str = ""
    _action: str = ""
    _data_key: str = ""
    _endpoint: str = ""
    _memory_update_key: str = ""

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        self.state: AgentState = AgentState.IDLE
        self._heartbeat_count: int = 0
        self._context: dict = {}
        self._current_memory_id: str = ""
        self._tenant_id: str = "default"
        self._plugin_loader: Any = None
        self._retries: int = 0

    def transition_to(self, new_state: AgentState) -> None:
        if STATE_ORDER[new_state] < STATE_ORDER[self.state]:
            raise ValueError(
                f"Transição inválida: {self.state} → {new_state} "
                f"(ordem {STATE_ORDER[self.state]} → {STATE_ORDER[new_state]})"
            )
        self.state = new_state

    async def heartbeat(self) -> None:
        self._heartbeat_count += 1

    async def use_tool(self, plugin: str, tool: str, args: dict) -> dict:
        if self._plugin_loader is None:
            raise RuntimeError("PluginLoader não configurado para este Agent")
        return await self._plugin_loader.invoke_tool(
            self.agent_id, getattr(self, "_tenant_id", "default"), plugin, tool, args
        )

    async def _init(self, request: InvokeRequest) -> None:
        if self._context_key:
            setattr(self, f"_{self._context_key}", request.context.get(self._context_key, {}))
        self._current_memory_id = request.memory_id
        self._tenant_id = request.tenant_id
        self._context = request.context

    async def _observe(self, request: InvokeRequest) -> dict:
        if self._context_key:
            return {self._context_key: getattr(self, f"_{self._context_key}")}
        return {}

    async def _decide(self, observation: dict) -> dict:
        if self._action and self._data_key:
            return {"action": self._action, self._data_key: observation[self._data_key], "memory_updates": []}
        return {"action": self._action, "memory_updates": []}

    async def _execute(self, decision: dict) -> Any:
        payload = decision.get(self._data_key, decision) if self._data_key else decision
        return await self._http_post(self._endpoint, payload)

    async def _http_post(self, endpoint: str, payload: Any, timeout: float = 60.0) -> dict:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(f"{MVP_AGENTS_URL}{endpoint}", json=payload)
            resp.raise_for_status()
        return resp.json()
