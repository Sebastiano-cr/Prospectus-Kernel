"""
Discourse ingestion and extraction endpoints.
"""
import logging
from fastapi import APIRouter, Depends
from src.locale import get_locale
from agents.config import (
    LITELLM_URL, DEEPSEEK_CHAT_API_KEY, LOCALE_CODE,
    verify_api_key, check_rate_limit,
)
from agents.discourse_ingestor import ingest_discourse
from agents.language_game import analyze_language_game
from agents.schemas import DiscourseRequest
from agents.metrics import kirin_errors_total
from fastapi import HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/discourse", tags=["discourse"])


@router.post("/ingest")
async def discourse_ingest_endpoint(request: DiscourseRequest, _=Depends(verify_api_key), __=Depends(check_rate_limit)):
    try:
        locale = get_locale(LOCALE_CODE)
        fragment = await ingest_discourse(
            request.text, request.source, request.context,
            LITELLM_URL, DEEPSEEK_CHAT_API_KEY,
            locale=locale,
        )
        return fragment
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in discourse ingest endpoint: {e}")
        kirin_errors_total.labels(component="discourse_ingestor").inc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract")
async def discourse_extract_endpoint(request: DiscourseRequest, _=Depends(verify_api_key), __=Depends(check_rate_limit)):
    try:
        locale = get_locale(LOCALE_CODE)
        fragment = await ingest_discourse(
            request.text, request.source, request.context,
            LITELLM_URL, DEEPSEEK_CHAT_API_KEY,
            locale=locale,
        )
        analysis = await analyze_language_game(fragment, LITELLM_URL, DEEPSEEK_CHAT_API_KEY, locale=locale)
        return {"fragment": fragment, "analysis": analysis}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in discourse extract endpoint: {e}")
        kirin_errors_total.labels(component="discourse_pipeline").inc()
        raise HTTPException(status_code=500, detail=get_locale(LOCALE_CODE).get_fallback("discourse_error"))
