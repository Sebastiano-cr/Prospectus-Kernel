from datetime import datetime, timezone
from core.engine.state_models import AgentRuntimeState
from core.agents.base_agent import AgentState, BaseAgent


def serialize_runtime_state(agent: BaseAgent) -> AgentRuntimeState:
    return AgentRuntimeState(
        memory_id=agent._current_memory_id,
        agent_id=agent.agent_id,
        tenant_id=agent._tenant_id,
        current_phase=agent.state,
        retries=getattr(agent, "_retries", 0),
        heartbeat_count=agent._heartbeat_count,
        execution_pointer=agent.state.value,
        timeout_deadline=getattr(agent, "_timeout_deadline", None),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def restore_runtime_state(state: AgentRuntimeState) -> dict:
    return state.model_dump()
