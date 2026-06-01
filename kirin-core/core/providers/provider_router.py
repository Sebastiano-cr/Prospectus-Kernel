import os
import time
from typing import Any
import httpx
from pydantic import BaseModel
from core.providers.static_fallback import StaticFallbackProvider

LITELLM_URL = os.environ.get("LITELLM_URL", "http://litellm:4000/v1/chat/completions")
FALLBACK_PROVIDER = os.environ.get("FALLBACK_PROVIDER", "ollama/llama3.2")


class NormalizedResponse(BaseModel):
    content: str
    tokens_used: int
    model: str
    provider: str


class ProviderRouter:
    def __init__(self, tracer: Any = None) -> None:
        self.tracer = tracer
        self._static_fallback = StaticFallbackProvider()

    async def call(self, model: str, messages: list[dict], **kwargs) -> NormalizedResponse:
        start = time.monotonic()
        try:
            response = await self._call_litellm(model, messages, **kwargs)
            latency_ms = int((time.monotonic() - start) * 1000)
            if self.tracer:
                await self.tracer.record_llm_call(
                    provider=response.provider,
                    model=response.model,
                    tokens=response.tokens_used,
                    latency_ms=latency_ms,
                )
            return response
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code >= 500:
                return await self._failover(exc, messages, **kwargs)
            raise

    async def _call_litellm(self, model: str, messages: list[dict], **kwargs) -> NormalizedResponse:
        payload = {"model": model, "messages": messages, **kwargs}
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(LITELLM_URL, json=payload)
            resp.raise_for_status()
        data = resp.json()
        choice = data["choices"][0]["message"]
        usage = data.get("usage", {})
        return NormalizedResponse(
            content=choice["content"],
            tokens_used=usage.get("total_tokens", 0),
            model=data.get("model", model),
            provider=data.get("provider", "litellm"),
        )

    async def _failover(self, error: Exception, messages: list[dict], **kwargs) -> NormalizedResponse:
        try:
            return await self._call_litellm(FALLBACK_PROVIDER, messages, **kwargs)
        except Exception:
            return self._static_fallback.respond()
