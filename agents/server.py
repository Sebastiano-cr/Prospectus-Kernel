"""
FastAPI app for the Kirin platform agents.
Provides endpoints for enrichment, scoring, messaging, research, and CRM sync.
"""
import asyncio
import json
import logging
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks, Header, Depends
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
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))


async def verify_api_key(x_api_key: str = Header(default="")):
    """Verify API key from header. If API_KEY is not configured, allows all requests."""
    if not API_KEY:
        return  # Dev mode: no auth required
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


class RateLimiter:
    """Simple in-memory rate limiter using sliding window."""
    
    def __init__(self, requests_per_minute: int):
        self.requests_per_minute = requests_per_minute
        self.requests: Dict[str, list] = {}
    
    def _get_client_id(self, x_api_key: str, x_forwarded_for: Optional[str] = None) -> str:
        """Get client identifier from API key or IP."""
        if x_api_key:
            return f"apikey:{x_api_key[:8]}"
        if x_forwarded_for:
            return f"ip:{x_forwarded_for.split(',')[0].strip()}"
        return "ip:unknown"
    
    async def check_rate_limit(self, x_api_key: str = "", x_forwarded_for: Optional[str] = None):
        """Check if request is within rate limit. Raises HTTPException if exceeded."""
        client_id = self._get_client_id(x_api_key, x_forwarded_for)
        now = __import__('time').time()
        window_start = now - 60
        
        # Clean old requests
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
    x_api_key: str = Header(default=""),
    x_forwarded_for: Optional[str] = Header(default=None)
):
    """Dependency to check rate limit."""
    await rate_limiter.check_rate_limit(x_api_key, x_forwarded_for)

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
async def enrich_endpoint(lead: Dict[str, Any], _=Depends(verify_api_key), __=Depends(check_rate_limit)):
    """
    Enrich a lead using the Enricher agent.
    
    Args:
        lead: Lead dictionary
        
    Returns:
        Enriched lead dictionary
    """
    try:
        # Increment leads extracted counter
        kirin_leads_extracted_total.labels(source="api").inc()
        
        # Get memory managers
        memory_managers = get_memory_managers()
        
        # Call the enricher agent with memory managers
        # Note: We need to modify the enrich_lead function to accept memory managers.
        # For now, we will call the existing function and then update it later.
        # Let's update the agent functions to accept memory managers.
        # We'll do that in the next step.
        
        # For now, we'll call the existing function without memory managers.
        # We'll update the agent functions in the next batch of changes.
        enriched_lead = await enrich_lead(lead, LITELLM_URL, QWEN_VL_MAX_API_KEY)
        
        # Update metrics
        if enriched_lead.get("enrichment_success"):
            kirin_enrichment_success_total.inc()
        else:
            kirin_enrichment_failed_total.inc()
        
        # Store enrichment result in memory if successful
        if enriched_lead.get("enrichment_success") and lead.get("id"):
            lead_id = lead["id"]
            dossie = enriched_lead.get("dossie", {})
            # We would store the dossie in memory, but we need to update the agent to return the dossie separately or we can extract it here.
            # For now, we'll skip storing in memory until we update the agent to work with memory managers.
            pass
        
        return enriched_lead
    except Exception as e:
        logger.error(f"Error in enrich endpoint: {e}")
        kirin_errors_total.labels(component="enricher").inc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/score")
async def score_endpoint(lead: Dict[str, Any], _=Depends(verify_api_key), __=Depends(check_rate_limit)):
    """
    Score a lead using the Scorer agent.
    
    Args:
        lead: Lead dictionary with dossiê
        
    Returns:
        Scored lead dictionary
    """
    try:
        # Get dossiê from lead
        dossie = lead.get("dossie", {})
        if not dossie:
            raise HTTPException(status_code=400, detail="Lead must have a dossiê to be scored")
        
        # Call the scorer agent
        scored_lead = await score_lead(dossie, LITELLM_URL, DEEPSEEK_CHAT_API_KEY)
        
        # Update metrics
        score_value = scored_lead.get("score", 0)
        kirin_lead_score.observe(score_value)
        
        return scored_lead
    except Exception as e:
        logger.error(f"Error in score endpoint: {e}")
        kirin_errors_total.labels(component="scorer").inc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate_message")
async def generate_message_endpoint(lead: Dict[str, Any], _=Depends(verify_api_key), __=Depends(check_rate_limit)):
    """
    Generate a WhatsApp message for a lead using the Messenger agent.
    
    Args:
        lead: Lead dictionary with score and dossiê
        
    Returns:
        Generated message string or None if score < 20
    """
    try:
        # Check if lead has score
        if "score" not in lead:
            raise HTTPException(status_code=400, detail="Lead must have a score to generate a message")
        
        # Call the messenger agent
        message = await generate_message(lead, LITELLM_URL, DEEPSEEK_CHAT_API_KEY)
        
        # Update metrics if message was generated
        if message is not None:
            kirin_messages_sent_total.labels(status="generated").inc()
        else:
            kirin_messages_sent_total.labels(status="discarded").inc()
        
        return {"message": message}
    except Exception as e:
        logger.error(f"Error in generate_message endpoint: {e}")
        kirin_errors_total.labels(component="messenger").inc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/research")
async def research_endpoint(lead: Dict[str, Any], _=Depends(verify_api_key), __=Depends(check_rate_limit)):
    """
    Research a lead using the Researcher agent.
    
    Args:
        lead: Lead dictionary
        
    Returns:
        Researched lead dictionary
    """
    try:
        # Only research leads with score >= 70
        if lead.get("score", 0) < 70:
            return lead  # Return lead unchanged if score too low
        
        # Call the researcher agent
        researched_lead = await research_lead(lead, LITELLM_URL, MOONSHOT_V1_128K_API_KEY)
        
        return researched_lead
    except Exception as e:
        logger.error(f"Error in research endpoint: {e}")
        kirin_errors_total.labels(component="researcher").inc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/crm_sync")
async def crm_sync_endpoint(lead: Dict[str, Any], _=Depends(verify_api_key), __=Depends(check_rate_limit)):
    """
    Synchronize a lead with the CRM.
    
    Args:
        lead: Lead dictionary
        
    Returns:
        Result of the CRM synchronization
    """
    try:
        if not crm_adapter:
            raise HTTPException(status_code=500, detail="CRM adapter not initialized")
        
        # Call the CRM adapter to upsert the lead
        result = await crm_adapter.upsert_lead(lead)
        
        return result
    except Exception as e:
        logger.error(f"Error in crm_sync endpoint: {e}")
        kirin_errors_total.labels(component="crm_connector").inc()
        raise HTTPException(status_code=500, detail=str(e))

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
async def discourse_ingest_endpoint(request: Dict[str, Any], _=Depends(verify_api_key), __=Depends(check_rate_limit)):
    """
    Ingest a raw discourse fragment.
    
    Args:
        request: Dict with 'text' (required), 'source' (required), 'context' (optional)
    
    Returns:
        Normalized DiscourseFragment dict
    """
    try:
        text = request.get("text", "")
        source = request.get("source", "other")
        context = request.get("context", "")
        
        if not text:
            raise HTTPException(status_code=400, detail="text is required")
        
        fragment = await ingest_discourse(text, source, context, LITELLM_URL, DEEPSEEK_CHAT_API_KEY)
        
        return fragment
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in discourse ingest endpoint: {e}")
        kirin_errors_total.labels(component="discourse_ingestor").inc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/discourse/extract")
async def discourse_extract_endpoint(request: Dict[str, Any], _=Depends(verify_api_key), __=Depends(check_rate_limit)):
    """
    Full extraction pipeline: ingest + language game analysis.
    
    Args:
        request: Dict with 'text' (required), 'source' (required), 'context' (optional)
    
    Returns:
        Dict with 'fragment' and 'analysis' keys
    """
    try:
        text = request.get("text", "")
        source = request.get("source", "other")
        context = request.get("context", "")
        
        if not text:
            raise HTTPException(status_code=400, detail="text is required")
        
        # Layer 1: Ingest
        fragment = await ingest_discourse(text, source, context, LITELLM_URL, DEEPSEEK_CHAT_API_KEY)
        
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
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/resonance/analyze")
async def resonance_analyze_endpoint(request: Dict[str, Any], _=Depends(verify_api_key), __=Depends(check_rate_limit)):
    """
    Analyze resonance patterns across multiple language game analyses.
    
    Args:
        request: Dict with 'analyses' (list of analysis dicts), 'market_cluster' (optional)
    
    Returns:
        ResonanceCluster dict
    """
    try:
        analyses = request.get("analyses", [])
        market_cluster = request.get("market_cluster", "")
        
        if not analyses:
            raise HTTPException(status_code=400, detail="analyses list is required")
        
        cluster = await analyze_resonance(analyses, market_cluster, LITELLM_URL, DEEPSEEK_CHAT_API_KEY)
        
        return cluster
    except Exception as e:
        logger.error(f"Error in resonance analyze endpoint: {e}")
        kirin_errors_total.labels(component="resonance").inc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/resonance/lookup")
async def resonance_lookup_endpoint(request: Dict[str, Any], _=Depends(verify_api_key), __=Depends(check_rate_limit)):
    """
    Search for similar resonance patterns.
    
    Args:
        request: Dict with 'query' (required), 'limit' (optional, default 5)
    
    Returns:
        List of matching ResonanceCluster dicts
    """
    try:
        query = request.get("query", "")
        limit = request.get("limit", 5)
        
        if not query:
            raise HTTPException(status_code=400, detail="query is required")
        
        results = await lookup_resonance(query, LITELLM_URL, DEEPSEEK_CHAT_API_KEY, limit)
        
        return {"results": results, "count": len(results)}
    except Exception as e:
        logger.error(f"Error in resonance lookup endpoint: {e}")
        kirin_errors_total.labels(component="resonance").inc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/prospects/generate")
async def prospect_generate_endpoint(request: Dict[str, Any], _=Depends(verify_api_key), __=Depends(check_rate_limit)):
    """
    Generate a prospect profile from language game analysis.
    
    Args:
        request: Dict with 'analysis' (required), 'resonance' (optional)
    
    Returns:
        ProspectProfile dict
    """
    try:
        analysis = request.get("analysis", {})
        resonance = request.get("resonance", None)
        
        if not analysis:
            raise HTTPException(status_code=400, detail="analysis is required")
        
        prospect = await generate_prospect(analysis, resonance, LITELLM_URL, DEEPSEEK_CHAT_API_KEY)
        
        return prospect
    except Exception as e:
        logger.error(f"Error in prospect generate endpoint: {e}")
        kirin_errors_total.labels(component="prospect_generator").inc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/resonance/signal")
async def resonance_signal_endpoint(request: Dict[str, Any], _=Depends(verify_api_key), __=Depends(check_rate_limit)):
    """
    Record a market response signal for a resonance cluster.
    
    Args:
        request: Dict with 'cluster_id' (required), 'signal_type' (required), 
                 'strength' (required, 0.0-1.0), 'metadata' (optional)
    
    Returns:
        Recorded signal dict
    """
    try:
        cluster_id = request.get("cluster_id", "")
        signal_type = request.get("signal_type", "")
        strength = request.get("strength", 0.0)
        metadata = request.get("metadata", {})
        
        if not cluster_id or not signal_type:
            raise HTTPException(status_code=400, detail="cluster_id and signal_type are required")
        
        signal = await record_signal(cluster_id, signal_type, strength, metadata)
        
        return signal
    except Exception as e:
        logger.error(f"Error in resonance signal endpoint: {e}")
        kirin_errors_total.labels(component="resonance").inc()
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
