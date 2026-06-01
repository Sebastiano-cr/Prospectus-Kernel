from __future__ import annotations
import asyncio
import os
from typing import TYPE_CHECKING, Any

from core.agents.base_agent import AgentState, BaseAgent, InvokeRequest, InvokeResponse
from core.engine.snapshot import serialize_runtime_state, restore_runtime_state
from core.engine.state_models import AgentRuntimeState

if TYPE_CHECKING:
    from core.memory.memory_manager import MemoryManager

HEARTBEAT_TIMEOUT = int(os.environ.get("AGENT_HEARTBEAT_TIMEOUT", 300))
MAX_HEARTBEAT_RENEWALS = int(os.environ.get("AGENT_MAX_HEARTBEAT_RENEWALS", 5))


class ConflictError(Exception):
    pass


class ExecutionEngine:
    def __init__(self, memory_manager: MemoryManager) -> None:
        self.memory_manager = memory_manager
        self._active: dict[str, BaseAgent] = {}

    async def run(self, agent: BaseAgent, request: InvokeRequest) -> InvokeResponse:
        memory_id = request.memory_id

        if memory_id in self._active:
            raise ConflictError(f"Agent já em execução para memory_id={memory_id}")

        self._active[memory_id] = agent
        try:
            await self.memory_manager.read_working_memory(memory_id, request.tenant_id)

            agent.transition_to(AgentState.INIT)
            await agent._init(request)
            await self.persist_snapshot(agent, memory_id, request.tenant_id)

            agent.transition_to(AgentState.OBSERVING)
            observation = await agent._observe(request)
            await self.persist_snapshot(agent, memory_id, request.tenant_id)

            agent.transition_to(AgentState.DECIDING)
            decision = await agent._decide(observation)
            await self.persist_snapshot(agent, memory_id, request.tenant_id)

            agent.transition_to(AgentState.EXECUTING)
            renewals = 0
            while True:
                try:
                    result = await asyncio.wait_for(
                        agent._execute(decision),
                        timeout=HEARTBEAT_TIMEOUT,
                    )
                    break
                except asyncio.TimeoutError:
                    if agent._heartbeat_count > renewals and renewals < MAX_HEARTBEAT_RENEWALS:
                        renewals = agent._heartbeat_count
                        continue
                    agent.transition_to(AgentState.FAILED_EXECUTE)
                    await self.persist_snapshot(agent, memory_id, request.tenant_id)
                    raise TimeoutError(
                        f"Agent timeout após {HEARTBEAT_TIMEOUT * (renewals + 1)}s"
                    )

            agent.transition_to(AgentState.COMPLETED)
            memory_updates = decision.get("memory_updates", [])
            for update in memory_updates:
                await self.memory_manager.write_working_memory(
                    memory_id, request.tenant_id, update
                )
            await self.persist_snapshot(agent, memory_id, request.tenant_id)

            return InvokeResponse(
                result=result,
                memory_updates=memory_updates,
                deterministic=request.deterministic,
                agent_id=agent.agent_id,
                memory_id=memory_id,
                status=AgentState.COMPLETED,
            )
        except Exception as exc:
            if agent.state == AgentState.INIT:
                agent.transition_to(AgentState.FAILED_INIT)
            elif agent.state == AgentState.OBSERVING:
                agent.transition_to(AgentState.FAILED_OBSERVE)
            elif agent.state == AgentState.DECIDING:
                agent.transition_to(AgentState.FAILED_DECIDE)
            elif agent.state not in (
                AgentState.FAILED_INIT,
                AgentState.FAILED_OBSERVE,
                AgentState.FAILED_DECIDE,
                AgentState.FAILED_EXECUTE,
            ):
                agent.transition_to(AgentState.FAILED_EXECUTE)
            await self.persist_snapshot(agent, memory_id, request.tenant_id)
            raise
        finally:
            self._active.pop(memory_id, None)

    async def persist_snapshot(self, agent: BaseAgent, memory_id: str, tenant_id: str) -> None:
        state = serialize_runtime_state(agent)
        await self.memory_manager.save_runtime_state(state)

    async def restore_from_snapshot(self, memory_id: str, tenant_id: str) -> dict | None:
        state = await self.memory_manager.load_runtime_state(memory_id, tenant_id)
        if state is None:
            return None
        return restore_runtime_state(state)

    async def renew_heartbeat(self, memory_id: str) -> None:
        agent = self._active.get(memory_id)
        if agent:
            await agent.heartbeat()

    async def restore_executing_agents(self) -> None:
        try:
            rows = await self.memory_manager.postgres.query_executing_snapshots()
            for row in rows:
                await self.memory_manager.postgres.update_snapshot_state(
                    row["memory_id"], AgentState.RECOVERING
                )
        except Exception:
            pass
