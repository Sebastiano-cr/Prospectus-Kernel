"""
Embedding Router --- Harness de Estrategias de Embedding para o Kirin Cognitive Runtime.

Layered Architecture:
  Layer 0: EmbeddingStrategy (ABC) - interface de toda strategy
  Layer 1: Strategies concretas - SentenceTransformers, OpenAI, Multimodal, GraphRAG
  Layer 2: EmbeddingRouter - gerencia ativacao e troca em tempo de execucao

Cada strategy e um "harness" que pode ser trocado sem modificar o resto do sistema.
Invariante I-Embed-1: mesma strategy + mesmo texto = mesmo vetor (determinismo).
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
import logging
import os
import httpx

logger = logging.getLogger(__name__)


class EmbeddingStrategy(ABC):
    """Interface abstrata para estrategias de embedding."""
    
    @abstractmethod
    def dimensions(self) -> int:
        """Dimensao do vetor de embedding produzido."""
        ...
    
    @abstractmethod
    def distance_metric(self) -> str:
        """Metrica de distancia: cosine, euclidean, dot."""
        ...
    
    @abstractmethod
    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Converte textos em vetores de embedding."""
        ...
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Nome identificador da strategy."""
        ...
    
    @abstractmethod
    async def validate(self) -> bool:
        """Valida se a strategy esta operacional."""
        ...


class SentenceTransformersStrategy(EmbeddingStrategy):
    """
    Harness 1: sentence-transformers local (384d all-MiniLM-L6-v2).
    Roda local, sem custo de API, determinismo garantido.
    """
    def __init__(self, model_name: str = None):
        self.model_name = model_name or os.getenv("SENTENCE_TRANSFORMERS_MODEL", "all-MiniLM-L6-v2")
        self._model = None
        self._dimensions = 384
    
    @property
    def name(self) -> str:
        return f"sentence-transformers-{self.model_name}"
    
    def dimensions(self) -> int:
        return self._dimensions
    
    def distance_metric(self) -> str:
        return "cosine"
    
    async def validate(self) -> bool:
        try:
            await self._lazy_load()
            return self._model is not None
        except Exception as e:
            logger.warning(f"SentenceTransformers validate failed: {e}")
            return False
    
    async def _lazy_load(self):
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
            import asyncio
            def _load():
                model = SentenceTransformer(self.model_name)
                dim = model.get_sentence_embedding_dimension()
                return model, dim
            self._model, self._dimensions = await asyncio.to_thread(_load)
            logger.info(f"SentenceTransformers loaded: {self.model_name} (dim={self._dimensions})")
        except ImportError:
            logger.error("sentence-transformers not installed. pip install sentence-transformers")
            raise
        except Exception as e:
            logger.error(f"Failed to load SentenceTransformer model: {e}")
            raise
    
    async def embed(self, texts: List[str]) -> List[List[float]]:
        await self._lazy_load()
        import asyncio
        def _encode():
            embeddings = self._model.encode(texts, show_progress_bar=False)
            return [emb.tolist() for emb in embeddings]
        return await asyncio.to_thread(_encode)


class OpenAITextEmbeddingStrategy(EmbeddingStrategy):
    """
    Harness 2: OpenAI API (3072d text-embedding-3-large).
    Alta qualidade, custo por token, depende de API externa.
    """
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model = model or os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")
        self._dimensions = 3072
        self._client = None
    
    @property
    def name(self) -> str:
        return f"openai-{self.model}"
    
    def dimensions(self) -> int:
        return self._dimensions
    
    def distance_metric(self) -> str:
        return "cosine"
    
    async def validate(self) -> bool:
        return bool(self.api_key)
    
    async def _lazy_load(self):
        if self._client is not None:
            return
        try:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=self.api_key)
        except ImportError:
            logger.error("openai not installed. pip install openai")
            raise
    
    async def embed(self, texts: List[str]) -> List[List[float]]:
        await self._lazy_load()
        response = await self._client.embeddings.create(model=self.model, input=texts)
        vectors = [item.embedding for item in response.data]
        self._dimensions = len(vectors[0]) if vectors else self._dimensions
        return vectors


class LiteLLMEmbeddingStrategy(EmbeddingStrategy):
    """
    Harness 3: Embedding via LiteLLM (qualquer provedor suportado).
    Reusa a infraestrutura existente de LiteLLM do Kirin.
    """
    def __init__(self, litellm_url: str = None, model: str = None):
        self.litellm_url = litellm_url or os.getenv("LITELLM_URL", "http://litellm:4000")
        self.model = model or os.getenv("LITELLM_EMBEDDING_MODEL", "text-embedding-ada-002")
        self._dimensions = 1536
    
    @property
    def name(self) -> str:
        return f"litellm-{self.model}"
    
    def dimensions(self) -> int:
        return self._dimensions
    
    def distance_metric(self) -> str:
        return "cosine"
    
    async def validate(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.litellm_url}/health")
                return resp.status_code == 200
        except Exception:
            return False
    
    async def embed(self, texts: List[str]) -> List[List[float]]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.litellm_url}/v1/embeddings",
                json={"model": self.model, "input": texts}
            )
            response.raise_for_status()
            result = response.json()
            vectors = [item["embedding"] for item in result["data"]]
            self._dimensions = len(vectors[0]) if vectors else self._dimensions
            return vectors


class GraphRAGStrategy(EmbeddingStrategy):
    """
    Harness 4: GraphRAG - travessia de grafo em PostgreSQL.
    Nao produz embeddings - armazena tripletas (sujeito, relacao, objeto).
    Invariante I-Graph-1: tripletas sao unicas na tabela.
    Invariante I-Graph-2: mesma query = mesmo caminho.
    """
    def __init__(self, postgres_config: Dict[str, Any] = None):
        self.config = postgres_config or {}
        self._dimensions = 768
    
    @property
    def name(self) -> str:
        return "graphrag-postgresql"
    
    def dimensions(self) -> int:
        return self._dimensions
    
    def distance_metric(self) -> str:
        return "dot"
    
    async def validate(self) -> bool:
        try:
            await self._ensure_tables()
            return True
        except Exception as e:
            logger.warning(f"GraphRAG validate failed: {e}")
            return False
    
    async def _ensure_tables(self):
        import asyncio
        import pg8000
        def _create():
            conn = pg8000.connect(
                host=self.config.get("host", "localhost"),
                port=self.config.get("port", 5432),
                database=self.config.get("database", "kirin"),
                user=self.config.get("user", "kirin"),
                password=self.config.get("password", "")
            )
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS knowledge_graph (
                            id SERIAL PRIMARY KEY,
                            subject VARCHAR(500) NOT NULL,
                            relation VARCHAR(200) NOT NULL,
                            object TEXT NOT NULL,
                            source VARCHAR(100),
                            confidence REAL DEFAULT 1.0,
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                            UNIQUE(subject, relation, object)
                        )
                    """)
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_kg_subject ON knowledge_graph (subject)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_kg_object ON knowledge_graph (object)")
                    conn.commit()
            finally:
                conn.close()
        await asyncio.to_thread(_create)
    
    async def store_triplet(self, subject: str, relation: str, obj: str, source: str = "", confidence: float = 1.0) -> bool:
        import asyncio
        import pg8000
        def _store():
            conn = pg8000.connect(
                host=self.config.get("host", "localhost"),
                port=self.config.get("port", 5432),
                database=self.config.get("database", "kirin"),
                user=self.config.get("user", "kirin"),
                password=self.config.get("password", "")
            )
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO knowledge_graph (subject, relation, object, source, confidence) "
                        "VALUES (%s, %s, %s, %s, %s) "
                        "ON CONFLICT (subject, relation, object) "
                        "DO UPDATE SET confidence = EXCLUDED.confidence, source = EXCLUDED.source",
                        (subject, relation, obj, source, confidence)
                    )
                    conn.commit()
                return True
            except Exception as e:
                logger.error(f"GraphRAG store_triplet failed: {e}")
                return False
            finally:
                conn.close()
        return await asyncio.to_thread(_store)
    
    async def traverse(self, subject: str, relation: str = None, max_depth: int = 2) -> List[Dict[str, Any]]:
        import asyncio
        import pg8000
        def _traverse():
            conn = pg8000.connect(
                host=self.config.get("host", "localhost"),
                port=self.config.get("port", 5432),
                database=self.config.get("database", "kirin"),
                user=self.config.get("user", "kirin"),
                password=self.config.get("password", "")
            )
            try:
                results = []
                visited = set()
                queue = [(subject, 0)]
                while queue and len(results) < 100:
                    current, depth = queue.pop(0)
                    if current in visited or depth > max_depth:
                        continue
                    visited.add(current)
                    with conn.cursor() as cur:
                        if relation:
                            cur.execute(
                                "SELECT subject, relation, object, source, confidence FROM knowledge_graph "
                                "WHERE subject = %s AND relation = %s ORDER BY confidence DESC LIMIT 20",
                                (current, relation)
                            )
                        else:
                            cur.execute(
                                "SELECT subject, relation, object, source, confidence FROM knowledge_graph "
                                "WHERE subject = %s ORDER BY confidence DESC LIMIT 20",
                                (current,)
                            )
                        for row in cur.fetchall():
                            triplet = {
                                "subject": row[0],
                                "relation": row[1],
                                "object": row[2],
                                "source": row[3],
                                "confidence": row[4],
                                "depth": depth
                            }
                            results.append(triplet)
                            if depth + 1 <= max_depth:
                                queue.append((row[2], depth + 1))
                return results
            finally:
                conn.close()
        return await asyncio.to_thread(_traverse)
    
    async def embed(self, texts: List[str]) -> List[List[float]]:
        logger.warning("GraphRAGStrategy.embed() retorna placeholder. Use store_triplet() e traverse().")
        return [[0.0] * self._dimensions for _ in texts]




class MultimodalVisionStrategy(EmbeddingStrategy):
    """
    Harness 5: Embedding multimodal (texto + imagem) via Qwen VL Max.

    Estrategia: extrai descricao textual da imagem via Qwen VL Max,
    depois embeda o texto resultante com uma text_strategy.

    Vantagens: permite busca multimodal sem modelo dedicado.
    Uso: combine com SentenceTransformersStrategy para busca de imagens.
    """
    def __init__(self, text_strategy: EmbeddingStrategy, litellm_url: str = None, api_key: str = None):
        self.text_strategy = text_strategy
        self.litellm_url = litellm_url or os.getenv("LITELLM_URL", "http://litellm:4000")
        self.api_key = api_key or os.getenv("QWEN_VL_MAX_API_KEY", "")

    @property
    def name(self) -> str:
        return f"multimodal-vl-{self.text_strategy.name}"

    def dimensions(self) -> int:
        return self.text_strategy.dimensions()

    def distance_metric(self) -> str:
        return self.text_strategy.distance_metric()

    async def validate(self) -> bool:
        return bool(self.api_key) and await self.text_strategy.validate()

    async def _describe_image(self, image_base64: str) -> str:
        prompt = "Descreva esta imagem em detalhes, focando em elementos visuais relevantes para analise comercial."
        payload = {
            "model": "qwen-vl-max",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                ]
            }],
            "max_tokens": 300,
            "temperature": 0.1
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{self.litellm_url}/v1/chat/completions", json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

    async def embed(self, texts: List[str]) -> List[List[float]]:
        return await self.text_strategy.embed(texts)

    async def embed_images(self, images_base64: List[str]) -> List[List[float]]:
        descriptions = []
        for img_b64 in images_base64:
            desc = await self._describe_image(img_b64)
            descriptions.append(desc)
        return await self.text_strategy.embed(descriptions)

class EmbeddingRouter:
    """
    Gerenciador de estrategias de embedding.
    Permite registrar, ativar, fallback automatico e versionamento de collections.
    """
    def __init__(self, default_strategy: EmbeddingStrategy = None):
        self._strategies: Dict[str, EmbeddingStrategy] = {}
        self._active: Optional[str] = None
        self._fallback_chain: List[str] = []
        if default_strategy is not None:
            self.register(default_strategy.name, default_strategy)
            self.activate(default_strategy.name)
    
    def register(self, name: str, strategy: EmbeddingStrategy) -> None:
        self._strategies[name] = strategy
        logger.info(f"Registered: {name} (dim={strategy.dimensions()}, metric={strategy.distance_metric()})")
    
    def activate(self, name: str) -> bool:
        if name not in self._strategies:
            logger.error(f"Cannot activate unknown strategy: {name}")
            return False
        self._active = name
        logger.info(f"Activated: {name}")
        return True
    
    def set_fallback_chain(self, names: List[str]) -> None:
        valid = [n for n in names if n in self._strategies]
        self._fallback_chain = valid
        logger.info(f"Fallback chain: {valid}")
    
    @property
    def active(self) -> Optional[EmbeddingStrategy]:
        if self._active is None:
            return None
        return self._strategies.get(self._active)
    
    @property
    def active_name(self) -> Optional[str]:
        return self._active
    
    def list_strategies(self) -> Dict[str, Dict[str, Any]]:
        return {
            name: {
                "name": s.name,
                "dimensions": s.dimensions(),
                "distance_metric": s.distance_metric(),
                "active": name == self._active
            }
            for name, s in self._strategies.items()
        }
    
    async def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        attempt_order = []
        if self._active and self._active in self._strategies:
            attempt_order.append(self._active)
        attempt_order.extend(n for n in self._fallback_chain if n != self._active and n in self._strategies)
        errors = []
        for sname in attempt_order:
            strategy = self._strategies[sname]
            try:
                if await strategy.validate():
                    vectors = await strategy.embed(texts)
                    if sname != self._active:
                        logger.info(f"Fallback activated: {sname}")
                        self._active = sname
                    return vectors
                else:
                    errors.append(f"{sname}: validation failed")
            except Exception as e:
                errors.append(f"{sname}: {str(e)}")
                logger.warning(f"Fallback from {sname}: {e}")
                continue
        raise RuntimeError(f"All embedding strategies failed: {"; ".join(errors)}")
    
    def get_collection_name(self, memory_type: str) -> str:
        suffix = self._active or "default"
        safe = suffix.replace("-", "_").replace(".", "_")
        return f"kirin_{memory_type}_{safe}"


def create_default_router() -> EmbeddingRouter:
    """
    Cria EmbeddingRouter com strategies padrao.
    Ordem: SentenceTransformers, LiteLLM, OpenAI.
    """
    router = EmbeddingRouter()
    candidates = [
        ("sentence-transformers", SentenceTransformersStrategy),
        ("litellm", LiteLLMEmbeddingStrategy),
        ("openai", OpenAITextEmbeddingStrategy),
    ]
    for name, cls in candidates:
        try:
            strategy = cls()
            router.register(name, strategy)
        except Exception as e:
            logger.debug(f"Could not register {name}: {e}")
    for name in [c[0] for c in candidates]:
        if name in router._strategies:
            strategy = router._strategies[name]
            import asyncio
            try:
                if asyncio.run(strategy.validate()):
                    router.activate(name)
                    break
            except Exception:
                continue
    router.set_fallback_chain([c[0] for c in candidates if c[0] in router._strategies])
    return router
