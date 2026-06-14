"""
Resonance analysis and prospect generation endpoints.
"""
import logging
from fastapi import APIRouter, Depends
from src.locale import get_locale
from agents.config import (
    LITELLM_URL, DEEPSEEK_CHAT_API_KEY, LOCALE_CODE,
    verify_api_key, check_rate_limit,
)
from agents.resonance import analyze_resonance, lookup_resonance, generate_prospect, record_signal
from agents.schemas import (
    ResonanceAnalyzeRequest, ResonanceLookupRequest,
    ResonanceProspectRequest, ResonanceRecordRequest,
)
from agents.metrics import kirin_errors_total
from fastapi import HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(tags=["resonance"])


@router.post("/resonance/analyze")
async def resonance_analyze_endpoint(request: ResonanceAnalyzeRequest, _=Depends(verify_api_key), __=Depends(check_rate_limit)):
    try:
        cluster = await analyze_resonance(
            request.analyses, request.market_cluster,
            LITELLM_URL, DEEPSEEK_CHAT_API_KEY,
        )
        return cluster
    except Exception as e:
        logger.error(f"Error in resonance analyze endpoint: {e}")
        kirin_errors_total.labels(component="resonance").inc()
        raise HTTPException(status_code=500, detail=get_locale(LOCALE_CODE).get_fallback("resonance_error"))


@router.post("/resonance/lookup")
async def resonance_lookup_endpoint(request: ResonanceLookupRequest, _=Depends(verify_api_key), __=Depends(check_rate_limit)):
    try:
        results = await lookup_resonance(
            request.query, LITELLM_URL, DEEPSEEK_CHAT_API_KEY, request.limit,
        )
        return {"results": results, "count": len(results)}
    except Exception as e:
        logger.error(f"Error in resonance lookup endpoint: {e}")
        kirin_errors_total.labels(component="resonance").inc()
        raise HTTPException(status_code=500, detail=get_locale(LOCALE_CODE).get_fallback("resonance_lookup_error"))


@router.post("/prospects/generate")
async def prospect_generate_endpoint(request: ResonanceProspectRequest, _=Depends(verify_api_key), __=Depends(check_rate_limit)):
    try:
        prospect = await generate_prospect(
            request.target_profile, None,
            LITELLM_URL, DEEPSEEK_CHAT_API_KEY,
        )
        return prospect
    except Exception as e:
        logger.error(f"Error in prospect generate endpoint: {e}")
        kirin_errors_total.labels(component="prospect_generator").inc()
        raise HTTPException(status_code=500, detail=get_locale(LOCALE_CODE).get_fallback("prospect_error"))


@router.post("/resonance/signal")
async def resonance_signal_endpoint(request: ResonanceRecordRequest, _=Depends(verify_api_key), __=Depends(check_rate_limit)):
    try:
        signal = await record_signal(
            request.lead_id, request.source, 1.0, {"text": request.text},
        )
        return signal
    except Exception as e:
        logger.error(f"Error in resonance signal endpoint: {e}")
        kirin_errors_total.labels(component="resonance").inc()
        raise HTTPException(status_code=500, detail=get_locale(LOCALE_CODE).get_fallback("signal_error"))
