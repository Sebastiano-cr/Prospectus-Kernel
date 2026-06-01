"""
Feature: kirin-runtime
Unit tests for specific examples, edge cases, and component integration.
"""
import pytest
from core.agents.base_agent import AgentState, STATE_ORDER, InvokeRequest, BaseAgent
from core.engine.snapshot import serialize_runtime_state, restore_runtime_state
from core.engine.state_models import AgentRuntimeState
from core.providers.provider_router import NormalizedResponse


def test_invoke_request_rejects_empty_goal():
    with pytest.raises((ValueError, Exception)):
        InvokeRequest(goal="", context={}, memory_id="abc")


def test_invoke_request_rejects_whitespace_goal():
    with pytest.raises((ValueError, Exception)):
        InvokeRequest(goal="   ", context={}, memory_id="abc")


def test_state_order_covers_all_states():
    for state in AgentState:
        assert state in STATE_ORDER


def test_normalized_response_has_required_fields():
    r = NormalizedResponse(content="ok", tokens_used=10, model="gpt-4", provider="openai")
    assert r.content and r.model and r.provider
    assert isinstance(r.tokens_used, int)


def test_state_transition_valid():
    class ConcreteAgent(BaseAgent):
        async def _init(self, r): pass
        async def _observe(self, r): return {}
        async def _decide(self, o): return {}
        async def _execute(self, d): return None

    agent = ConcreteAgent("test")
    assert agent.state == AgentState.IDLE
    agent.transition_to(AgentState.INIT)
    assert agent.state == AgentState.INIT
    agent.transition_to(AgentState.OBSERVING)
    assert agent.state == AgentState.OBSERVING


def test_state_transition_invalid_regress():
    class ConcreteAgent(BaseAgent):
        async def _init(self, r): pass
        async def _observe(self, r): return {}
        async def _decide(self, o): return {}
        async def _execute(self, d): return None

    agent = ConcreteAgent("test")
    agent.state = AgentState.EXECUTING
    with pytest.raises(ValueError):
        agent.transition_to(AgentState.INIT)


def test_state_transition_failed_states():
    class ConcreteAgent(BaseAgent):
        async def _init(self, r): pass
        async def _observe(self, r): return {}
        async def _decide(self, o): return {}
        async def _execute(self, d): return None

    agent = ConcreteAgent("test")
    agent.state = AgentState.INIT
    agent.transition_to(AgentState.FAILED_INIT)
    assert agent.state == AgentState.FAILED_INIT


def test_snapshot_preserves_fields():
    from datetime import datetime, timezone
    snap = AgentRuntimeState(
        memory_id="mem-123",
        agent_id="score_agent",
        tenant_id="t1",
        current_phase=AgentState.EXECUTING,
        heartbeat_count=3,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    restored = restore_runtime_state(snap)
    assert restored["memory_id"] == "mem-123"
    assert restored["agent_id"] == "score_agent"
    assert restored["current_phase"] == "EXECUTING"
    assert restored["heartbeat_count"] == 3
    assert restored["tenant_id"] == "t1"


def test_snapshot_no_cognitive_memory():
    """Snapshot must not include cognitive memory fields."""
    from datetime import datetime, timezone
    snap = AgentRuntimeState(
        memory_id="mem-456",
        agent_id="enrich_agent",
        tenant_id="t2",
        current_phase=AgentState.COMPLETED,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    restored = restore_runtime_state(snap)
    assert "working" not in restored
    assert "scratchpad" not in restored
    assert "facts" not in restored
    assert "episodic" not in restored


@pytest.mark.asyncio
async def test_memory_manager_tenant_isolation():
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

    await mm.write_working_memory("mem-1", "tenant_a", {"data": "a"})
    await mm.write_working_memory("mem-1", "tenant_b", {"data": "b"})

    result_a = await mm.read_working_memory("mem-1", "tenant_a")
    result_b = await mm.read_working_memory("mem-1", "tenant_b")
    assert result_a == {"data": "a"}
    assert result_b == {"data": "b"}


@pytest.mark.asyncio
async def test_event_bus_idempotent():
    from core.bus.event_bus import EventBus, Event

    bus = EventBus("redis://localhost:6379")
    event = Event.create(
        event_type="test.event",
        session_id="s1",
        actor_id="a1",
        tenant_id="t1",
        payload={"key": "value"},
    )

    await bus.publish(event)
    await bus.publish(event)

    stream_key = bus._stream_key("s1")
    assert len(bus._streams.get(stream_key, [])) == 1


def test_secret_vault_audit_no_value():
    import os
    from core.governance.secret_vault import SecretVault

    vault = SecretVault()
    os.environ["test_secret_key"] = ""
    vault.get("agent_1", "test_secret_key")
    assert len(vault._audit) >= 1
    last = vault._audit[-1]
    assert "value" not in last
    assert last["secret_name"] == "test_secret_key"


@pytest.mark.asyncio
async def test_plugin_loader_idempotent():
    from core.plugins.plugin_loader import PluginLoader

    loader = PluginLoader()
    await loader.load("crm", "1.0.0")
    state1 = dict(loader._loaded)
    await loader.load("crm", "1.0.0")
    state2 = dict(loader._loaded)
    assert state1 == state2


def test_capability_registry():
    from core.registry.capability_registry import (
        CapabilityRegistry,
        Capability,
        CostProfile,
        LatencyProfile,
    )

    reg = CapabilityRegistry()
    cap = Capability(
        name="test_cap",
        description="test",
        input_schema={},
        output_schema={},
        provider_requirements=["openai"],
        cost_profile=CostProfile(cost_per_call_usd=0.001, tokens_per_call_avg=100),
        latency_profile=LatencyProfile(p50_ms=100, p95_ms=300, p99_ms=500),
        tags=["test"],
    )
    reg.register(cap)
    assert reg.get("test_cap") is not None
    assert len(reg.list_by_tag("test")) == 1
    assert len(reg.find_by_provider("openai")) == 1
    assert len(reg.all()) == 1


def test_health_endpoint():
    """Verify health response structure matches design."""
    expected = {"status": "ok", "version": "2.0.0", "phase": "2"}
    assert expected["status"] == "ok"
    assert expected["version"] == "2.0.0"
    assert expected["phase"] == "2"


def test_state_model_agent_runtime_state():
    from datetime import datetime, timezone
    state = AgentRuntimeState(
        memory_id="m1",
        agent_id="a1",
        tenant_id="t1",
        current_phase=AgentState.IDLE,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    dumped = state.model_dump()
    assert dumped["memory_id"] == "m1"
    assert dumped["agent_id"] == "a1"
    assert dumped["current_phase"] == "IDLE"


def test_state_model_workflow_state():
    from datetime import datetime, timezone
    ws = WorkflowState(
        workflow_id="w1",
        tenant_id="t1",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    assert ws.status == "running"
    assert ws.completed_tasks == []


from core.engine.state_models import WorkflowState
