"""
Adapter LiteLLM -- Implementa ILLMClient para o LiteLLM proxy.

Substitui as 7+ chamadas httpx duplicadas nos agentes.
"""
import httpx
import os
from typing import List, Optional
from ..ports.llm_client import ILLMClient, LLMMessage, LLMResponse, LLMError


class LiteLLMAdapter(ILLMClient):
    """Adapter para LiteLLM proxy."""

    def __init__(self, base_url: str = None, api_key: str = None):
        self.base_url = base_url or os.getenv("LITELLM_URL", "http://localhost:4000")
        self.api_key = api_key or os.getenv("LITELLM_API_KEY", "")

    async def complete(
        self,
        messages: List[LLMMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        response_format: Optional[str] = None,
    ) -> LLMResponse:
        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        if response_format == "json":
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{self.base_url}/v1/chat/completions",
                    json=payload,
                    headers=headers
                )
                resp.raise_for_status()
                result = resp.json()
        except httpx.HTTPStatusError as e:
            raise LLMError(
                f"LiteLLM HTTP error: {e.response.status_code}",
                model=model,
                status_code=e.response.status_code
            )
        except httpx.RequestError as e:
            raise LLMError(f"LiteLLM connection error: {e}", model=model)

        return LLMResponse(
            content=result["choices"][0]["message"]["content"],
            model=result.get("model", model),
            usage=result.get("usage", {}),
            finish_reason=result["choices"][0].get("finish_reason", "stop")
        )

    async def embed(self, texts: List[str], model: str) -> List[List[float]]:
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{self.base_url}/v1/embeddings",
                    json={"model": model, "input": texts},
                    headers={"Authorization": f"Bearer {self.api_key}"}
                )
                resp.raise_for_status()
                return [item["embedding"] for item in resp.json()["data"]]
        except Exception as e:
            raise LLMError(f"Embedding error: {e}", model=model)

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/health")
                return resp.status_code == 200
        except Exception:
            return False
