"""
FastAPI app for the Kirin platform agents.
Provides endpoints for enrichment, scoring, messaging, research, and CRM sync.
"""
import asyncio
import json
import logging
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks, Header, Depends, Request
from fastapi.responses import JSONResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
import uvicorn
import os
from agents.pure_functions import VALID_STATUSES
from agents.enricher import enrich_lead
from agents.scorer import score_lead
from agents.messenger import generate_message, send_whatsapp_message
from agents.researcher import research_lead
from agents.crm_connector import get_crm_adapter
from agents.schemas import (
    EnrichRequest, ScoreRequest, MessageRequest, ResearchRequest,
    CRMSyncRequest, DiscourseRequest, LanguageGameRequest,
    ResonanceAnalyzeRequest, ResonanceLookupRequest, ResonanceProspectRequest, ResonanceRecordRequest
)
from agents.metrics import (
    kirin_leads_extracted_total,
    kirin_enrichment_success_total,
    kirin_enrichment_failed_total,
    kirin_lead_score,
    kirin_messages_sent_total,
    kirin_errors_total,
    kirin_active_leads
)
from agents.runtime import initialize_memory_managers, shutdown_memory_managers_async, get_postgres_memory, get_qdrant_memory, get_redis_memory
from agents.discourse_ingestor import ingest_discourse
from agents.language_game import analyze_language_game, batch_analyze
from agents.resonance import analyze_resonance, lookup_resonance, generate_prospect, record_signal

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Kirin Agents API", description="API for Kirin platform agents")


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler to mask internal errors."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Erro interno do servidor"}
    )

# Configuration from environment
LITELLM_URL = os.getenv("LITELLM_URL", "http://litellm:4000")
QWEN_VL_MAX_API_KEY = os.getenv("QWEN_VL_MAX_API_KEY", "")
DEEPSEEK_CHAT_API_KEY = os.getenv("DEEPSEEK_CHAT_API_KEY", "")
MOONSHOT_V1_128K_API_KEY = os.getenv("MOONSHOT_V1_128K_API_KEY", "")
EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL", "")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY", "")
EVOLUTION_INSTANCE_ID = os.getenv("EVOLUTION_INSTANCE_ID", "")
CRM_PROVIDER = os.getenv("CRM_PROVIDER", "")

# Memory manager configuration from environment
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "kirin")
POSTGRES_USER = os.getenv("POSTGRES_USER", "kirin")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")

QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

# API Key authentication
API_KEY = os.getenv("API_KEY", "")
REQUIRE_AUTH = os.getenv("KIRIN_REQUIRE_AUTH", "true").lower() == "true"
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))


async def verify_api_key(x_api_key: str = Header(default="")):
    """Verify API key from header. Requires KIRIN_REQUIRE_AUTH=true (default)."""
    if not REQUIRE_AUTH:
        return  # Dev mode: explicit opt-out via KIRIN_REQUIRE_AUTH=false
    
    if not API_KEY:
        raise HTTPException(
            status_code=500,
            detail="API_KEY não configurada. Defina a variável de ambiente API_KEY."
        )
    
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="API key inválida")


class RateLimiter:
    """Simple in-memory rate limiter using sliding window with IP-based identification."""
    
    def __init__(self, requests_per_minute: int, max_clients: int = 10000):
        self.requests_per_minute = requests_per_minute
        self.max_clients = max_clients
        self.requests: Dict[str, list] = {}
        import time
        self.time = time
    
    def _get_client_id(self, client_ip: str) -> str:
        """Get client identifier from IP address."""
        return f"ip:{client_ip}"
    
    def _cleanup_old_clients(self):
        """Remove old client entries to prevent memory leaks."""
        if len(self.requests) > self.max_clients:
            # Remove oldest 20% of clients
            now = self.time.time()
            sorted_clients = sorted(
                self.requests.keys(),
                key=lambda k: self.requests[k][0] if self.requests[k] else 0
            )
            for key in sorted_clients[:len(sorted_clients) // 5]:
                del self.requests[key]
    
    async def check_rate_limit(self, client_ip: str = "unknown"):
        """Check if request is within rate limit. Raises HTTPException if exceeded."""
        client_id = self._get_client_id(client_ip)
        now = self.time.time()
        window_start = now - 60
        
        # Cleanup old clients periodically
        self._cleanup_old_clients()
        
        # Clean old requests for this client
        if client_id in self.requests:
            self.requests[client_id] = [t for t in self.requests[client_id] if t > window_start]
        else:
            self.requests[client_id] = []
        
        # Check limit
        if len(self.requests[client_id]) >= self.requests_per_minute:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Max {self.requests_per_minute} requests per minute."
            )
        
        # Record request
        self.requests[client_id].append(now)


rate_limiter = RateLimiter(RATE_LIMIT_PER_MINUTE)


async def check_rate_limit(
    request: "Request",
    x_forwarded_for: Optional[str] = Header(default=None)
):
    """Dependency to check rate limit using client IP."""
    # Use X-Forwarded-For if available (behind proxy), otherwise use client IP
    if x_forwarded_for:
        client_ip = x_forwarded_for.split(",")[0].strip()
    elif request.client:
        client_ip = request.client.host
    else:
        client_ip = "unknown"
    
    await rate_limiter.check_rate_limit(client_ip)

# Initialize CRM adapter if provider is set
crm_adapter = None
if CRM_PROVIDER:
    try:
        crm_config = {}  # In a real implementation, this would contain actual config
        crm_adapter = get_crm_adapter(CRM_PROVIDER, crm_config)
    except Exception as e:
        logger.error(f"Failed to initialize CRM adapter for provider {CRM_PROVIDER}: {e}")

# Initialize memory managers on startup
@app.on_event("startup")
async def startup_event():
    logger.info("Starting up Kirin Agents API...")
    # Initialize memory managers
    memory_config = {
        "postgres": {
            "host": POSTGRES_HOST,
            "port": POSTGRES_PORT,
            "database": POSTGRES_DB,
            "user": POSTGRES_USER,
            "password": POSTGRES_PASSWORD
        },
        "qdrant": {
            "host": QDRANT_HOST,
            "port": QDRANT_PORT
        },
        "redis": {
            "host": REDIS_HOST,
            "port": REDIS_PORT,
            "password": REDIS_PASSWORD,
            "db": REDIS_DB
        }
    }
    await initialize_memory_managers(memory_config)
    logger.info("Memory managers initialized")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Kirin Agents API...")
    await shutdown_memory_managers_async()
    logger.info("Memory managers shut down")

# Helper function to get memory managers
def get_memory_managers():
    return {
        "postgres": get_postgres_memory(),
        "qdrant": get_qdrant_memory(),
        "redis": get_redis_memory()
    }

# Endpoint to check memory manager health
@app.get("/memory/health")
async def memory_health():
    postgres = get_postgres_memory()
    qdrant = get_qdrant_memory()
    redis = get_redis_memory()
    return {
        "postgres": postgres is not None,
        "qdrant": qdrant is not None,
        "redis": redis is not None
    }

@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    
    Returns:
        Health status with service checks
    """
    checks = {}
    status = "healthy"
    
    # PostgreSQL
    try:
        pg = get_postgres_memory()
        if pg and pg._pool:
            async with pg._pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            checks["postgres"] = "healthy"
        else:
            checks["postgres"] = "not_initialized"
            status = "degraded"
    except Exception:
        checks["postgres"] = "unhealthy"
        status = "degraded"
    
    # Qdrant
    try:
        qd = get_qdrant_memory()
        if qd and qd._client:
            qd._client.get_collections()
            checks["qdrant"] = "healthy"
        else:
            checks["qdrant"] = "not_initialized"
            status = "degraded"
    except Exception:
        checks["qdrant"] = "unhealthy"
        status = "degraded"
    
    # Redis
    try:
        rd = get_redis_memory()
        if rd and rd._redis:
            await rd._redis.ping()
            checks["redis"] = "healthy"
        else:
            checks["redis"] = "not_initialized"
            status = "degraded"
    except Exception:
        checks["redis"] = "unhealthy"
        status = "degraded"
    
    return {"status": status, "checks": checks}

@app.post("/enrich")
async def enrich_endpoint(lead: EnrichRequest, _=Depends(verify_api_key), __=Depends(check_rate_limit)):
    """
    Enrich a lead using the Enricher agent.
    
    Args:
        lead: Lead data validated by EnrichRequest schema
        
    Returns:
        Enriched lead dictionary
    """
    try:
        # Increment leads extracted counter
        kirin_leads_extracted_total.labels(source="api").inc()
        
        # Convert Pydantic model to dict for agent
        lead_dict = lead.model_dump()
        
        # Call the enricher agent
        enriched_lead = await enrich_lead(lead_dict, LITELLM_URL, QWEN_VL_MAX_API_KEY)
        
        # Update metrics
        if enriched_lead.get("enrichment_success"):
            kirin_enrichment_success_total.inc()
        else:
            kirin_enrichment_failed_total.inc()
        
        return enriched_lead
    except Exception as e:
        logger.error(f"Error in enrich endpoint: {e}")
        kirin_errors_total.labels(component="enricher").inc()
        raise HTTPException(status_code=500, detail="Erro interno no enriquecimento")

@app.post("/score")
async def score_endpoint(lead: ScoreRequest, _=Depends(verify_api_key), __=Depends(check_rate_limit)):
    """
    Score a lead using the Scorer agent.
    
    Args:
        lead: Lead data with dossier validated by ScoreRequest schema
        
    Returns:
        Scored lead dictionary
    """
    try:
        # Call the scorer agent
        scored_lead = await score_lead(lead.dossier, LITELLM_URL, DEEPSEEK_CHAT_API_KEY)
        
        # Update metrics
        score_value = scored_lead.get("score", 0)
        kirin_lead_score.observe(score_value)
        
        return scored_lead
    except Exception as e:
        logger.error(f"Error in score endpoint: {e}")
        kirin_errors_total.labels(component="scorer").inc()
        raise HTTPException(status_code=500, detail="Erro interno na pontuação")

@app.post("/generate_message")
async def generate_message_endpoint(lead: MessageRequest, _=Depends(verify_api_key), __=Depends(check_rate_limit)):
    """
    Generate a WhatsApp message for a lead using the Messenger agent.
    
    Args:
        lead: Lead data with score and dossier validated by MessageRequest schema
        
    Returns:
        Generated message string or None if score < 20
    """
    try:
        # Convert Pydantic model to dict for agent
        lead_dict = lead.model_dump()
        
        # Call the messenger agent
        message = await generate_message(lead_dict, LITELLM_URL, DEEPSEEK_CHAT_API_KEY)
        
        # Update metrics if message was generated
        if message is not None:
            kirin_messages_sent_total.labels(status="generated").inc()
        else:
            kirin_messages_sent_total.labels(status="discarded").inc()
        
        return {"message": message}
    except Exception as e:
        logger.error(f"Error in generate_message endpoint: {e}")
        kirin_errors_total.labels(component="messenger").inc()
        raise HTTPException(status_code=500, detail="Erro interno na geração de mensagem")

@app.post("/research")
async def research_endpoint(lead: ResearchRequest, _=Depends(verify_api_key), __=Depends(check_rate_limit)):
    """
    Research a lead using the Researcher agent.
    
    Args:
        lead: Lead data validated by ResearchRequest schema
        
    Returns:
        Researched lead dictionary
    """
    try:
        # Convert Pydantic model to dict for agent
        lead_dict = lead.model_dump()
        
        # Call the researcher agent
        researched_lead = await research_lead(lead_dict, LITELLM_URL, MOONSHOT_V1_128K_API_KEY)
        
        return researched_lead
    except Exception as e:
        logger.error(f"Error in research endpoint: {e}")
        kirin_errors_total.labels(component="researcher").inc()
        raise HTTPException(status_code=500, detail="Erro interno na pesquisa")

@app.post("/crm_sync")
async def crm_sync_endpoint(lead: CRMSyncRequest, _=Depends(verify_api_key), __=Depends(check_rate_limit)):
    """
    Synchronize a lead with the CRM.
    
    Args:
        lead: Lead data validated by CRMSyncRequest schema
        
    Returns:
        Result of the CRM synchronization
    """
    try:
        if not crm_adapter:
            raise HTTPException(status_code=500, detail="CRM adapter not initialized")
        
        # Convert Pydantic model to dict for adapter
        lead_dict = lead.model_dump()
        
        # Call the CRM adapter to upsert the lead
        result = await crm_adapter.upsert_lead(lead_dict)
        
        return result
    except Exception as e:
        logger.error(f"Error in crm_sync endpoint: {e}")
        kirin_errors_total.labels(component="crm_connector").inc()
        raise HTTPException(status_code=500, detail="Erro interno na sincronização CRM")

@app.get("/metrics")
async def metrics_endpoint():
    """
    Prometheus metrics endpoint.
    
    Returns:
        Prometheus metrics in text format
    """
    from fastapi import Response
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/discourse/ingest")
async def discourse_ingest_endpoint(request: DiscourseRequest, _=Depends(verify_api_key), __=Depends(check_rate_limit)):
    """
    Ingest a raw discourse fragment.
    
    Args:
        request: Discourse data validated by DiscourseRequest schema
    
    Returns:
        Normalized DiscourseFragment dict
    """
    try:
        fragment = await ingest_discourse(
            request.text, request.source, request.context,
            LITELLM_URL, DEEPSEEK_CHAT_API_KEY
        )
        
        return fragment
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in discourse ingest endpoint: {e}")
        kirin_errors_total.labels(component="discourse_ingestor").inc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/discourse/extract")
async def discourse_extract_endpoint(request: DiscourseRequest, _=Depends(verify_api_key), __=Depends(check_rate_limit)):
    """
    Full extraction pipeline: ingest + language game analysis.
    
    Args:
        request: Discourse data validated by DiscourseRequest schema
    
    Returns:
        Dict with 'fragment' and 'analysis' keys
    """
    try:
        # Layer 1: Ingest
        fragment = await ingest_discourse(
            request.text, request.source, request.context,
            LITELLM_URL, DEEPSEEK_CHAT_API_KEY
        )
        
        # Layer 2: Language Game Analysis
        analysis = await analyze_language_game(fragment, LITELLM_URL, DEEPSEEK_CHAT_API_KEY)
        
        return {
            "fragment": fragment,
            "analysis": analysis,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in discourse extract endpoint: {e}")
        kirin_errors_total.labels(component="discourse_pipeline").inc()
        raise HTTPException(status_code=500, detail="Erro interno na extração de discurso")


@app.post("/resonance/analyze")
async def resonance_analyze_endpoint(request: ResonanceAnalyzeRequest, _=Depends(verify_api_key), __=Depends(check_rate_limit)):
    """
    Analyze resonance patterns across multiple language game analyses.
    
    Args:
        request: Resonance data validated by ResonanceAnalyzeRequest schema
    
    Returns:
        ResonanceCluster dict
    """
    try:
        cluster = await analyze_resonance(
            request.analyses, request.market_cluster,
            LITELLM_URL, DEEPSEEK_CHAT_API_KEY
        )
        
        return cluster
    except Exception as e:
        logger.error(f"Error in resonance analyze endpoint: {e}")
        kirin_errors_total.labels(component="resonance").inc()
        raise HTTPException(status_code=500, detail="Erro interno na análise de ressonância")


@app.post("/resonance/lookup")
async def resonance_lookup_endpoint(request: ResonanceLookupRequest, _=Depends(verify_api_key), __=Depends(check_rate_limit)):
    """
    Search for similar resonance patterns.
    
    Args:
        request: Resonance data validated by ResonanceLookupRequest schema
    
    Returns:
        List of matching ResonanceCluster dicts
    """
    try:
        results = await lookup_resonance(
            request.query, LITELLM_URL, DEEPSEEK_CHAT_API_KEY, request.limit
        )
        
        return {"results": results, "count": len(results)}
    except Exception as e:
        logger.error(f"Error in resonance lookup endpoint: {e}")
        kirin_errors_total.labels(component="resonance").inc()
        raise HTTPException(status_code=500, detail="Erro interno na busca de ressonância")


@app.post("/prospects/generate")
async def prospect_generate_endpoint(request: ResonanceProspectRequest, _=Depends(verify_api_key), __=Depends(check_rate_limit)):
    """
    Generate a prospect profile from language game analysis.
    
    Args:
        request: Prospect data validated by ResonanceProspectRequest schema
    
    Returns:
        ProspectProfile dict
    """
    try:
        prospect = await generate_prospect(
            request.target_profile, None,
            LITELLM_URL, DEEPSEEK_CHAT_API_KEY
        )
        
        return prospect
    except Exception as e:
        logger.error(f"Error in prospect generate endpoint: {e}")
        kirin_errors_total.labels(component="prospect_generator").inc()
        raise HTTPException(status_code=500, detail="Erro interno na geração de prospect")


@app.post("/resonance/signal")
async def resonance_signal_endpoint(request: ResonanceRecordRequest, _=Depends(verify_api_key), __=Depends(check_rate_limit)):
    """
    Record a market response signal for a resonance cluster.
    
    Args:
        request: Signal data validated by ResonanceRecordRequest schema
    
    Returns:
        Recorded signal dict
    """
    try:
        signal = await record_signal(
            request.lead_id, request.source, 1.0, {"text": request.text}
        )
        
        return signal
    except Exception as e:
        logger.error(f"Error in resonance signal endpoint: {e}")
        kirin_errors_total.labels(component="resonance").inc()
        raise HTTPException(status_code=500, detail="Erro interno no registro de sinal")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
