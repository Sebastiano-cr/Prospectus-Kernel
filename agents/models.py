"""
Data models for the Kirin platform.
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime


@dataclass
class Lead:
    """Lead data model."""
    # Identification
    id: Optional[str] = None
    google_maps_id: Optional[str] = None
    name: str = ""
    address: str = ""
    phone: str = ""
    website: str = ""
    instagram_username: str = ""
    
    # Google Maps data
    google_maps_data: Dict[str, Any] = field(default_factory=dict)
    google_maps_rating: Optional[float] = None
    google_maps_screenshot: Optional[str] = None  # base64 encoded
    
    # Instagram data
    instagram_data: Dict[str, Any] = field(default_factory=dict)
    instagram_followers: Optional[int] = None
    instagram_post_count: Optional[int] = None
    instagram_last_post_date: Optional[str] = None
    instagram_recent_images: List[str] = field(default_factory=list)
    instagram_inativo: bool = False
    instagram_status: str = ""  # ativo, inativo, privado, não encontrado, bloqueado
    instagram_screenshot: Optional[str] = None  # base64 encoded
    
    # Website data
    website_screenshot: Optional[str] = None  # base64 encoded
    
    # Enrichment
    dossie: Dict[str, Any] = field(default_factory=dict)
    enrichment_success: bool = False
    enrichment_failed: bool = False
    enrichment_error: Optional[str] = None
    
    # Scoring
    score: int = 0
    score_justification: str = ""
    faixa: str = ""  # frio, morno, quente
    
    # Research
    pesquisa: Dict[str, Any] = field(default_factory=dict)
    
    # Messaging
    generated_message: Optional[str] = None
    whatsapp_status: str = ""  # enviado, falha, telefone_inválido, etc.
    message_sent_at: Optional[str] = None
    delivery_status: str = ""
    message_id: Optional[str] = None
    
    # CRM and pipeline
    status: str = "novo"  # novo, contato_inicial, agendamento, enriquecido, qualificado, mensagem_enviada, respondeu, vendido, repassado, descartado
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # Resale fields
    sale_value: Optional[float] = None
    sale_date: Optional[str] = None
    sale_owner: Optional[str] = None
    resale_partner: Optional[str] = None
    resale_date: Optional[str] = None
    resale_commission: Optional[float] = None


@dataclass
class CampaignConfig:
    """Campaign configuration model."""
    # Targeting
    niche: str = ""
    location: str = ""
    limit: int = 10
    
    # Scoring thresholds
    score_threshold_research: int = 70  # Minimum score to trigger Kimi K2 research
    score_threshold_message: int = 20   # Minimum score to send message
    
    # Messaging
    daily_message_limit: int = 200
    message_interval_min: int = 30      # seconds
    message_interval_max: int = 120     # seconds
    
    # Processing
    max_concurrent_leads: int = 10
    enable_research: bool = True
    enable_messaging: bool = True
    enable_crm_sync: bool = True
    
    # Timing
    start_hour: int = 9                 # Start sending messages at 9 AM
    end_hour: int = 18                  # Stop sending messages at 6 PM
    
    # API Keys (should come from environment in practice)
    qwen_vl_max_api_key: str = ""
    deepseek_chat_api_key: str = ""
    moonshot_v1_128k_api_key: str = ""
    
    # API URLs
    litellm_url: str = "http://litellm:4000"
    evolution_api_url: str = ""
    evolution_api_key: str = ""
    evolution_instance_id: str = ""
    
    # CRM
    crm_provider: str = ""  # notion, airtable, nocodb
    crm_config: Dict[str, Any] = field(default_factory=dict)
    
    # Google Maps scraping
    max_concurrent_sessions: int = 3
    playwright_timeout: int = 30000     # milliseconds
    
    # Instagram scraping
    instagram_decoy_user: str = ""
    instagram_decoy_pass: str = ""
    instagram_third_party_api_url: str = ""
    
    # Feature flags
    enable_anti_detection: bool = False
    enable_human_simulation: bool = False