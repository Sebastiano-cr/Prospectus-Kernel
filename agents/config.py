"""
Shared configuration for the Prospectus-Kernel platform API.
Provides env vars, auth, rate limiter, and locale helpers.
"""
import os
import logging
from typing import Dict, Optional
from fastapi import HTTPException, Header, Request
from src.locale import get_locale, LocalePort

logger = logging.getLogger(__name__)

# ── Environment ──────────────────────────────────────────────────────────

LITELLM_URL = os.getenv("LITELLM_URL", "http://litellm:4000")
QWEN_VL_MAX_API_KEY = os.getenv("QWEN_VL_MAX_API_KEY", "")
DEEPSEEK_CHAT_API_KEY = os.getenv("DEEPSEEK_CHAT_API_KEY", "")
MOONSHOT_V1_128K_API_KEY = os.getenv("MOONSHOT_V1_128K_API_KEY", "")
EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL", "")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY", "")
EVOLUTION_INSTANCE_ID = os.getenv("EVOLUTION_INSTANCE_ID", "")
CRM_PROVIDER = os.getenv("CRM_PROVIDER", "")
CHROMA_PATH = os.getenv("CHROMA_PATH", "./data/chroma")
LOCALE_CODE = os.getenv("LOCALE", "pt-BR")
API_KEY = os.getenv("API_KEY", "")
REQUIRE_AUTH = os.getenv("PROSPECTUS_KERNEL_REQUIRE_AUTH", "true").lower() == "true"
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))


def get_locale_instance() -> LocalePort:
    return get_locale(LOCALE_CODE)


# ── Auth ─────────────────────────────────────────────────────────────────

async def verify_api_key(x_api_key: str = Header(default="")):
    if not REQUIRE_AUTH:
        return
    if not API_KEY:
        raise HTTPException(
            status_code=500,
            detail=get_locale_instance().get_fallback("api_key_not_configured"),
        )
    if x_api_key != API_KEY:
        raise HTTPException(
            status_code=401,
            detail=get_locale_instance().get_fallback("invalid_api_key"),
        )


# ── Rate Limiter ─────────────────────────────────────────────────────────

class RateLimiter:
    def __init__(self, requests_per_minute: int, max_clients: int = 10000):
        self.requests_per_minute = requests_per_minute
        self.max_clients = max_clients
        self.requests: Dict[str, list] = {}
        import time
        self.time = time

    def _cleanup_old_clients(self):
        if len(self.requests) > self.max_clients:
            sorted_clients = sorted(
                self.requests.keys(),
                key=lambda k: self.requests[k][0] if self.requests[k] else 0,
            )
            for key in sorted_clients[:len(sorted_clients) // 5]:
                del self.requests[key]

    async def check_rate_limit(self, client_ip: str = "unknown"):
        client_id = f"ip:{client_ip}"
        now = self.time.time()
        window_start = now - 60
        self._cleanup_old_clients()
        if client_id in self.requests:
            self.requests[client_id] = [t for t in self.requests[client_id] if t > window_start]
        else:
            self.requests[client_id] = []
        if len(self.requests[client_id]) >= self.requests_per_minute:
            raise HTTPException(
                status_code=429,
                detail=get_locale_instance()
                .get_fallback("rate_limit_exceeded")
                .format(limit=self.requests_per_minute),
            )
        self.requests[client_id].append(now)


_rate_limiter = RateLimiter(RATE_LIMIT_PER_MINUTE)


async def check_rate_limit(
    request: Request,
    x_forwarded_for: Optional[str] = Header(default=None),
):
    if x_forwarded_for:
        client_ip = x_forwarded_for.split(",")[0].strip()
    elif request.client:
        client_ip = request.client.host
    else:
        client_ip = "unknown"
    await _rate_limiter.check_rate_limit(client_ip)
