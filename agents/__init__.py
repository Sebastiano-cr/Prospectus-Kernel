"""
Prospectus-Kernel Agents Package
"""
from .models import Lead, CampaignConfig
from .pure_functions import (
    normalize_score,
    classify_faixa,
    deduplicate_leads,
    compute_instagram_inativo,
    truncate_message,
    is_valid_status,
    can_send_message_sync,
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

__all__ = [
    "Lead",
    "CampaignConfig",
    "normalize_score",
    "classify_faixa",
    "deduplicate_leads",
    "compute_instagram_inativo",
    "truncate_message",
    "is_valid_status",
    "can_send_message_sync",
    "VALID_STATUSES",
    "BLOCKED_STATUSES",
    "DiscourseFragment",
    "LanguageGameAnalysis",
    "ResonanceCluster",
    "ResonanceSignal",
    "ProspectProfile",
    "IngestionResult",
]
