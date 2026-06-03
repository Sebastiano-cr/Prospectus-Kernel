"""
Pydantic schemas for request validation.
All POST endpoints use these schemas to validate input data.
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any


class EnrichRequest(BaseModel):
    """Schema for /enrich endpoint."""
    lead_id: str = Field(..., min_length=1, max_length=100, description="Unique lead identifier")
    name: str = Field(..., min_length=1, max_length=200, description="Business name")
    address: str = Field(default="", max_length=500, description="Business address")
    phone: str = Field(default="", max_length=20, description="Phone number")
    website: str = Field(default="", max_length=500, description="Website URL")
    instagram_username: str = Field(default="", max_length=100, description="Instagram username")
    rating: Optional[float] = Field(default=None, ge=0, le=5, description="Google Maps rating")
    google_maps_url: str = Field(default="", max_length=500, description="Google Maps URL")
    
    class Config:
        extra = "forbid"  # Reject unknown fields


class ScoreRequest(BaseModel):
    """Schema for /score endpoint."""
    lead_id: str = Field(..., min_length=1, description="Unique lead identifier")
    dossier: Dict[str, Any] = Field(..., description="Enrichment dossier")
    
    class Config:
        extra = "forbid"


class MessageRequest(BaseModel):
    """Schema for /generate_message endpoint."""
    lead_id: str = Field(..., min_length=1, description="Unique lead identifier")
    name: str = Field(..., min_length=1, max_length=200, description="Business name")
    score: int = Field(..., ge=0, le=100, description="Lead score")
    faixa: str = Field(..., description="Score classification (frio/morno/quente)")
    dossier: Dict[str, Any] = Field(..., description="Enrichment dossier")
    
    class Config:
        extra = "forbid"


class ResearchRequest(BaseModel):
    """Schema for /research endpoint."""
    lead_id: str = Field(..., min_length=1, description="Unique lead identifier")
    name: str = Field(..., min_length=1, max_length=200, description="Business name")
    address: str = Field(default="", max_length=500, description="Business address")
    city: str = Field(default="", max_length=100, description="City")
    
    class Config:
        extra = "forbid"


class CRMSyncRequest(BaseModel):
    """Schema for /crm_sync endpoint."""
    lead_id: str = Field(..., min_length=1, description="Unique lead identifier")
    action: str = Field(..., pattern="^(create|update|upsert)$", description="CRM action")
    data: Dict[str, Any] = Field(..., description="Lead data to sync")
    
    class Config:
        extra = "forbid"


class DiscourseRequest(BaseModel):
    """Schema for /discourse/ingest endpoint."""
    text: str = Field(..., min_length=1, max_length=10000, description="Text to analyze")
    source: str = Field(..., min_length=1, max_length=100, description="Source identifier")
    context: str = Field(default="", max_length=1000, description="Additional context")
    
    class Config:
        extra = "forbid"


class LanguageGameRequest(BaseModel):
    """Schema for /language_game/analyze endpoint."""
    text: str = Field(..., min_length=1, max_length=10000, description="Text to analyze")
    lead_id: str = Field(default="", max_length=100, description="Associated lead ID")
    
    class Config:
        extra = "forbid"


class ResonanceAnalyzeRequest(BaseModel):
    """Schema for /resonance/analyze endpoint."""
    analyses: list = Field(..., min_length=1, description="List of language game analyses")
    market_cluster: str = Field(default="", max_length=100, description="Market cluster name")
    
    class Config:
        extra = "forbid"


class ResonanceLookupRequest(BaseModel):
    """Schema for /resonance/lookup endpoint."""
    query: str = Field(..., min_length=1, max_length=500, description="Search query")
    limit: int = Field(default=5, ge=1, le=50, description="Max results to return")
    
    class Config:
        extra = "forbid"


class ResonanceProspectRequest(BaseModel):
    """Schema for /resonance/prospect endpoint."""
    cluster_id: str = Field(..., min_length=1, description="Cluster ID")
    target_profile: dict = Field(..., description="Target profile")
    
    class Config:
        extra = "forbid"


class ResonanceRecordRequest(BaseModel):
    """Schema for /resonance/record endpoint."""
    text: str = Field(..., min_length=1, max_length=10000, description="Text to record")
    lead_id: str = Field(default="", max_length=100, description="Associated lead ID")
    source: str = Field(default="api", max_length=50, description="Source identifier")
    
    class Config:
        extra = "forbid"
