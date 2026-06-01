from datetime import datetime
from pydantic import BaseModel
from core.agents.base_agent import AgentState


class AgentRuntimeState(BaseModel):
    memory_id: str
    agent_id: str
    tenant_id: str
    current_phase: AgentState
    retries: int = 0
    heartbeat_count: int = 0
    current_task: str | None = None
    execution_pointer: str | None = None
    timeout_deadline: datetime | None = None
    created_at: datetime
    updated_at: datetime


class WorkflowState(BaseModel):
    workflow_id: str
    tenant_id: str
    completed_tasks: list[str] = []
    failed_tasks: list[str] = []
    retry_counts: dict[str, int] = {}
    approval_gates: dict[str, str] = {}
    execution_graph: dict = {}
    status: str = "running"
    created_at: datetime
    updated_at: datetime
