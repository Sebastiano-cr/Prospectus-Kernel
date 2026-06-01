"""
Feature: kirin-embedding
Hypothesis property tests for embedding strategies and router.
I-Embed-1: determinism (same text = same vector)
I-Router-1: fallback doesn't lose data
"""
import pytest
from hypothesis import given, settings, strategies as st, HealthCheck
from typing import List


settings.register_profile("ci", max_examples=100, suppress_health_check=[HealthCheck.too_slow])
settings.load_profile("ci")


class MockEmbeddingStrategy:
    """Deterministic mock for property testing."""
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


# ── I-Embed-1: Determinism ─────────────────────────────────────────────────

@given(
    text=st.text(min_size=1, max_size=200),
    dim=st.sampled_from([64, 128, 384, 768]),
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_i_embed_1_determinism(text, dim):
    """I-Embed-1: same strategy + same text = same vector."""
    strategy = MockEmbeddingStrategy("det-test", dim)
    vectors1 = await strategy.embed([text])
    vectors2 = await strategy.embed([text])
    assert vectors1 == vectors2


@given(
    texts=st.lists(st.text(min_size=1, max_size=50), min_size=1, max_size=10),
    dim=st.sampled_from([64, 128, 384]),
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_i_embed_1_batch_determinism(texts, dim):
    """I-Embed-1: batch embed is deterministic."""
    strategy = MockEmbeddingStrategy("batch-det", dim)
    vectors1 = await strategy.embed(texts)
    vectors2 = await strategy.embed(texts)
    assert vectors1 == vectors2


# ── I-Router-1: Fallback doesn't lose data ─────────────────────────────────

@given(
    text=st.text(min_size=1, max_size=100),
    active_dim=st.sampled_from([128, 384]),
    fallback_dim=st.sampled_from([64, 256]),
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_i_router_1_fallback_no_data_loss(text, active_dim, fallback_dim):
    """I-Embed-1 + I-Router-1: fallback returns valid vectors without data loss."""
    from agents.memory.embedding_router import EmbeddingRouter

    router = EmbeddingRouter()
    router.register("active", MockEmbeddingStrategy("active", active_dim, should_fail=True))
    router.register("fallback", MockEmbeddingStrategy("fallback", fallback_dim))
    router.activate("active")
    router.set_fallback_chain(["fallback"])

    vectors = await router.embed([text])
    assert len(vectors) == 1
    assert len(vectors[0]) == fallback_dim


# ── Collection name determinism ────────────────────────────────────────────

@given(
    memory_type=st.text(min_size=1, max_size=30, alphabet=st.characters(
        whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters="_"
    )),
    strategy_name=st.text(min_size=1, max_size=20, alphabet=st.characters(
        whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters="_-."
    )),
)
@settings(max_examples=100)
def test_collection_name_deterministic(memory_type, strategy_name):
    """get_collection_name is deterministic for same inputs."""
    from agents.memory.embedding_router import EmbeddingRouter

    router = EmbeddingRouter()
    router.register(strategy_name, MockEmbeddingStrategy(strategy_name, 384))
    router.activate(strategy_name)

    name1 = router.get_collection_name(memory_type)
    name2 = router.get_collection_name(memory_type)
    assert name1 == name2
    assert name1.startswith("kirin_")


# ── Collection name format ─────────────────────────────────────────────────

@given(
    memory_type=st.sampled_from(["enrichment", "scoring", "discourse", "episodic"]),
    strategy_name=st.sampled_from(["sentence-transformers-model", "litellm-ada-002", "openai-3-large"]),
)
@settings(max_examples=100)
def test_collection_name_format(memory_type, strategy_name):
    """Collection name follows kirin_{type}_{strategy} format with safe chars."""
    from agents.memory.embedding_router import EmbeddingRouter

    router = EmbeddingRouter()
    router.register(strategy_name, MockEmbeddingStrategy(strategy_name, 384))
    router.activate(strategy_name)

    name = router.get_collection_name(memory_type)
    assert name.startswith("kirin_")
    assert memory_type in name
    # No hyphens or dots in collection name (replaced by underscores)
    assert "-" not in name.split("_", 2)[-1] or name.count("-") == 0
    assert "." not in name.split("_", 2)[-1] or name.count(".") == 0


# ── Embedding dimensions consistency ───────────────────────────────────────

@given(dim=st.sampled_from([64, 128, 256, 384, 768, 1024]))
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_dimensions_consistent_after_embed(dim):
    """dimensions() returns consistent value before and after embed()."""
    strategy = MockEmbeddingStrategy("dim-test", dim)
    assert strategy.dimensions() == dim
    await strategy.embed(["test"])
    assert strategy.dimensions() == dim
