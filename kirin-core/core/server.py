import os
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException

from core.agents.base_agent import InvokeRequest, InvokeResponse, AgentState
from core.engine.execution_engine import ExecutionEngine, ConflictError
from core.memory.memory_manager import MemoryManager
from core.memory.redis_store import RedisStore
from core.memory.postgres_store import PostgresStore
from core.memory.qdrant_store import QdrantStore
from core.providers.provider_router import ProviderRouter
from core.registry.capability_registry import (
    CapabilityRegistry,
    Capability,
    CostProfile,
    LatencyProfile,
)
from core.governance.policy_engine import PolicyEngine
from core.observability.tracer import Tracer

_engine: ExecutionEngine | None = None
_policy: PolicyEngine | None = None
_tracer: Tracer | None = None
_registry: CapabilityRegistry | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _engine, _policy, _tracer, _registry

    _tracer = Tracer()
    mm = MemoryManager(
        redis=RedisStore(os.environ.get("REDIS_URL", "redis://localhost:6379")),
        postgres=PostgresStore(os.environ.get("POSTGRES_URL", "postgresql://localhost:5432")),
        qdrant=QdrantStore(os.environ.get("QDRANT_URL", "http://localhost:6333")),
    )
    _engine = ExecutionEngine(mm)
    _policy = PolicyEngine()

    _registry = CapabilityRegistry()
    _registry.register(Capability(
        name="score_lead",
        description="Calcula score de propensão de compra de um lead",
        input_schema={"type": "object", "properties": {"dossie": {"type": "object"}}},
        output_schema={"type": "object", "properties": {"score": {"type": "integer"}, "faixa": {"type": "string"}}},
        provider_requirements=["deepseek-chat"],
        cost_profile=CostProfile(cost_per_call_usd=0.001, tokens_per_call_avg=512),
        latency_profile=LatencyProfile(p50_ms=800, p95_ms=2000, p99_ms=4000),
        deterministic=False,
        tags=["lead", "scoring"],
    ))
    _registry.register(Capability(
        name="enrich_lead",
        description="Enriquece dados de um lead com informações externas",
        input_schema={"type": "object", "properties": {"lead": {"type": "object"}}},
        output_schema={"type": "object", "properties": {"dossie": {"type": "object"}}},
        provider_requirements=["qwen-vl-max"],
        cost_profile=CostProfile(cost_per_call_usd=0.003, tokens_per_call_avg=1024),
        latency_profile=LatencyProfile(p50_ms=1200, p95_ms=3000, p99_ms=6000),
        deterministic=False,
        tags=["lead", "enrichment", "multimodal"],
    ))

    await _engine.restore_executing_agents()
    yield


app = FastAPI(title="Kirin Core", version="2.0.0", lifespan=lifespan)


@app.post("/invoke", response_model=InvokeResponse)
async def invoke(request: InvokeRequest):
    await _policy.check(request)
    agent = _build_agent(request)
    try:
        return await _engine.run(agent, request)
    except ConflictError:
        raise HTTPException(status_code=409, detail="Agent já em execução para este memory_id")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.get("/agents/{memory_id}/state")
async def get_state(memory_id: str, tenant_id: str = "default"):
    agent = _engine._active.get(memory_id)
    if agent is None:
        snap = await _engine.restore_from_snapshot(memory_id, tenant_id)
        if snap is None:
            raise HTTPException(status_code=404, detail=f"memory_id={memory_id} não encontrado")
        return {"memory_id": memory_id, "state": snap["current_phase"]}
    return {"memory_id": memory_id, "state": agent.state}


@app.post("/agents/{memory_id}/heartbeat")
async def heartbeat(memory_id: str):
    await _engine.renew_heartbeat(memory_id)
    return {"ok": True}


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0", "phase": "2"}


@app.get("/capabilities")
async def list_capabilities():
    return {"capabilities": [c.model_dump() for c in _registry.all()]}


@app.get("/capabilities/{name}")
async def get_capability(name: str):
    cap = _registry.get(name)
    if cap is None:
        raise HTTPException(status_code=404, detail=f"Capability '{name}' não encontrada")
    return cap.model_dump()


@app.post("/enrich")
async def compat_enrich(lead: dict):
    req = InvokeRequest(
        goal="enrich_lead",
        context={"lead": lead},
        memory_id=lead.get("id", "default"),
        mode="autonomous",
    )
    resp = await invoke(req)
    return resp.result


@app.post("/score")
async def compat_score(payload: dict):
    req = InvokeRequest(
        goal="score_lead",
        context={"dossie": payload.get("dossie", payload)},
        memory_id=payload.get("id", "default"),
        mode="autonomous",
    )
    resp = await invoke(req)
    return resp.result


@app.post("/generate_message")
async def compat_generate_message(payload: dict):
    req = InvokeRequest(
        goal="generate_message",
        context=payload,
        memory_id=payload.get("id", "default"),
        mode="autonomous",
    )
    resp = await invoke(req)
    return resp.result


@app.post("/research")
async def compat_research(lead: dict):
    req = InvokeRequest(
        goal="research_lead",
        context={"lead": lead},
        memory_id=lead.get("id", "default"),
        mode="autonomous",
    )
    resp = await invoke(req)
    return resp.result


@app.post("/crm_sync")
async def compat_crm_sync(lead: dict):
    req = InvokeRequest(
        goal="crm_sync",
        context={"lead": lead},
        memory_id=lead.get("id", "default"),
        mode="autonomous",
    )
    resp = await invoke(req)
    return resp.result


def _build_agent(request: InvokeRequest):
    from core.agents.enrich_agent import EnrichAgent
    from core.agents.score_agent import ScoreAgent
    from core.agents.message_agent import MessageAgent
    from core.agents.research_agent import ResearchAgent
    from core.agents.crm_agent import CRMAgent

    mm = _engine.memory_manager
    pr = ProviderRouter(tracer=_tracer)
    registry = {
        "enrich_lead": EnrichAgent,
        "score_lead": ScoreAgent,
        "generate_message": MessageAgent,
        "research_lead": ResearchAgent,
        "crm_sync": CRMAgent,
    }
    cls = registry.get(request.goal)
    if cls is None:
        raise ValueError(f"goal desconhecido: {request.goal}")
    agent = cls(agent_id=request.goal)
    agent._current_memory_id = request.memory_id
    agent._tenant_id = request.tenant_id
    return agent


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
