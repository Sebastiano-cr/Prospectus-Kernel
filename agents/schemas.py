"""
Pydantic schemas for Kirin platform API endpoints.
"""
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


class EnrichRequest(BaseModel):
    """Request schema for POST /enrich."""
    id: Optional[str] = None
    google_maps_id: Optional[str] = None
    name: str = ''
    address: str = ''
    phone: str = ''
    website: str = ''
    instagram_username: str = ''
    google_maps_data: Dict[str, Any] = Field(default_factory=dict)
    google_maps_rating: Optional[float] = None
    google_maps_screenshot: Optional[str] = None
    instagram_data: Dict[str, Any] = Field(default_factory=dict)
    instagram_followers: Optional[int] = None
    instagram_post_count: Optional[int] = None
    instagram_last_post_date: Optional[str] = None
    instagram_recent_images: List[str] = Field(default_factory=list)
    instagram_inativo: bool = False
    instagram_status: str = ''
    instagram_screenshot: Optional[str] = None
    website_screenshot: Optional[str] = None


class ScoreRequest(BaseModel):
    """Request schema for POST /score."""
    id: Optional[str] = None
    name: str = ''
    dossie: Dict[str, Any] = Field(default_factory=dict)


class MessageRequest(BaseModel):
    """Request schema for POST /generate_message."""
    id: Optional[str] = None
    name: str = ''
    score: int = 0
    faixa: str = ''
    status: str = 'novo'
    dossie: Dict[str, Any] = Field(default_factory=dict)
    website: str = ''
    instagram_username: str = ''
    phone: str = ''
