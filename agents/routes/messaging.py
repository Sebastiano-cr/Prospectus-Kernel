"""
Message generation endpoint.
"""
import logging
from fastapi import APIRouter, Depends
from src.locale import get_locale
from agents.config import (
    LITELLM_URL, DEEPSEEK_CHAT_API_KEY, LOCALE_CODE,
    verify_api_key, check_rate_limit,
)
from agents.messenger import generate_message
from agents.schemas import MessageRequest
from agents.metrics import prospectus_kernel_messages_sent_total, prospectus_kernel_errors_total
from fastapi import HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(tags=["messaging"])


@router.post("/generate_message")
async def generate_message_endpoint(lead: MessageRequest, _=Depends(verify_api_key), __=Depends(check_rate_limit)):
    try:
        lead_dict = lead.model_dump()
        locale = get_locale(LOCALE_CODE)
        message = await generate_message(lead_dict, LITELLM_URL, DEEPSEEK_CHAT_API_KEY, locale)
        if message is not None:
            prospectus_kernel_messages_sent_total.labels(status="generated").inc()
        else:
            prospectus_kernel_messages_sent_total.labels(status="discarded").inc()
        return {"message": message}
    except Exception as e:
        logger.error(f"Error in generate_message endpoint: {e}")
        prospectus_kernel_errors_total.labels(component="messenger").inc()
        raise HTTPException(status_code=500, detail=get_locale(LOCALE_CODE).get_fallback("message_error"))
