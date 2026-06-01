"""
Kirin Agents Package
"""
from .memory import BaseMemoryManager
from .models import Lead, CampaignConfig
from .pure_functions import (
    normalize_score,
    classify_faixa,
    deduplicate_leads,
    compute_instagram_inativo,
    truncate_message,
    is_valid_status,
    can_send_message_sync,
    build_mcp_error,
    VALID_STATUSES,
    BLOCKED_STATUSES
)

from .discourse_models import (
    DiscourseFragment,
    LanguageGameAnalysis,
    ResonanceCluster,
    ResonanceSignal,
    ProspectProfile,
    IngestionResult,
)
from .discourse_ingestor import ingest_discourse
from .language_game import analyze_language_game
from .resonance import analyze_resonance, lookup_resonance, generate_prospect

__all__ = [
    "BaseMemoryManager",
    "Lead",
    "CampaignConfig",
    "normalize_score",
    "classify_faixa",
    "deduplicate_leads",
    "compute_instagram_inativo",
    "truncate_message",
    "is_valid_status",
    "can_send_message_sync",
    "build_mcp_error",
    "VALID_STATUSES",
    "BLOCKED_STATUSES",
    "DiscourseFragment",
    "LanguageGameAnalysis",
    "ResonanceCluster",
    "ResonanceSignal",
    "ProspectProfile",
    "IngestionResult",
    "ingest_discourse",
    "analyze_language_game",
    "analyze_resonance",
    "lookup_resonance",
    "generate_prospect"
]
