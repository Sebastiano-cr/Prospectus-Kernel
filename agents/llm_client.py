import os
from dataclasses import dataclass, field
from typing import List, Optional

import httpx


@dataclass(frozen=True)
class LLMMessage:
    role: str
    content: str


@dataclass(frozen=True)
class LLMResponse:
    content: str
    model: str
    usage: dict = field(default_factory=dict)
    finish_reason: str = "stop"


class LLMError(Exception):
    def __init__(self, message: str, model: str = None, status_code: int = None):
        super().__init__(message)
        self.model = model
        self.status_code = status_code


_litellm_url = os.environ.get("LITELLM_URL", "http://localhost:4000")
_api_key = os.environ.get("LITELLM_API_KEY", "")


async def llm_complete(
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
        "Authorization": f"Bearer {_api_key}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{_litellm_url}/v1/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            result = resp.json()
    except httpx.HTTPStatusError as e:
        raise LLMError(
            f"LiteLLM HTTP error: {e.response.status_code}",
            model=model,
            status_code=e.response.status_code,
        )
    except httpx.RequestError as e:
        raise LLMError(f"LiteLLM connection error: {e}", model=model)

    return LLMResponse(
        content=result["choices"][0]["message"]["content"],
        model=result.get("model", model),
        usage=result.get("usage", {}),
        finish_reason=result["choices"][0].get("finish_reason", "stop"),
    )


async def llm_embed(texts: List[str], model: str) -> List[List[float]]:
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{_litellm_url}/v1/embeddings",
                json={"model": model, "input": texts},
                headers={"Authorization": f"Bearer {_api_key}"},
            )
            resp.raise_for_status()
            return [item["embedding"] for item in resp.json()["data"]]
    except Exception as e:
        raise LLMError(f"Embedding error: {e}", model=model)


async def llm_health_check() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{_litellm_url}/health")
            return resp.status_code == 200
    except Exception:
        return False
