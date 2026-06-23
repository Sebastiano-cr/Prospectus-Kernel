"""
Research and CRM sync endpoints.
"""
import logging
from fastapi import APIRouter, Depends
from src.locale import get_locale
from agents.config import (
    LITELLM_URL, MOONSHOT_V1_128K_API_KEY, CRM_PROVIDER, LOCALE_CODE,
    verify_api_key, check_rate_limit,
)
from agents.researcher import research_lead
from agents.crm_connector import get_crm_adapter
from agents.schemas import ResearchRequest, CRMSyncRequest
from agents.metrics import prospectus_kernel_errors_total
from fastapi import HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(tags=["research"])

# Initialize CRM adapter if provider is set
_crm_adapter = None
if CRM_PROVIDER:
    try:
        _crm_adapter = get_crm_adapter(CRM_PROVIDER, {})
    except Exception as e:
        logger.error(f"Failed to initialize CRM adapter for provider {CRM_PROVIDER}: {e}")


@router.post("/research")
async def research_endpoint(lead: ResearchRequest, _=Depends(verify_api_key), __=Depends(check_rate_limit)):
    try:
        lead_dict = lead.model_dump()
        locale = get_locale(LOCALE_CODE)
        researched_lead = await research_lead(lead_dict, LITELLM_URL, MOONSHOT_V1_128K_API_KEY, locale)
        return researched_lead
    except Exception as e:
        logger.error(f"Error in research endpoint: {e}")
        prospectus_kernel_errors_total.labels(component="researcher").inc()
        raise HTTPException(status_code=500, detail=get_locale(LOCALE_CODE).get_fallback("research_error"))


@router.post("/crm_sync")
async def crm_sync_endpoint(lead: CRMSyncRequest, _=Depends(verify_api_key), __=Depends(check_rate_limit)):
    try:
        if not _crm_adapter:
            raise HTTPException(status_code=500, detail="CRM adapter not initialized")
        lead_dict = lead.model_dump()
        result = await _crm_adapter.upsert_lead(lead_dict)
        return result
    except Exception as e:
        logger.error(f"Error in crm_sync endpoint: {e}")
        prospectus_kernel_errors_total.labels(component="crm_connector").inc()
        raise HTTPException(status_code=500, detail=get_locale(LOCALE_CODE).get_fallback("crm_error"))
