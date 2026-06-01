"""
Porta IMediaGenerator -- Interface invariante para geração de mídia com IA.

Invariantes:
  - I-MEDIA-1: generate() aceita MediaRequest e retorna MediaResponse
  - I-MEDIA-2: poll_result() é para operações assíncronas
  - I-MEDIA-3: O api_key é passado por chamada, NÃO armazenado na interface
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum


class MediaType(Enum):
    """Tipos de mídia suportados."""
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    LIP_SYNC = "lip_sync"
    IMAGE_TO_IMAGE = "image_to_image"
    IMAGE_TO_VIDEO = "image_to_video"
    VIDEO_TO_VIDEO = "video_to_video"
    AUDIO_TTS = "audio_tts"
    CLIPPING = "clipping"
    MOTION_GRAPHICS = "motion_graphics"


@dataclass(frozen=True)
class MediaRequest:
    """Requisição de geração de mídia."""
    prompt: str
    media_type: MediaType
    params: Dict[str, Any] = field(default_factory=dict)
    model_id: Optional[str] = None

    def __post_init__(self):
        if self.params is None:
            object.__setattr__(self, 'params', {})


@dataclass(frozen=True)
class MediaResponse:
    """Resposta de geração de mídia."""
    success: bool
    output_url: Optional[str] = None
    outputs: List[str] = field(default_factory=list)
    request_id: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class IMediaGenerator(ABC):
    """
    Porta invariante para geração de mídia com IA.

    Suporta Muapi.ai, MoneyPrinterTurbo, ou qualquer outro serviço.
    """

    @abstractmethod
    async def generate(self, request: MediaRequest, api_key: str) -> MediaResponse:
        """Gera mídia a partir de um prompt."""
        ...

    @abstractmethod
    async def poll_result(self, request_id: str, api_key: str) -> MediaResponse:
        """Consulta resultado de uma geração assíncrona."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Verifica se o serviço está operacional."""
        ...
