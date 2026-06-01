"""
Feature: kirin-runtime
Unified property-based tests using Hypothesis. Minimum 100 examples per property.
"""
import os
import pytest
from hypothesis import given, settings, strategies as st, HealthCheck
from hypothesis.strategies import composite
from pydantic import ValidationError

settings.register_profile("ci", max_examples=100, suppress_health_check=[HealthCheck.too_slow])
settings.load_profile("ci")

from core.agents.base_agent import AgentState, STATE_ORDER, InvokeRequest, BaseAgent
from core.engine.snapshot import serialize_runtime_state, restore_runtime_state
from core.engine.state_models import AgentRuntimeState
from core.providers.provider_router import NormalizedResponse
from core.governance.secret_vault import SecretVault

# ── Strategies ──────────────────────────────────────────────────────────────

valid_goal = st.text(min_size=1).filter(lambda s: s.strip())
whitespace_goal = st.text(alphabet=" \t\n\r", min_size=0)
memory_id = st.uuids().map(str)
tenant_id = st.text(
    min_size=1, max_size=32,
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")),
)
context_dict = st.dictionaries(st.text(min_size=1), st.text())
env_var_name = st.text(
    min_size=1, max_size=32,
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_"),
).filter(lambda s: s[0].isalpha() or s[0] == "_")


@composite
def agent_state_sequence(draw):
    states = list(AgentState)
    start_idx = draw(st.integers(min_value=0, max_value=len(states) - 2))
    end_idx = draw(st.integers(min_value=start_idx, max_value=len(states) - 1))
    return states[start_idx], states[end_idx]


# ── P1: Idempotência de Upsert de Memória ──────────────────────────────────

@pytest.mark.asyncio
@given(mid=memory_id, tid=tenant_id, content=context_dict)
@settings(max_examples=100)
async def test_p1_memory_upsert_idempotent(mid, tid, content):
    """Feature: kirin-runtime, Property 1: Idempotência de Upsert de Memória"""
    from unittest.mock import AsyncMock
    from core.memory.memory_manager import MemoryManager

    store = {}
    async def mock_set(key, value, ttl=None):
        store[key] = value
    async def mock_get(key):
        return store.get(key)

    redis = AsyncMock()
    redis.set = mock_set
    redis.get = mock_get
    mm = MemoryManager(redis=redis, postgres=AsyncMock(), qdrant=AsyncMock())

    await mm.write_working_memory(mid, tid, content)
    first_write = dict(store)
    await mm.write_working_memory(mid, tid, content)
    second_write = dict(store)

    assert first_write == second_write


# ── P2: Invariante de Progressão de Estado ─────────────────────────────────

@given(pair=agent_state_sequence())
@settings(max_examples=100)
def test_p2_state_never_regresses(pair):
    """Feature: kirin-runtime, Property 2: Invariante de Progressão de Estado"""

    class ConcreteAgent(BaseAgent):
        async def _init(self, r): pass
        async def _observe(self, r): return {}
        async def _decide(self, o): return {}
        async def _execute(self, d): return None

    agent = ConcreteAgent("test")
    s1, s2 = pair
    agent.state = s1
    if STATE_ORDER[s2] >= STATE_ORDER[s1]:
        agent.transition_to(s2)
        assert STATE_ORDER[agent.state] >= STATE_ORDER[s1]
    else:
        with pytest.raises(ValueError):
            agent.transition_to(s2)


# ── P3: Round-Trip de Snapshot ─────────────────────────────────────────────

@given(
    agent_id=st.text(min_size=1, max_size=32),
    mid=memory_id,
    state=st.sampled_from(list(AgentState)),
    hb=st.integers(min_value=0, max_value=5),
)
@settings(max_examples=100)
def test_p3_snapshot_roundtrip(agent_id, mid, state, hb):
    """Feature: kirin-runtime, Property 3: Round-Trip de Serialização de Snapshot"""
    from datetime import datetime, timezone
    snap = AgentRuntimeState(
        memory_id=mid,
        agent_id=agent_id,
        tenant_id="default",
        current_phase=state,
        heartbeat_count=hb,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    restored = restore_runtime_state(snap)
    assert restored["agent_id"] == agent_id
    assert restored["memory_id"] == mid
    assert restored["current_phase"] == state.value
    assert restored["heartbeat_count"] == hb


# ── P4: Idempotência de Publicação no Event Bus ────────────────────────────

@pytest.mark.asyncio
@given(
    mid=memory_id,
    payload=context_dict,
    topic=st.sampled_from(["lead.created", "agent.completed", "message.sent"]),
)
@settings(max_examples=100)
async def test_p4_event_bus_publish_idempotent(mid, payload, topic):
    """Feature: kirin-runtime, Property 4: Idempotência de Publicação no Event Bus"""
    from core.bus.event_bus import EventBus, Event

    bus = EventBus("redis://localhost:6379")
    event = Event.create(
        event_type=topic,
        session_id=mid,
        actor_id="test",
        tenant_id="default",
        payload=payload,
    )

    await bus.publish(event)
    await bus.publish(event)

    stream_key = bus._stream_key(mid)
    assert len(bus._streams.get(stream_key, [])) == 1


# ── P5: Idempotência de Carregamento de Plugin ─────────────────────────────

@pytest.mark.asyncio
@given(plugin_name=st.sampled_from(["crm", "whatsapp", "vectordb"]))
@settings(max_examples=100)
async def test_p5_plugin_load_idempotent(plugin_name):
    """Feature: kirin-runtime, Property 5: Idempotência de Carregamento de Plugin"""
    from core.plugins.plugin_loader import PluginLoader

    loader = PluginLoader()
    await loader.load(plugin_name, version="1.0.0")
    state_after_first = dict(loader._loaded)
    await loader.load(plugin_name, version="1.0.0")
    state_after_second = dict(loader._loaded)
    assert state_after_first == state_after_second


# ── P6: Normalização de Resposta de Provider ───────────────────────────────

@given(
    content=st.text(min_size=1),
    tokens=st.integers(min_value=0, max_value=100000),
    model=st.text(min_size=1),
    provider=st.sampled_from(["openai", "anthropic", "google", "deepseek", "ollama"]),
)
@settings(max_examples=100)
def test_p6_normalized_response_has_required_fields(content, tokens, model, provider):
    """Feature: kirin-runtime, Property 6: Normalização de Resposta de Provider"""
    r = NormalizedResponse(content=content, tokens_used=tokens, model=model, provider=provider)
    assert isinstance(r.content, str)
    assert isinstance(r.tokens_used, int)
    assert isinstance(r.model, str)
    assert isinstance(r.provider, str)


# ── P7: Isolamento de Memória entre Tenants ────────────────────────────────

@pytest.mark.asyncio
@given(mid=memory_id, content1=context_dict, content2=context_dict)
@settings(max_examples=100)
async def test_p7_tenant_memory_isolation(mid, content1, content2):
    """Feature: kirin-runtime, Property 7: Isolamento de Memória entre Tenants"""
    from unittest.mock import AsyncMock
    from core.memory.memory_manager import MemoryManager

    t1 = "tenant_alpha"
    t2 = "tenant_beta"

    store = {}
    async def mock_set(key, value, ttl=None):
        store[key] = value
    async def mock_get(key):
        return store.get(key)

    redis = AsyncMock()
    redis.set = mock_set
    redis.get = mock_get
    mm = MemoryManager(redis=redis, postgres=AsyncMock(), qdrant=AsyncMock())

    await mm.write_working_memory(mid, t1, content1)
    await mm.write_working_memory(mid, t2, content2)

    result_t1 = await mm.read_working_memory(mid, t1)
    result_t2 = await mm.read_working_memory(mid, t2)

    assert result_t1 == content1
    assert result_t2 == content2


# ── P8: Determinismo de Grafo de Workflow ──────────────────────────────────

@pytest.mark.asyncio
@given(
    task_ids=st.lists(
        st.text(min_size=1, max_size=8), min_size=1, max_size=5, unique=True
    ),
    inputs=context_dict,
)
@settings(max_examples=100)
async def test_p8_workflow_graph_determinism(task_ids, inputs):
    """Feature: kirin-runtime, Property 8: Determinismo de Grafo de Workflow"""
    from core.engine.pipeline_engine import PipelineEngine, Task

    tasks = [Task(task_id=tid, name=tid) for tid in task_ids]
    engine = PipelineEngine()

    async def executor(task, inp):
        return {"done": True}

    results1 = await engine.run(tasks, executor, inputs)
    results2 = await engine.run(tasks, executor, inputs)

    assert set(results1.keys()) == set(results2.keys())


# ── P9: Consistência de Leitura Após Escrita ───────────────────────────────

@pytest.mark.asyncio
@given(mid=memory_id, tid=tenant_id, content=context_dict)
@settings(max_examples=100)
async def test_p9_read_after_write_consistency(mid, tid, content):
    """Feature: kirin-runtime, Property 9: Consistência de Leitura Após Escrita"""
    from unittest.mock import AsyncMock
    from core.memory.memory_manager import MemoryManager

    store = {}
    async def mock_set(key, value, ttl=None):
        store[key] = value
    async def mock_get(key):
        return store.get(key)

    redis = AsyncMock()
    redis.set = mock_set
    redis.get = mock_get
    mm = MemoryManager(redis=redis, postgres=AsyncMock(), qdrant=AsyncMock())

    await mm.write_working_memory(mid, tid, content)
    result = await mm.read_working_memory(mid, tid)
    assert result == content


# ── P10: Equivalência de Restauração de Snapshot ──────────────────────────

@given(
    agent_id=st.text(min_size=1, max_size=32),
    mid=memory_id,
    state=st.sampled_from(list(AgentState)),
    hb=st.integers(min_value=0, max_value=5),
)
@settings(max_examples=100)
def test_p10_snapshot_restoration_equivalence(agent_id, mid, state, hb):
    """Feature: kirin-runtime, Property 10: Equivalência de Restauração de Snapshot"""
    from datetime import datetime, timezone
    snap = AgentRuntimeState(
        memory_id=mid,
        agent_id=agent_id,
        tenant_id="default",
        current_phase=state,
        heartbeat_count=hb,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    restored = restore_runtime_state(snap)
    assert restored["current_phase"] == state
    assert restored["heartbeat_count"] == hb
    assert restored["agent_id"] == agent_id


# ── P11: Schema de Saída Preservado ───────────────────────────────────────

@given(goal=valid_goal, mid=memory_id, ctx=context_dict)
@settings(max_examples=100)
def test_p11_invoke_request_schema_valid(goal, mid, ctx):
    """Feature: kirin-runtime, Property 11: Schema de Saída Preservado para Qualquer Agent"""
    req = InvokeRequest(goal=goal, context=ctx, memory_id=mid)
    assert req.goal == goal.strip() or req.goal == goal
    assert req.memory_id == mid


# ── P12: Rejeição de Inputs Inválidos ─────────────────────────────────────

@given(goal=whitespace_goal)
@settings(max_examples=100)
def test_p12_whitespace_goal_rejected(goal):
    """Feature: kirin-runtime, Property 12: Rejeição de Inputs Inválidos"""
    with pytest.raises((ValidationError, ValueError)):
        InvokeRequest(goal=goal, context={}, memory_id="test-id")


# ── P13: Secret Vault Não Expõe Valores ───────────────────────────────────

@given(
    agent_id=st.text(min_size=1, max_size=32),
    secret_name=env_var_name,
)
@settings(max_examples=100)
def test_p13_secret_vault_no_value_in_audit(agent_id, secret_name):
    """Feature: kirin-runtime, Property 13: Secret Vault Não Expõe Valores"""
    vault = SecretVault()
    os.environ[secret_name] = ""
    vault.get(agent_id, secret_name)
    last = vault._audit[-1]
    assert "value" not in last
    assert last["secret_name"] == secret_name


# ── P14: Compatibilidade de Schema com MVP ────────────────────────────────

@given(goal=st.sampled_from(["score_lead", "enrich_lead", "generate_message", "research_lead", "crm_sync"]))
@settings(max_examples=100)
def test_p14_mvp_schema_compatibility(goal):
    """Feature: kirin-runtime, Property 14: Compatibilidade de Schema com MVP"""

    class ConcreteAgent(BaseAgent):
        async def _init(self, r): pass
        async def _observe(self, r): return {}
        async def _decide(self, o): return {}
        async def _execute(self, d): return {"result": "ok"}

    agent = ConcreteAgent(goal)
    req = InvokeRequest(goal=goal, context={"lead": {"id": "1"}}, memory_id="test-mid")
    assert agent.agent_id == goal
    assert req.goal == goal
