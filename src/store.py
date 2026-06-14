"""
ChromaStore — Unified storage for Kirin using ChromaDB.
Replaces PostgreSQL + Qdrant + Redis with a single vector database.
"""

import json
import logging
import uuid
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from collections import OrderedDict

import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)


class ChromaStore:
    """
    Unified storage layer backed by ChromaDB.
    Handles: persistence, vector search, metadata filtering, caching.
    """

    def __init__(self, path: str = "./data/chroma", collection_prefix: str = "kirin_"):
        self._path = path
        self._prefix = collection_prefix
        self._client: Optional[chromadb.Client] = None
        self._collections: Dict[str, chromadb.Collection] = {}
        self._cache: OrderedDict = OrderedDict()
        self._cache_ttl: Dict[str, float] = {}
        self._cache_max = 1000
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return
        try:
            self._client = chromadb.PersistentClient(
                path=self._path,
                settings=Settings(anonymized_telemetry=False),
            )
            logger.info(f"ChromaStore initialized at {self._path}")
            self._initialized = True
        except Exception as e:
            logger.error(f"Failed to initialize ChromaStore: {e}")
            raise

    async def ready(self) -> bool:
        """Probe de saúde — tenta uma query real no ChromaDB."""
        if not self._initialized or not self._client:
            return False
        try:
            coll = self._collection("_health")
            coll.count()
            return True
        except Exception as e:
            logger.warning(f"Health probe failed: {e}")
            self._initialized = False
            return False

    async def shutdown(self) -> None:
        self._collections.clear()
        self._cache.clear()
        self._cache_ttl.clear()
        self._client = None
        self._initialized = False
        logger.info("ChromaStore shut down")

    def _collection(self, name: str) -> chromadb.Collection:
        coll_name = f"{self._prefix}{name}"
        if coll_name not in self._collections:
            self._collections[coll_name] = self._client.get_or_create_collection(
                name=coll_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collections[coll_name]

    # ─── Lead Memory ─────────────────────────────────────────────────────

    async def store_lead_memory(
        self, lead_id: str, memory_type: str, data: Dict[str, Any]
    ) -> bool:
        try:
            coll = self._collection("leads")
            doc_id = f"{lead_id}:{memory_type}"
            metadata = {
                "lead_id": lead_id,
                "memory_type": memory_type,
                "stored_at": datetime.now(timezone.utc).isoformat(),
            }
            coll.upsert(
                ids=[doc_id],
                documents=[json.dumps(data)],
                metadatas=[metadata],
            )
            return True
        except Exception as e:
            logger.error(f"Failed to store lead memory {lead_id}:{memory_type}: {e}")
            return False

    async def retrieve_lead_memory(
        self, lead_id: str, memory_type: str
    ) -> Optional[Dict[str, Any]]:
        try:
            coll = self._collection("leads")
            doc_id = f"{lead_id}:{memory_type}"
            results = coll.get(ids=[doc_id])
            if results and results["documents"]:
                return json.loads(results["documents"][0])
            return None
        except Exception as e:
            logger.error(f"Failed to retrieve lead memory {lead_id}:{memory_type}: {e}")
            return None

    async def delete_lead_memory(self, lead_id: str, memory_type: str) -> bool:
        try:
            coll = self._collection("leads")
            doc_id = f"{lead_id}:{memory_type}"
            coll.delete(ids=[doc_id])
            return True
        except Exception as e:
            logger.error(f"Failed to delete lead memory {lead_id}:{memory_type}: {e}")
            return False

    async def search_by_text(
        self, namespace: str, query: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        try:
            coll = self._collection("leads")
            # Use ChromaDB's text search via embedding
            results = coll.query(
                query_texts=[query],
                n_results=limit,
                where={"memory_type": namespace},
            )
            docs = []
            if results and results["documents"]:
                for i, doc in enumerate(results["documents"][0]):
                    data = json.loads(doc)
                    if results["metadatas"] and results["metadatas"][0]:
                        data["_score"] = results["distances"][0][i] if results["distances"] else 0
                    docs.append(data)
            return docs
        except Exception as e:
            logger.warning(f"Text search failed for {namespace}: {e}")
            return []

    # ─── Structured Storage (namespace/key) ──────────────────────────────

    async def store(self, namespace: str, key: str, data: Dict[str, Any]) -> bool:
        return await self.store_lead_memory(key, namespace, data)

    async def retrieve(self, namespace: str, key: str) -> Optional[Dict[str, Any]]:
        return await self.retrieve_lead_memory(key, namespace)

    async def delete(self, namespace: str, key: str) -> bool:
        return await self.delete_lead_memory(key, namespace)

    # ─── Vector Search ───────────────────────────────────────────────────

    async def store_text(
        self,
        collection_name: str,
        text: str,
        payload: Dict[str, Any],
        point_id: Optional[int] = None,
    ) -> bool:
        try:
            coll = self._collection(collection_name)
            doc_id = str(point_id or uuid.uuid4().hex[:16])
            metadata = {k: str(v) if isinstance(v, (list, dict)) else v for k, v in payload.items()}
            coll.upsert(
                ids=[doc_id],
                documents=[text],
                metadatas=[metadata],
            )
            return True
        except Exception as e:
            logger.warning(f"Failed to store text in {collection_name}: {e}")
            return False

    async def search_text(
        self, collection_name: str, query: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        try:
            coll = self._collection(collection_name)
            results = coll.query(
                query_texts=[query],
                n_results=limit,
            )
            docs = []
            if results and results["documents"]:
                for i, doc in enumerate(results["documents"][0]):
                    entry = {"text": doc}
                    if results["metadatas"] and results["metadatas"][0]:
                        entry.update(results["metadatas"][0][i])
                    if results["distances"]:
                        entry["score"] = results["distances"][0][i]
                    docs.append(entry)
            return docs
        except Exception as e:
            logger.warning(f"Text search failed in {collection_name}: {e}")
            return []

    # ─── Cache (in-memory, LRU) ─────────────────────────────────────────

    async def cache_get(self, key: str) -> Optional[Any]:
        self._evict_expired()
        if key in self._cache:
            if time.time() < self._cache_ttl.get(key, 0):
                self._cache.move_to_end(key)
                return self._cache[key]
            else:
                del self._cache[key]
                self._cache_ttl.pop(key, None)
        return None

    async def cache_set(self, key: str, value: Any, ttl_seconds: int = 3600) -> bool:
        if len(self._cache) >= self._cache_max:
            self._cache.popitem(last=False)
        self._cache[key] = value
        self._cache.move_to_end(key)
        self._cache_ttl[key] = time.time() + ttl_seconds
        return True

    async def cache_delete(self, key: str) -> bool:
        self._cache.pop(key, None)
        self._cache_ttl.pop(key, None)
        return True

    def _evict_expired(self):
        now = time.time()
        expired = [k for k, t in self._cache_ttl.items() if now >= t]
        for k in expired:
            self._cache.pop(k, None)
            self._cache_ttl.pop(k, None)

    # ─── Conversation Context (uses cache with lead_id prefix) ──────────

    async def store_conversation_context(
        self, lead_id: str, context: Dict[str, Any], ttl: int = 3600
    ) -> bool:
        return await self.cache_set(f"ctx:{lead_id}", context, ttl)

    async def retrieve_conversation_context(self, lead_id: str) -> Optional[Dict[str, Any]]:
        return await self.cache_get(f"ctx:{lead_id}")

    # ─── Dedup (used by discourse_ingestor) ──────────────────────────────

    async def check_duplicate(self, key: str) -> bool:
        cached = await self.cache_get(f"dedup:{key}")
        return cached is not None

    async def store_dedup(self, key: str, value: Any, ttl: int = 86400) -> None:
        await self.cache_set(f"dedup:{key}", value, ttl)

    async def get_dedup(self, key: str) -> Optional[Any]:
        return await self.cache_get(f"dedup:{key}")
