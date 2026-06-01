class Tracer:
    def __init__(self) -> None:
        self._calls: list[dict] = []

    async def record_llm_call(
        self, provider: str, model: str, tokens: int, latency_ms: int
    ) -> None:
        self._calls.append({
            "provider": provider,
            "model": model,
            "tokens": tokens,
            "latency_ms": latency_ms,
        })
