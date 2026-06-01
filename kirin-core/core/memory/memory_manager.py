import os
from core.memory.redis_store import RedisStore
from core.memory.postgres_store import PostgresStore
from core.memory.qdrant_store import QdrantStore
from core.engine.state_models import AgentRuntimeState, WorkflowState

DEFAULT_TTL = int(os.environ.get("MEMORY_SHORT_TERM_TTL", 3600))
HEARTBEAT_TIMEOUT = int(os.environ.get("AGENT_HEARTBEAT_TIMEOUT", 300))
MAX_HEARTBEAT_RENEWALS = int(os.environ.get("AGENT_MAX_HEARTBEAT_RENEWALS", 5))


def _key(namespace: str, tenant_id: str, memory_id: str) -> str:
    """Build a namespaced key for Redis."""
    return f"{namespace}:{tenant_id}:{memory_id}"


class MemoryManager:
    def __init__(self, redis: RedisStore, postgres: PostgresStore, qdrant: QdrantStore) -> None:
        self.redis = redis
        self.postgres = postgres
        self.qdrant = qdrant

    async def save_runtime_state(self, state: AgentRuntimeState) -> None:
        await self.redis.set(_key("runtime", state.tenant_id, state.memory_id), state.model_dump())

    async def load_runtime_state(self, memory_id: str, tenant_id: str) -> AgentRuntimeState | None:
        data = await self.redis.get(_key("runtime", tenant_id, memory_id))
        return AgentRuntimeState(**data) if data else None

    async def write_working_memory(self, memory_id: str, tenant_id: str, content: dict) -> None:
        await self.redis.set(_key("working", tenant_id, memory_id), content)

    async def read_working_memory(self, memory_id: str, tenant_id: str) -> dict | None:
        return await self.redis.get(_key("working", tenant_id, memory_id))

    async def append_episodic(self, memory_id: str, tenant_id: str, entry: dict) -> None:
        await self.postgres.append_episodic(memory_id, tenant_id, entry)

    async def write_semantic(self, memory_id: str, tenant_id: str, text: str, metadata: dict) -> None:
        await self.qdrant.upsert(memory_id, tenant_id, text, metadata)

    async def search_semantic(self, tenant_id: str, query: str, limit: int = 5) -> list[dict]:
        return await self.qdrant.search(tenant_id, query, limit)

    async def save_workflow_state(self, state: WorkflowState) -> None:
        await self.postgres.upsert_workflow(state)

    async def load_workflow_state(self, workflow_id: str, tenant_id: str) -> WorkflowState | None:
        return await self.postgres.get_workflow(workflow_id, tenant_id)
