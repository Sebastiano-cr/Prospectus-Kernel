from typing import Any


class PostgresStore:
    def __init__(self, postgres_url: str) -> None:
        self._url = postgres_url
        self._facts: dict[str, dict] = {}
        self._episodic: dict[str, list[dict]] = {}
        self._snapshots: list[dict] = []

    async def get_facts(self, memory_id: str, tenant_id: str) -> dict | None:
        key = f"{tenant_id}:{memory_id}"
        return self._facts.get(key)

    async def append_episodic(self, memory_id: str, tenant_id: str, entry: dict) -> None:
        key = f"{tenant_id}:{memory_id}"
        if key not in self._episodic:
            self._episodic[key] = []
        self._episodic[key].append(entry)

    async def upsert_workflow(self, state: Any) -> None:
        pass

    async def get_workflow(self, workflow_id: str, tenant_id: str) -> Any | None:
        return None

    async def query_executing_snapshots(self) -> list[dict]:
        return [s for s in self._snapshots if s.get("state") in ("EXECUTING", "RECOVERING")]

    async def update_snapshot_state(self, memory_id: str, state: Any) -> None:
        for s in self._snapshots:
            if s.get("memory_id") == memory_id:
                s["state"] = state if isinstance(state, str) else state.value
