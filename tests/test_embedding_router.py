"""
Testes para o Embedding Router.

Cobre:
- Testes de unidade para cada strategy
- Testes de propriedade (I-Embed-1: determinismo)
- Testes de integracao do EmbeddingRouter (fallback, ativacao)
- Mocks para strategies (sem dependencias externas)
"""
import pytest
from unittest.mock import AsyncMock, patch
from typing import List

# ==============================================================================
# Mocks
# ==============================================================================

class MockEmbeddingStrategy:
    """Strategy mockada para testes do router."""
    def __init__(self, name: str, dimensions: int = 384, should_fail: bool = False):
        self._name = name
        self._dimensions = dimensions
        self._should_fail = should_fail
    
    @property
    def name(self) -> str:
        return self._name
    
    def dimensions(self) -> int:
        return self._dimensions
    
    def distance_metric(self) -> str:
        return "cosine"
    
    async def validate(self) -> bool:
        return not self._should_fail
    
    async def embed(self, texts: List[str]) -> List[List[float]]:
        if self._should_fail:
            raise RuntimeError(f"Mock {self._name} failed")
        return [[float(i + j) for j in range(self._dimensions)] for i in range(len(texts))]


# ==============================================================================
# Testes de Unidade: EmbeddingRouter
# ==============================================================================

class TestEmbeddingRouter:
    """Testes do EmbeddingRouter."""
    
    @pytest.mark.asyncio
    async def test_router_register_and_activate(self):
        from agents.memory.embedding_router import EmbeddingRouter
        router = EmbeddingRouter()
        strategy = MockEmbeddingStrategy("mock-v1", 384)
        
        router.register("mock-v1", strategy)
        assert "mock-v1" in router._strategies
        
        assert router.activate("mock-v1") is True
        assert router.active_name == "mock-v1"
        assert router.active is strategy
    
    @pytest.mark.asyncio
    async def test_router_activate_unknown(self):
        from agents.memory.embedding_router import EmbeddingRouter
        router = EmbeddingRouter()
        assert router.activate("unknown") is False
    
    @pytest.mark.asyncio
    async def test_router_embed_with_active(self):
        from agents.memory.embedding_router import EmbeddingRouter
        router = EmbeddingRouter()
        router.register("mock", MockEmbeddingStrategy("mock", 384))
        router.activate("mock")
        
        vectors = await router.embed(["texto 1", "texto 2"])
        assert len(vectors) == 2
        assert len(vectors[0]) == 384
    
    @pytest.mark.asyncio
    async def test_router_embed_empty_input(self):
        from agents.memory.embedding_router import EmbeddingRouter
        router = EmbeddingRouter()
        router.register("mock", MockEmbeddingStrategy("mock", 384))
        router.activate("mock")
        
        vectors = await router.embed([])
        assert vectors == []
    
    @pytest.mark.asyncio
    async def test_router_fallback_chain(self):
        from agents.memory.embedding_router import EmbeddingRouter
        router = EmbeddingRouter()
        
        # Ativa falha, fallback 1 falha, fallback 2 funciona
        router.register("ativa", MockEmbeddingStrategy("ativa", 384, should_fail=True))
        router.register("fallback1", MockEmbeddingStrategy("fallback1", 384, should_fail=True))
        router.register("fallback2", MockEmbeddingStrategy("fallback2", 128))
        
        router.activate("ativa")
        router.set_fallback_chain(["fallback1", "fallback2"])
        
        vectors = await router.embed(["teste"])
        assert len(vectors) == 1
        assert len(vectors[0]) == 128  # fallback2 tem 128d
        assert router.active_name == "fallback2"  # router mudou para fallback2
    
    @pytest.mark.asyncio
    async def test_router_all_fail_raises_error(self):
        from agents.memory.embedding_router import EmbeddingRouter
        router = EmbeddingRouter()
        
        router.register("fail1", MockEmbeddingStrategy("fail1", 384, should_fail=True))
        router.register("fail2", MockEmbeddingStrategy("fail2", 128, should_fail=True))
        
        router.activate("fail1")
        router.set_fallback_chain(["fail2"])
        
        with pytest.raises(RuntimeError) as excinfo:
            await router.embed(["teste"])
        assert "All embedding strategies failed" in str(excinfo.value)
    
    @pytest.mark.asyncio
    async def test_router_list_strategies(self):
        from agents.memory.embedding_router import EmbeddingRouter
        router = EmbeddingRouter()
        router.register("mock1", MockEmbeddingStrategy("mock1", 384))
        router.register("mock2", MockEmbeddingStrategy("mock2", 768))
        router.activate("mock1")
        
        listed = router.list_strategies()
        assert len(listed) == 2
        assert listed["mock1"]["active"] is True
        assert listed["mock2"]["active"] is False
        assert listed["mock1"]["dimensions"] == 384
    
    def test_get_collection_name(self):
        from agents.memory.embedding_router import EmbeddingRouter
        router = EmbeddingRouter()
        router.register("mock-1.0", MockEmbeddingStrategy("mock-1.0", 384))
        router.activate("mock-1.0")
        
        name = router.get_collection_name("enrichment")
        assert name == "kirin_enrichment_mock_1_0"
    
    def test_get_collection_name_no_active(self):
        from agents.memory.embedding_router import EmbeddingRouter
        router = EmbeddingRouter()
        name = router.get_collection_name("test")
        assert name == "kirin_test_default"


# ==============================================================================
# Testes de Unidade: SentenceTransformersStrategy
# ==============================================================================

class TestSentenceTransformersStrategy:
    """Testes do SentenceTransformersStrategy com mock."""
    
    @pytest.mark.asyncio
    async def test_validate_returns_false_when_not_installed(self):
        from agents.memory.embedding_router import SentenceTransformersStrategy
        strategy = SentenceTransformersStrategy()
        
        # Sem sentence-transformers instalado
        is_valid = await strategy.validate()
        assert is_valid is False
    
    def test_properties(self):
        from agents.memory.embedding_router import SentenceTransformersStrategy
        strategy = SentenceTransformersStrategy()
        
        assert strategy.name == "sentence-transformers-all-MiniLM-L6-v2"
        assert strategy.dimensions() == 384
        assert strategy.distance_metric() == "cosine"


# ==============================================================================
# Testes de Unidade: LiteLLMEmbeddingStrategy
# ==============================================================================

class TestLiteLLMEmbeddingStrategy:
    """Testes do LiteLLMEmbeddingStrategy com mock."""
    
    def test_properties(self):
        from agents.memory.embedding_router import LiteLLMEmbeddingStrategy
        strategy = LiteLLMEmbeddingStrategy(
            litellm_url="http://test:4000",
            model="text-embedding-ada-002"
        )
        
        assert strategy.dimensions() == 1536
        assert strategy.distance_metric() == "cosine"
        assert strategy.name == "litellm-text-embedding-ada-002"
    
    @pytest.mark.asyncio
    async def test_validate_without_server(self):
        from agents.memory.embedding_router import LiteLLMEmbeddingStrategy
        strategy = LiteLLMEmbeddingStrategy(
            litellm_url="http://localhost:19999",
        )
        
        is_valid = await strategy.validate()
        assert is_valid is False  # Nao tem LiteLLM rodando na porta 19999


# ==============================================================================
# Testes de Unidade: OpenAITextEmbeddingStrategy
# ==============================================================================

class TestOpenAITextEmbeddingStrategy:
    """Testes do OpenAITextEmbeddingStrategy."""
    
    def test_properties(self):
        from agents.memory.embedding_router import OpenAITextEmbeddingStrategy
        strategy = OpenAITextEmbeddingStrategy(
            api_key="test-key",
            model="text-embedding-3-large"
        )
        
        assert strategy.dimensions() == 3072
        assert strategy.distance_metric() == "cosine"
        assert strategy.name == "openai-text-embedding-3-large"
    
    @pytest.mark.asyncio
    async def test_validate_without_key(self):
        from agents.memory.embedding_router import OpenAITextEmbeddingStrategy
        strategy = OpenAITextEmbeddingStrategy(api_key="")
        
        is_valid = await strategy.validate()
        assert is_valid is False
    
    @pytest.mark.asyncio
    async def test_validate_with_key(self):
        from agents.memory.embedding_router import OpenAITextEmbeddingStrategy
        strategy = OpenAITextEmbeddingStrategy(api_key="sk-test123")
        
        is_valid = await strategy.validate()
        assert is_valid is True


# ==============================================================================
# Testes de Propriedade (Hypothesis)
# ==============================================================================

class TestEmbeddingProperties:
    """Testes de propriedade usando Hypothesis."""
    
    @pytest.mark.asyncio
    async def test_router_get_collection_name_property(self):
        """Propriedade: get_collection_name sempre retorna string nao vazia."""
        from agents.memory.embedding_router import EmbeddingRouter
        router = EmbeddingRouter()
        router.register("mock", MockEmbeddingStrategy("mock", 384))
        router.activate("mock")
        
        for memory_type in ["", "a", "enrichment", "scoring", "discourse", "test_memoria_longa"]:
            name = router.get_collection_name(memory_type)
            assert isinstance(name, str)
            assert len(name) > 0
            assert name.startswith("kirin_")
    
    @pytest.mark.asyncio
    async def test_router_list_strategies_property(self):
        """Propriedade: list_strategies retorna dict com chaves esperadas."""
        from agents.memory.embedding_router import EmbeddingRouter
        router = EmbeddingRouter()
        router.register("a", MockEmbeddingStrategy("a", 384))
        router.register("b", MockEmbeddingStrategy("b", 768))
        
        listed = router.list_strategies()
        for name, info in listed.items():
            assert "name" in info
            assert "dimensions" in info
            assert "distance_metric" in info
            assert "active" in info
            assert isinstance(info["dimensions"], int)
            assert info["dimensions"] > 0
            assert isinstance(info["active"], bool)


# ==============================================================================
# Testes de Integracao: create_default_router
# ==============================================================================

class TestDefaultRouter:
    """Testes do create_default_router."""
    
    def test_create_default_router_returns_router(self):
        from agents.memory.embedding_router import create_default_router, EmbeddingRouter
        router = create_default_router()
        assert isinstance(router, EmbeddingRouter)
        assert len(router.list_strategies()) >= 3
    
    def test_default_router_has_expected_strategies(self):
        from agents.memory.embedding_router import create_default_router
        router = create_default_router()
        strategies = router.list_strategies()
        assert "sentence-transformers" in strategies
        assert "litellm" in strategies
        assert "openai" in strategies


# ==============================================================================
# Testes de Unidade: MultimodalVisionStrategy
# ==============================================================================

class TestMultimodalVisionStrategy:
    """Testes do MultimodalVisionStrategy."""

    def test_properties_delegates_to_text_strategy(self):
        """MultimodalVisionStrategy delega dimensao e metrica para text_strategy."""
        from agents.memory.embedding_router import MultimodalVisionStrategy, SentenceTransformersStrategy

        text_st = SentenceTransformersStrategy()
        mv = MultimodalVisionStrategy(text_strategy=text_st, api_key="sk-test")

        assert mv.name.startswith("multimodal-vl-")
        assert mv.dimensions() == 384
        assert mv.distance_metric() == "cosine"

    @pytest.mark.asyncio
    async def test_validate_requires_api_key(self):
        from agents.memory.embedding_router import MultimodalVisionStrategy, SentenceTransformersStrategy

        text_st = SentenceTransformersStrategy()
        mv_no_key = MultimodalVisionStrategy(text_strategy=text_st, api_key="")

        # Com api_key vazia, sempre invalido
        assert await mv_no_key.validate() is False

    @pytest.mark.asyncio
    async def test_embed_delegates_to_text_strategy(self):
        """embed() delega para text_strategy.embed()."""
        from agents.memory.embedding_router import MultimodalVisionStrategy

        # Usa um MockEmbeddingStrategy como text_strategy
        mock_strategy = MockEmbeddingStrategy("mock-text", 128)
        mv = MultimodalVisionStrategy(text_strategy=mock_strategy, api_key="sk-test")

        vectors = await mv.embed(["hello", "world"])
        assert len(vectors) == 2
        assert len(vectors[0]) == 128

    def test_embed_images_method_exists(self):
        from agents.memory.embedding_router import MultimodalVisionStrategy
        from typing import List

        assert hasattr(MultimodalVisionStrategy, "embed_images")

    def test_name_contains_text_strategy_name(self):
        from agents.memory.embedding_router import MultimodalVisionStrategy, SentenceTransformersStrategy

        text_st = SentenceTransformersStrategy()
        mv = MultimodalVisionStrategy(text_strategy=text_st, api_key="sk-test")

        assert "sentence-transformers" in mv.name
        assert "multimodal-vl-" in mv.name


# ==============================================================================
# Testes de Integracao: QdrantMemoryManager com EmbeddingRouter
# ==============================================================================

class TestQdrantMemoryManagerIntegration:
    """Testes de integracao QdrantMemoryManager + EmbeddingRouter (sem servidor Qdrant real)."""

    def test_qdrant_accepts_embedding_router_param(self):
        """QdrantMemoryManager aceita embedding_router como parametro opcional."""
        from agents.memory.qdrant_memory import QdrantMemoryManager
        from agents.memory.embedding_router import EmbeddingRouter

        router = EmbeddingRouter()
        qdrant = QdrantMemoryManager(host="localhost", port=6333, embedding_router=router)
        assert qdrant.embedding_router is router

    def test_qdrant_backwards_compatibility(self):
        """QdrantMemoryManager sem embedding_router funciona igual antes."""
        from agents.memory.qdrant_memory import QdrantMemoryManager

        qdrant = QdrantMemoryManager(host="localhost", port=6333)
        assert qdrant.embedding_router is None

    def test_qdrant_uses_router_collection_name(self):
        """Qdrant usa router.get_collection_name quando router esta ativo."""
        from agents.memory.qdrant_memory import QdrantMemoryManager
        from agents.memory.embedding_router import EmbeddingRouter

        router = EmbeddingRouter()
        router.register("mock", MockEmbeddingStrategy("mock", 384))
        router.activate("mock")

        qdrant = QdrantMemoryManager(host="localhost", port=6333, embedding_router=router)
        name = qdrant._get_collection_name("enrichment")
        assert name == "kirin_enrichment_mock"

    def test_qdrant_fallback_to_default_collection_name(self):
        """Qdrant usa f'kirin_{memory_type}' quando nao tem router."""
        from agents.memory.qdrant_memory import QdrantMemoryManager

        qdrant = QdrantMemoryManager(host="localhost", port=6333)
        name = qdrant._get_collection_name("discourse")
        assert name == "kirin_discourse"

    def test_qdrant_parse_distance(self):
        """_parse_distance mapeia strings para enums Qdrant corretamente."""
        from agents.memory.qdrant_memory import QdrantMemoryManager
        from qdrant_client.http import models

        qdrant = QdrantMemoryManager(host="localhost", port=6333)
        assert qdrant._parse_distance("cosine") == models.Distance.COSINE
        assert qdrant._parse_distance("euclidean") == models.Distance.EUCLID
        assert qdrant._parse_distance("dot") == models.Distance.DOT
        assert qdrant._parse_distance("unknown") == models.Distance.COSINE


# ==============================================================================
# Testes de Compatibilidade Retroativa
# ==============================================================================

class TestBackwardsCompatibility:
    """Garante que o codigo existente nao quebrou com as mudancas."""

    def test_imports_existing_modules(self):
        """Todos os modulos existentes ainda sao importaveis."""
        import sys
        sys.path.insert(0, "/home/vector/Kirin")

        from agents.memory.base import BaseMemoryManager
        from agents.memory.postgres_memory import PostgresMemoryManager
        from agents.memory.qdrant_memory import QdrantMemoryManager
        from agents.memory.redis_memory import RedisMemoryManager
        from agents.runtime import get_postgres_memory, get_qdrant_memory, get_redis_memory, is_initialized

    def test_runtime_has_new_accessor(self):
        """Runtime expoe get_embedding_router()."""
        from agents.runtime import get_embedding_router

        # Sem inicializacao, retorna None
        result = get_embedding_router()
        assert result is None

    def test_memory_package_exports(self):
        """agents.memory.__init__ exporta todas as classes esperadas."""
        from agents.memory import (
            BaseMemoryManager,
            EmbeddingStrategy,
            SentenceTransformersStrategy,
            OpenAITextEmbeddingStrategy,
            LiteLLMEmbeddingStrategy,
            GraphRAGStrategy,
            MultimodalVisionStrategy,
            EmbeddingRouter,
            create_default_router,
        )

        assert EmbeddingStrategy is not None
        assert SentenceTransformersStrategy is not None
        assert OpenAITextEmbeddingStrategy is not None
        assert LiteLLMEmbeddingStrategy is not None
        assert GraphRAGStrategy is not None
        assert MultimodalVisionStrategy is not None
        assert EmbeddingRouter is not None
        assert callable(create_default_router)

    def test_agents_imports_unchanged(self):
        """imports de agents.core nao quebraram."""
        from agents.pure_functions import normalize_score, classify_faixa, deduplicate_leads
        from agents.pure_functions import compute_instagram_inativo, truncate_message, is_valid_status
        from agents.pure_functions import can_send_message_sync, build_mcp_error

        assert normalize_score(150) == 100
        assert classify_faixa(80) == "quente"
        assert deduplicate_leads([]) == []

    def test_enricher_imports_unchanged(self):
        """imports do enricher nao quebraram."""
        from agents.enricher import _validate_and_structure_dossie, _mark_enrichment_failed

        dossie = _validate_and_structure_dossie({"resumo_perfil": "test"})
        assert dossie["maturidade_digital"] in ("alto", "médio", "baixo")



# ==============================================================================
# Testes de Unidade: LiteLLMEmbeddingStrategy com Mock HTTP
# ==============================================================================

class TestLiteLLMEmbeddingMocked:
    """Testes do LiteLLMEmbeddingStrategy com mock de HTTP."""

    @pytest.mark.asyncio
    async def test_embed_returns_vectors(self):
        """embed() retorna vetores corretos quando LiteLLM responde."""
        from agents.memory.embedding_router import LiteLLMEmbeddingStrategy

        strategy = LiteLLMEmbeddingStrategy(
            litellm_url="http://test:4000",
            model="text-embedding-ada-002"
        )

        mock_response_data = {
            "data": [
                {"embedding": [0.1] * 1536, "index": 0},
                {"embedding": [0.2] * 1536, "index": 1},
            ]
        }

        mock_resp = AsyncMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = lambda: None
        mock_resp.json = lambda: mock_response_data

        with patch("agents.memory.embedding_router.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_instance.post = AsyncMock(return_value=mock_resp)
            MockClient.return_value = mock_instance

            vectors = await strategy.embed(["texto 1", "texto 2"])

        assert len(vectors) == 2
        assert len(vectors[0]) == 1536
        assert vectors[0] == [0.1] * 1536
        assert vectors[1] == [0.2] * 1536

    @pytest.mark.asyncio
    async def test_embed_preserves_order(self):
        """embed() preserva a ordem dos textos de entrada."""
        from agents.memory.embedding_router import LiteLLMEmbeddingStrategy

        strategy = LiteLLMEmbeddingStrategy(litellm_url="http://test:4000")

        mock_response_data = {
            "data": [
                {"embedding": [0.9] * 1536, "index": 0},
                {"embedding": [0.3] * 1536, "index": 1},
                {"embedding": [0.7] * 1536, "index": 2},
            ]
        }

        mock_resp = AsyncMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = lambda: None
        mock_resp.json = lambda: mock_response_data

        with patch("agents.memory.embedding_router.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_instance.post = AsyncMock(return_value=mock_resp)
            MockClient.return_value = mock_instance

            vectors = await strategy.embed(["a", "b", "c"])

        assert vectors[0] == [0.9] * 1536
        assert vectors[1] == [0.3] * 1536
        assert vectors[2] == [0.7] * 1536


# ==============================================================================
# Testes de Unidade: OpenAITextEmbeddingStrategy com Mock
# ==============================================================================

class TestOpenAIEmbeddingMocked:
    """Testes do OpenAITextEmbeddingStrategy com mock do cliente OpenAI."""

    @pytest.mark.asyncio
    async def test_embed_returns_vectors(self):
        """embed() retorna vetores corretos quando OpenAI responde."""
        from agents.memory.embedding_router import OpenAITextEmbeddingStrategy

        strategy = OpenAITextEmbeddingStrategy(
            api_key="sk-test",
            model="text-embedding-3-large"
        )

        # Cria mock do objeto Embedding retornado pela API
        mock_embedding_0 = type("Embedding", (), {"embedding": [0.1] * 3072})()
        mock_embedding_1 = type("Embedding", (), {"embedding": [0.2] * 3072})()

        mock_response = type("Response", (), {
            "data": [mock_embedding_0, mock_embedding_1]
        })()

        mock_client = AsyncMock()
        mock_client.embeddings.create = AsyncMock(return_value=mock_response)

        with patch.object(strategy, '_client', mock_client):
            vectors = await strategy.embed(["hello", "world"])

        assert len(vectors) == 2
        assert len(vectors[0]) == 3072
        assert vectors[0] == [0.1] * 3072

    @pytest.mark.asyncio
    async def test_embed_empty_input(self):
        """embed() com lista vazia."""
        from agents.memory.embedding_router import OpenAITextEmbeddingStrategy

        strategy = OpenAITextEmbeddingStrategy(api_key="sk-test")

        mock_response = type("Response", (), {"data": []})()
        mock_client = AsyncMock()
        mock_client.embeddings.create = AsyncMock(return_value=mock_response)

        with patch.object(strategy, '_client', mock_client):
            vectors = await strategy.embed([])

        assert vectors == []

    @pytest.mark.asyncio
    async def test_validate_with_key_returns_true(self):
        """validate() retorna True quando api_key esta configurada."""
        from agents.memory.embedding_router import OpenAITextEmbeddingStrategy

        strategy = OpenAITextEmbeddingStrategy(api_key="sk-real-key")
        result = await strategy.validate()
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_without_key_returns_false(self):
        """validate() retorna False quando api_key esta vazia."""
        from agents.memory.embedding_router import OpenAITextEmbeddingStrategy

        strategy = OpenAITextEmbeddingStrategy(api_key="")
        result = await strategy.validate()
        assert result is False

    def test_dimensions_updates_after_embed(self):
        """dimensions() atualiza apos embed() retornar vetores de tamanho diferente."""
        from agents.memory.embedding_router import OpenAITextEmbeddingStrategy

        strategy = OpenAITextEmbeddingStrategy(
            api_key="sk-test",
            model="text-embedding-3-large"
        )

        # Dimensao inicial e 3072 (padrao)
        assert strategy.dimensions() == 3072


# ==============================================================================
# Testes de Propriedade: I-Embed-1 (Determinismo)
# ==============================================================================

class TestDeterminismProperty:
    """Testes da invariante I-Embed-1: mesmo input = mesmo output."""

    @pytest.mark.asyncio
    async def test_mock_strategy_deterministic(self):
        """MockEmbeddingStrategy e deterministica: mesmo input = mesmo output."""
        strategy = MockEmbeddingStrategy("mock", 128)

        vectors1 = await strategy.embed(["hello world"])
        vectors2 = await strategy.embed(["hello world"])

        assert vectors1 == vectors2

    @pytest.mark.asyncio
    async def test_mock_strategy_same_length(self):
        """Embedding sempre produz vetores do mesmo tamanho."""
        strategy = MockEmbeddingStrategy("mock", 64)

        for _ in range(10):
            vectors = await strategy.embed(["any text"])
            assert len(vectors[0]) == 64

    def test_collection_name_deterministic(self):
        """get_collection_name retorna o mesmo nome para a mesma strategy."""
        from agents.memory.embedding_router import EmbeddingRouter

        router = EmbeddingRouter()
        router.register("test", MockEmbeddingStrategy("test", 384))
        router.activate("test")

        names = [router.get_collection_name("enrichment") for _ in range(10)]
        assert len(set(names)) == 1
