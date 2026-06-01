class StaticFallbackProvider:
    def respond(self) -> "NormalizedResponse":
        from core.providers.provider_router import NormalizedResponse
        STATIC_RESPONSE = "Desculpe, o serviço está temporariamente indisponível."
        return NormalizedResponse(
            content=STATIC_RESPONSE,
            tokens_used=0,
            model="static",
            provider="static",
        )
