from typing import Any


class QdrantStore:
    def __init__(self, qdrant_url: str) -> None:
        self._url = qdrant_url

    async def upsert(self, memory_id: str, tenant_id: str, text: str, metadata: dict) -> None:
        pass

    async def search(self, tenant_id: str, query: str, limit: int = 5) -> list[dict]:
        return []
