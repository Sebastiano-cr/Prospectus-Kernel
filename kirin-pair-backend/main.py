"""
Kirin Pair Backend - Main FastAPI Application
"""
import asyncio
import logging
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Depends, Header, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
import uvicorn
import os
import jwt
import time
from datetime import datetime, timedelta

# Import pair agents
sys_path_added = False
if '/app/pair_agents' not in __import__('sys').path:
    __import__('sys').path.insert(0, '/app/pair_agents')
    sys_path_added = True

from profile_study import get_profile_study_agent
from prospect import get_prospect_agent

# Import memory managers (from kirin-platform runtime) and initialization function
from agents.runtime import (
    get_postgres_memory, 
    get_qdrant_memory, 
    get_redis_memory, 
    is_initialized,
    initialize_memory_managers,
    shutdown_memory_managers_async
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Kirin Pair API", description="API for Kirin Pair cognitive runtime")

# Security
security = HTTPBearer()
JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_MINUTES = int(os.getenv("JWT_EXPIRATION_MINUTES", "60"))

# Dependency to get current workspace from JWT token
async def get_current_workspace(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        workspace_id = payload.get("workspace_id")
        if workspace_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing workspace_id",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return workspace_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

# Dependency to ensure memory managers are initialized
async def ensure_memory_managers():
    if not is_initialized():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Memory managers not initialized"
        )

# Initialize memory managers on startup
@app.on_event("startup")
async def startup_event():
    logger.info("Starting up Kirin Pair API...")
    # Initialize memory managers using the same configuration as the agents service
    memory_config = {
        "postgres": {
            "host": os.getenv("POSTGRES_HOST", "postgres"),
            "port": int(os.getenv("POSTGRES_PORT", "5432")),
            "database": os.getenv("POSTGRES_DB", "kirin"),
            "user": os.getenv("POSTGRES_USER", "kirin"),
            "password": os.getenv("POSTGRES_PASSWORD", "")
        },
        "qdrant": {
            "host": os.getenv("QDRANT_HOST", "qdrant"),
            "port": int(os.getenv("QDRANT_PORT", "6333"))
        },
        "redis": {
            "host": os.getenv("REDIS_HOST", "redis"),
            "port": int(os.getenv("REDIS_PORT", "6379")),
            "password": os.getenv("REDIS_PASSWORD", None),
            "db": int(os.getenv("REDIS_DB", "0"))
        }
    }
    await initialize_memory_managers(memory_config)
    logger.info("Memory managers initialized successfully")

# Shutdown event to clean up memory managers
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Kirin Pair API...")
    await shutdown_memory_managers_async()
    logger.info("Memory managers shut down")

# Health check endpoint
@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    Returns the status of the service and its dependencies.
    """
    # Check if memory managers are initialized
    memory_initialized = is_initialized()
    
    # TODO: Add checks for external services (kirin-platform, whisper-service, etc.)
    
    return {
        "status": "healthy" if memory_initialized else "initializing",
        "memory_managers_initialized": memory_initialized,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

# Example endpoint to demonstrate agent usage (to be implemented)
@app.post("/test")
async def test_endpoint(
    workspace_id: str = Depends(get_current_workspace),
    _: bool = Depends(ensure_memory_managers)
):
    """
    Test endpoint to verify authentication and memory manager access.
    """
    # Get memory manager instances
    postgres = get_postgres_memory()
    qdrant = get_qdrant_memory()
    redis = get_redis_memory()
    
    return {
        "message": "Kirin Pair backend is operational",
        "workspace_id": workspace_id,
        "memory_managers": {
            "postgres": postgres is not None,
            "qdrant": qdrant is not None,
            "redis": redis is not None
        }
    }

# Pair Linguístico endpoints
@app.post("/style-profile")
async def get_or_create_style_profile(
    workspace_id: str = Depends(get_current_workspace),
    _: bool = Depends(ensure_memory_managers),
    days_back: int = 30,
    limit: int = 1000,
    force_refresh: bool = False
):
    """
    Get or create a style profile for a workspace.
    If force_refresh is True, or no profile exists, analyze communications to create/update profile.
    """
    profile_study_agent = get_profile_study_agent()
    
    # Try to get existing profile first (unless forcing refresh)
    if not force_refresh:
        existing_profile = await profile_study_agent.get_workspace_profile(workspace_id)
        if existing_profile:
            return {
                "workspace_id": workspace_id,
                "profile": existing_profile,
                "source": "cached",
                "timestamp": datetime.utcnow().isoformat()
            }
    
    # Analyze communications to create/update profile
    style_profile = await profile_study_agent.analyze_workspace_communications(
        workspace_id=workspace_id,
        days_back=days_back,
        limit=limit
    )
    
    # Save the profile
    await profile_study_agent.update_workspace_profile(workspace_id, style_profile)
    
    return {
        "workspace_id": workspace_id,
        "profile": style_profile,
        "source": "analyzed",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/prospect/process")
async def process_new_lead(
    lead_data: Dict[str, Any],
    workspace_id: str = Depends(get_current_workspace),
    _: bool = Depends(ensure_memory_managers)
):
    """
    Process a new lead through the prospecting pipeline:
    enrichment -> scoring -> message generation.
    """
    prospect_agent = get_prospect_agent()
    
    result = await prospect_agent.process_new_lead(
        lead_data=lead_data,
        workspace_id=workspace_id
    )
    
    return result

@app.post("/prospect/enrich-and-score")
async def enrich_and_score_lead(
    lead_data: Dict[str, Any],
    workspace_id: str = Depends(get_current_workspace),
    _: bool = Depends(ensure_memory_managers)
):
    """
    Enrich and score a lead using the kirin-platform pipelines.
    """
    prospect_agent = get_prospect_agent()
    
    result = await prospect_agent.enrich_and_score_lead(
        lead_data=lead_data,
        workspace_id=workspace_id
    )
    
    return result

@app.post("/prospect/generate-message")
async def generate_outreach_message(
    lead_data: Dict[str, Any],
    workspace_id: str = Depends(get_current_workspace),
    style_profile: Optional[Dict[str, Any]] = None,
    message_type: str = "initial_outreach",
    _: bool = Depends(ensure_memory_managers)
):
    """
    Generate an outreach message for a lead based on workspace style and lead data.
    """
    prospect_agent = get_prospect_agent()
    
    result = await prospect_agent.generate_outreach_message(
        lead_data=lead_data,
        workspace_id=workspace_id,
        style_profile=style_profile,
        message_type=message_type
    )
    
    return result

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8002")))
