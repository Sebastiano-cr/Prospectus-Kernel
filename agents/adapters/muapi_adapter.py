"""
Adapter Muapi -- Implementa IMediaGenerator para Muapi.ai (Open-Generative-AI).

Suporta 200+ modelos de geração de mídia via model registry.
"""
import httpx
import asyncio
import logging
from typing import Dict, Any, Optional
from ..ports.media_generator import IMediaGenerator, MediaRequest, MediaResponse, MediaType
from ..muapi_models_pkg.muapi_models import get_model_by_id, CATEGORY_MAP

logger = logging.getLogger(__name__)

# Endpoints padrão por MediaType (fallback quando model_id não fornecido)
DEFAULT_ENDPOINTS = {
    MediaType.IMAGE: "flux-dev-image",
    MediaType.IMAGE_TO_IMAGE: "flux-kontext-dev-i2i",
    MediaType.VIDEO: "seedance-pro-t2v",
    MediaType.IMAGE_TO_VIDEO: "wan2.1-image-to-video",
    MediaType.VIDEO_TO_VIDEO: "video-watermark-remover",
    MediaType.LIP_SYNC: "infinitetalk-image-to-video",
    MediaType.AUDIO: "suno-create-music",
    MediaType.AUDIO_TTS: "minimax-speech-2.6-hd",
    MediaType.CLIPPING: "suno-create-music",
    MediaType.MOTION_GRAPHICS: "video-effects",
}


class MuapiAdapter(IMediaGenerator):
    """Adapter para Muapi.ai com suporte a 200+ modelos."""

    def __init__(self, base_url: str = "https://api.muapi.ai"):
        self.base_url = base_url
        self.poll_interval = 2
        self.max_polls = 900  # 30 minutes

    async def generate(self, request: MediaRequest, api_key: str) -> MediaResponse:
        endpoint = self._resolve_endpoint(request)
        payload = self._build_payload(request)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self.base_url}/api/v1/{endpoint}",
                    json=payload,
                    headers={"x-api-key": api_key},
                )

            if resp.status_code != 200:
                return MediaResponse(
                    success=False,
                    error=f"HTTP {resp.status_code}: {resp.text[:200]}",
                )

            data = resp.json()
            request_id = data.get("request_id") or data.get("id")

            if not request_id:
                # Response might contain direct output
                output_url = (
                    data.get("url")
                    or data.get("output", {}).get("url")
                    or (data.get("outputs", [{}])[0].get("url") if data.get("outputs") else None)
                )
                if output_url:
                    return MediaResponse(success=True, output_url=output_url, metadata=data)
                return MediaResponse(success=False, error="No request_id in response")

            return await self.poll_result(request_id, api_key)

        except httpx.TimeoutException:
            return MediaResponse(success=False, error="MuAPI request timeout")
        except httpx.ConnectError:
            return MediaResponse(success=False, error="MuAPI unreachable")
        except Exception as e:
            logger.warning(f"MuAPI generate failed: {e}")
            return MediaResponse(success=False, error=str(e))

    async def poll_result(self, request_id: str, api_key: str) -> MediaResponse:
        for _ in range(self.max_polls):
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(
                        f"{self.base_url}/api/v1/predictions/{request_id}/result",
                        headers={"x-api-key": api_key},
                    )

                if resp.status_code == 200:
                    data = resp.json()
                    status = data.get("status", "").lower()

                    if status in ("completed", "succeeded", "success"):
                        output = data.get("output", {})
                        output_url = None

                        # Extract output URL from various response formats
                        if isinstance(output, dict):
                            output_url = output.get("url")
                            if not output_url and output.get("outputs"):
                                first_output = output["outputs"][0]
                                if isinstance(first_output, dict):
                                    output_url = first_output.get("url")
                                elif isinstance(first_output, str):
                                    output_url = first_output
                        elif isinstance(output, str):
                            output_url = output

                        # Fallback to top-level fields
                        if not output_url:
                            output_url = data.get("url")
                        if not output_url and data.get("outputs"):
                            first = data["outputs"][0]
                            if isinstance(first, dict):
                                output_url = first.get("url")
                            elif isinstance(first, str):
                                output_url = first

                        # Collect all output URLs
                        outputs = []
                        if isinstance(output, dict) and output.get("outputs"):
                            outputs = [
                                o.get("url") if isinstance(o, dict) else o
                                for o in output["outputs"]
                                if (o.get("url") if isinstance(o, dict) else o)
                            ]
                        elif output_url:
                            outputs = [output_url]

                        return MediaResponse(
                            success=True,
                            output_url=output_url,
                            outputs=outputs,
                            request_id=request_id,
                            metadata=data,
                        )
                    elif status in ("failed", "error"):
                        return MediaResponse(
                            success=False,
                            request_id=request_id,
                            error=data.get("error", "Generation failed"),
                        )

            except Exception:
                pass

            await asyncio.sleep(self.poll_interval)

        return MediaResponse(success=False, request_id=request_id, error="Polling timeout")

    def _resolve_endpoint(self, request: MediaRequest) -> str:
        """Resolve endpoint from model_id or MediaType default."""
        # Try model_id first
        if request.model_id:
            model = get_model_by_id(request.model_id)
            if model:
                return model.endpoint
            # If not in registry, use as raw endpoint
            return request.model_id

        # Fallback to MediaType default
        return DEFAULT_ENDPOINTS.get(request.media_type, "flux-dev-image")

    def _build_payload(self, request: MediaRequest) -> Dict[str, Any]:
        """Build API payload from request."""
        payload: Dict[str, Any] = {}

        if request.prompt:
            payload["prompt"] = request.prompt

        # Merge params
        if request.params:
            for key, value in request.params.items():
                if key not in ("tool_name",):
                    payload[key] = value

        return payload

    def _get_endpoint(self, media_type: MediaType) -> str:
        """Legacy method for backward compatibility."""
        return DEFAULT_ENDPOINTS.get(media_type, "flux-dev-image")

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/health")
                return resp.status_code == 200
        except Exception:
            return False
