"""
Lead enrichment and scoring endpoints.
"""
import logging
from fastapi import APIRouter, Depends
from src.locale import get_locale
from agents.config import (
    LITELLM_URL, QWEN_VL_MAX_API_KEY, DEEPSEEK_CHAT_API_KEY, LOCALE_CODE,
    verify_api_key, check_rate_limit,
)
from agents.enricher import enrich_lead
from agents.scorer import score_lead
from agents.schemas import EnrichRequest, ScoreRequest
from agents.metrics import (
    prospectus_kernel_leads_extracted_total,
    prospectus_kernel_enrichment_success_total,
    prospectus_kernel_enrichment_failed_total,
    prospectus_kernel_lead_score,
    prospectus_kernel_errors_total,
)
from fastapi import HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(tags=["leads"])


@router.post("/enrich")
async def enrich_endpoint(lead: EnrichRequest, _=Depends(verify_api_key), __=Depends(check_rate_limit)):
    try:
        prospectus_kernel_leads_extracted_total.labels(source="api").inc()
        lead_dict = lead.model_dump()
        locale = get_locale(LOCALE_CODE)
        enriched_lead = await enrich_lead(lead_dict, LITELLM_URL, QWEN_VL_MAX_API_KEY, locale)
        if enriched_lead.get("enrichment_success"):
            prospectus_kernel_enrichment_success_total.inc()
        else:
            prospectus_kernel_enrichment_failed_total.inc()
        return enriched_lead
    except Exception as e:
        logger.error(f"Error in enrich endpoint: {e}")
        prospectus_kernel_errors_total.labels(component="enricher").inc()
        raise HTTPException(status_code=500, detail=get_locale(LOCALE_CODE).get_fallback("enrichment_error"))


@router.post("/score")
async def score_endpoint(lead: ScoreRequest, _=Depends(verify_api_key), __=Depends(check_rate_limit)):
    try:
        locale = get_locale(LOCALE_CODE)
        scored_lead = await score_lead(lead.dossier, LITELLM_URL, DEEPSEEK_CHAT_API_KEY, locale)
        prospectus_kernel_lead_score.observe(scored_lead.get("score", 0))
        return scored_lead
    except Exception as e:
        logger.error(f"Error in score endpoint: {e}")
        prospectus_kernel_errors_total.labels(component="scorer").inc()
        raise HTTPException(status_code=500, detail=get_locale(LOCALE_CODE).get_fallback("scoring_error"))
