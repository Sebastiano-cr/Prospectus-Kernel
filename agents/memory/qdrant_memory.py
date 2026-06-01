"""
Qdrant memory manager for vector storage and similarity search.
"""
from typing import Dict, Any, Optional, List
from qdrant_client import QdrantClient
from qdrant_client.http import models
import logging
import numpy as np
from .base import BaseMemoryManager

logger = logging.getLogger(__name__)


class QdrantMemoryManager(BaseMemoryManager):
    """
    Qdrant-based memory manager for storing and searching vector embeddings.

    All direct Qdrant client access is private (_client). Use store_* and search_* methods.
    """

    def __init__(self, host: str, port: int, embedding_router: Optional["EmbeddingRouter"] = None):
        self.host = host
        self.port = port
        self._client: Optional[QdrantClient] = None
        self.embedding_router = embedding_router

    @property
    def client(self) -> Optional[QdrantClient]:
        """Direct Qdrant client access (internal use only). Prefer store_* and search_* methods."""
        return self._client

    async def initialize(self) -> None:
        """Initialize the Qdrant client and ensure collections exist."""
        try:
            self._client = QdrantClient(host=self.host, port=self.port)

            # Determine vector size and distance from router, or use defaults
            if self.embedding_router and self.embedding_router.active:
                vector_size = self.embedding_router.active.dimensions()
                distance_metric = self.embedding_router.active.distance_metric()
                distance = self._parse_distance(distance_metric)
            else:
                vector_size = 1536
                distance = models.Distance.COSINE

            # Ensure collections for different memory types exist
            memory_types = ["enrichment", "scoring", "messaging", "research", "discourse"]
            for memory_type in memory_types:
                if self.embedding_router:
                    collection_name = self.embedding_router.get_collection_name(memory_type)
                else:
                    collection_name = f"kirin_{memory_type}"

                try:
                    self._client.get_collection(collection_name=collection_name)
                except Exception:
                    self._client.create_collection(
                        collection_name=collection_name,
                        vectors_config=models.VectorParams(
                            size=vector_size,
                            distance=distance
                        )
                    )
                    logger.info(f"Created Qdrant collection: {collection_name} (dim={vector_size}, metric={distance_metric})")

            logger.info("Qdrant memory manager initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Qdrant memory manager: {e}")
            raise
    
    def _parse_distance(self, metric: str) -> models.Distance:
        """Converte string de metrica para enum do Qdrant."""
        if metric == "euclidean":
            return models.Distance.EUCLID
        elif metric == "dot":
            return models.Distance.DOT
        else:
            return models.Distance.COSINE
    
    def _get_collection_name(self, memory_type: str) -> str:
        """Retorna o nome da collection baseado no router ou padrao."""
        if self.embedding_router:
            return self.embedding_router.get_collection_name(memory_type)
        return f"kirin_{memory_type}"
    
    async def _generate_embedding(self, text: str) -> Optional[List[float]]:
        """Gera embedding para um texto usando o router.
        Se nao tiver router, retorna None (usara placeholder).
        """
        if not self.embedding_router or not self.embedding_router.active:
            return None
        try:
            vectors = await self.embedding_router.embed([text])
            return vectors[0] if vectors else None
        except Exception as e:
            logger.warning(f"Embedding generation failed: {e}")
            return None
    
    async def shutdown(self) -> None:
        """Close the Qdrant client connection."""
        if self._client:
            self._client.close()
            logger.info("Qdrant memory manager shutdown")

    async def store_lead_memory(self, lead_id: str, memory_type: str, data: Dict[str, Any]) -> bool:
        """
        Store memory associated with a lead.
        """
        try:
            # Determine the embedding
            if "embedding" in data:
                embedding = data["embedding"]
                payload = {k: v for k, v in data.items() if k != "embedding"}
            else:
                text_to_embed = str(data.get("text", "") or data.get("resumo_perfil", "") or lead_id)
                embedding = await self._generate_embedding(text_to_embed)
                payload = dict(data)

            if embedding is None:
                logger.warning(f"No embedding available for {lead_id}:{memory_type}, using placeholder")
                embedding = list(np.random.uniform(-1.0, 1.0, size=1536))

            payload["lead_id"] = lead_id
            payload["memory_type"] = memory_type

            point_id = hash(f"{lead_id}_{memory_type}") % (2**63)

            self._client.upsert(
                collection_name=self._get_collection_name(memory_type),
                points=[
                    models.PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload=payload
                    )
                ]
            )
            return True
        except Exception as e:
            logger.error(f"Failed to store lead memory in Qdrant for {lead_id}: {e}")
            return False

    async def store_lead_memory_with_text(
        self,
        lead_id: str,
        memory_type: str,
        text: str,
        payload: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Store memory, generating embedding from text."""
        data = payload or {}
        embedding = await self._generate_embedding(text)
        if embedding:
            data["embedding"] = embedding
        data["text"] = text
        return await self.store_lead_memory(lead_id, memory_type, data)

    async def retrieve_lead_memory(self, lead_id: str, memory_type: str) -> Optional[Dict[str, Any]]:
        """Retrieve memory associated with a lead by ID."""
        try:
            results = self._client.scroll(
                collection_name=self._get_collection_name(memory_type),
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="lead_id",
                            match=models.MatchValue(value=lead_id)
                        ),
                        models.FieldCondition(
                            key="memory_type",
                            match=models.MatchValue(value=memory_type)
                        )
                    ]
                ),
                limit=1
            )

            points = results[0]
            if points:
                point = points[0]
                data = point.payload.copy()
                if "embedding" not in data and hasattr(point, 'vector'):
                    data["embedding"] = point.vector
                return data
            return None
        except Exception as e:
            logger.error(f"Failed to retrieve lead memory from Qdrant for {lead_id}: {e}")
            return None

    async def search_similar_memories(
        self,
        query_vector: List[float],
        memory_type: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search for memories similar to a query vector."""
        try:
            results = self._client.search(
                collection_name=self._get_collection_name(memory_type),
                query_vector=query_vector,
                limit=limit
            )

            memories = []
            for result in results:
                payload = result.payload.copy()
                if "embedding" not in payload:
                    payload["embedding"] = result.vector
                memories.append(payload)

            return memories
        except Exception as e:
            logger.error(f"Failed to search similar memories in Qdrant: {e}")
            return []

    async def search_similar_by_text(
        self,
        query_text: str,
        memory_type: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search by text similarity using embedding router."""
        embedding = await self._generate_embedding(query_text)
        if embedding is None:
            logger.warning("Cannot search by text: no embedding router available")
            return []
        return await self.search_similar_memories(embedding, memory_type, limit)

    # ─── Store text with automatic embedding ──────────────────────────────────

    async def store_text(
        self,
        collection_name: str,
        text: str,
        payload: Optional[Dict[str, Any]] = None,
        point_id: Optional[int] = None
    ) -> bool:
        """Store text with automatic embedding generation."""
        try:
            embedding = await self._generate_embedding(text)
            if embedding is None:
                logger.warning("Cannot store text: no embedding router available")
                return False

            data = payload or {}
            data["text"] = text

            if point_id is None:
                point_id = abs(hash(text)) % (2**63)

            self._client.upsert(
                collection_name=collection_name,
                points=[
                    models.PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload=data
                    )
                ]
            )
            return True
        except Exception as e:
            logger.error(f"Failed to store text in Qdrant: {e}")
            return False

    async def search_text(
        self,
        collection_name: str,
        query: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search by text using embedding similarity."""
        return await self.search_similar_by_text(query, collection_name, limit)

    # ─── Abstract methods from BaseMemoryManager ──────────────────────────────

    async def cache_get(self, key: str) -> Optional[Any]:
        """Qdrant doesn't support key-value cache. Returns None."""
        logger.warning("Qdrant does not support key-value cache. Use Redis.")
        return None

    async def cache_set(self, key: str, value: Any, ttl_seconds: int = 3600) -> bool:
        """Qdrant doesn't support key-value cache."""
        logger.warning("Qdrant does not support key-value cache. Use Redis.")
        return False

    async def cache_delete(self, key: str) -> bool:
        """Qdrant doesn't support key-value cache."""
        logger.warning("Qdrant does not support key-value cache. Use Redis.")
        return False

    async def store(self, namespace: str, key: str, data: Dict[str, Any]) -> bool:
        """Store structured data as vector point with payload."""
        return await self.store_text(namespace, key, data)

    async def retrieve(self, namespace: str, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve by key from vector store."""
        try:
            results = self._client.scroll(
                collection_name=namespace,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="text",
                            match=models.MatchValue(value=key)
                        )
                    ]
                ),
                limit=1
            )
            points = results[0]
            if points:
                return points[0].payload
            return None
        except Exception as e:
            logger.error(f"Failed to retrieve from Qdrant {namespace}:{key}: {e}")
            return None

    async def delete(self, namespace: str, key: str) -> bool:
        """Delete from vector store."""
        try:
            point_id = abs(hash(key)) % (2**63)
            self._client.delete(
                collection_name=namespace,
                points_selector=models.PointIdsList(points=[point_id])
            )
            return True
        except Exception as e:
            logger.error(f"Failed to delete from Qdrant {namespace}:{key}: {e}")
            return False

    async def search_by_text(self, namespace: str, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search by text using embedding similarity."""
        return await self.search_text(namespace, query, limit)

    async def store_conversation_context(self, lead_id: str, context: Dict[str, Any], ttl: int = 3600) -> bool:
        raise NotImplementedError("Short-term context with TTL requires Redis memory manager")

    async def retrieve_conversation_context(self, lead_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError("Short-term context retrieval requires Redis memory manager")


# Import for type hint
from .embedding_router import EmbeddingRouter
