"""
Model Registry -- Catálogo de modelos MuAPI extraído do Open-Generative-AI.

Cada modelo tem: id, name, endpoint, category.
O lookup é feito por model_id.
"""
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class MuAPIModel:
    """Definição de um modelo MuAPI."""
    id: str
    name: str
    endpoint: str
    category: str  # t2i, i2i, t2v, i2v, v2v, lipsync, audio, clipping


# ─── Image Generation (T2I) ─────────────────────────────────────────────────

T2I_MODELS = [
    MuAPIModel("nano-banana", "Nano Banana", "nano-banana", "t2i"),
    MuAPIModel("nano-banana-pro", "Nano Banana Pro", "nano-banana-pro", "t2i"),
    MuAPIModel("nano-banana-2", "Nano Banana 2", "nano-banana-2", "t2i"),
    MuAPIModel("flux-dev", "Flux Dev", "flux-dev-image", "t2i"),
    MuAPIModel("flux-dev-lora", "Flux Dev LoRA", "flux-dev-lora", "t2i"),
    MuAPIModel("flux-schnell", "Flux Schnell", "flux-schnell", "t2i"),
    MuAPIModel("flux-pulid", "Flux PuLID", "flux-pulid", "t2i"),
    MuAPIModel("flux-redux", "Flux Redux", "flux-redux", "t2i"),
    MuAPIModel("flux-krea-dev", "Flux Krea Dev", "flux-krea-dev", "t2i"),
    MuAPIModel("flux-2-dev", "Flux 2 Dev", "flux-2-dev", "t2i"),
    MuAPIModel("flux-2-flex", "Flux 2 Flex", "flux-2-flex", "t2i"),
    MuAPIModel("flux-2-pro", "Flux 2 Pro", "flux-2-pro", "t2i"),
    MuAPIModel("flux-2-klein-4b", "Flux 2 Klein 4B", "flux-2-klein-4b", "t2i"),
    MuAPIModel("flux-2-klein-9b", "Flux 2 Klein 9B", "flux-2-klein-9b", "t2i"),
    MuAPIModel("flux-kontext-dev-t2i", "Flux Kontext Dev", "flux-kontext-dev-t2i", "t2i"),
    MuAPIModel("flux-kontext-pro-t2i", "Flux Kontext Pro", "flux-kontext-pro-t2i", "t2i"),
    MuAPIModel("flux-kontext-max-t2i", "Flux Kontext Max", "flux-kontext-max-t2i", "t2i"),
    MuAPIModel("hidream-i1-fast", "HiDream I1 Fast", "hidream-i1-fast", "t2i"),
    MuAPIModel("hidream-i1-dev", "HiDream I1 Dev", "hidream-i1-dev", "t2i"),
    MuAPIModel("hidream-i1-full", "HiDream I1 Full", "hidream-i1-full", "t2i"),
    MuAPIModel("ai-anime-generator", "AI Anime Generator", "ai-anime-generator", "t2i"),
    MuAPIModel("wan2.1-text-to-image", "Wan 2.1 T2I", "wan2.1-text-to-image", "t2i"),
    MuAPIModel("wan2.5-text-to-image", "Wan 2.5 T2I", "wan2.5-text-to-image", "t2i"),
    MuAPIModel("wan2.6-text-to-image", "Wan 2.6 T2I", "wan2.6-text-to-image", "t2i"),
    MuAPIModel("gpt4o-text-to-image", "GPT-4o T2I", "gpt4o-text-to-image", "t2i"),
    MuAPIModel("gpt-image-1.5", "GPT Image 1.5", "gpt-image-1.5", "t2i"),
    MuAPIModel("gpt-image-2", "GPT Image 2", "gpt-image-2", "t2i"),
    MuAPIModel("midjourney-v7-text-to-image", "Midjourney V7", "midjourney-v7-text-to-image", "t2i"),
    MuAPIModel("bytedance-seedream-v3", "Seedream V3", "bytedance-seedream-v3", "t2i"),
    MuAPIModel("bytedance-seedream-v4", "Seedream V4", "bytedance-seedream-v4", "t2i"),
    MuAPIModel("bytedance-seedream-v4.5", "Seedream V4.5", "bytedance-seedream-v4.5", "t2i"),
    MuAPIModel("seedream-5.0", "Seedream 5.0", "seedream-5.0", "t2i"),
    MuAPIModel("qwen-image", "Qwen Image", "qwen-image", "t2i"),
    MuAPIModel("qwen-text-to-image-2512", "Qwen T2I 2512", "qwen-text-to-image-2512", "t2i"),
    MuAPIModel("ideogram-v3-t2i", "Ideogram V3", "ideogram-v3-t2i", "t2i"),
    MuAPIModel("google-imagen4", "Google Imagen 4", "google-imagen4", "t2i"),
    MuAPIModel("google-imagen4-fast", "Google Imagen 4 Fast", "google-imagen4-fast", "t2i"),
    MuAPIModel("google-imagen4-ultra", "Google Imagen 4 Ultra", "google-imagen4-ultra", "t2i"),
    MuAPIModel("sdxl-image", "SDXL", "sdxl-image", "t2i"),
    MuAPIModel("hunyuan-image-2.1", "Hunyuan Image 2.1", "hunyuan-image-2.1", "t2i"),
    MuAPIModel("hunyuan-image-3.0", "Hunyuan Image 3.0", "hunyuan-image-3.0", "t2i"),
    MuAPIModel("chroma-image", "Chroma", "chroma-image", "t2i"),
    MuAPIModel("perfect-pony-xl", "Perfect Pony XL", "perfect-pony-xl", "t2i"),
    MuAPIModel("neta-lumina", "Neta Lumina", "neta-lumina", "t2i"),
    MuAPIModel("leonardoai-phoenix-1.0", "Leonardo Phoenix 1.0", "leonardoai-phoenix-1.0", "t2i"),
    MuAPIModel("leonardoai-lucid-origin", "Leonardo Lucid Origin", "leonardoai-lucid-origin", "t2i"),
    MuAPIModel("reve-text-to-image", "REVE", "reve-text-to-image", "t2i"),
    MuAPIModel("grok-imagine-text-to-image", "Grok Imagine", "grok-imagine-text-to-image", "t2i"),
    MuAPIModel("kling-o1-text-to-image", "Kling O1 T2I", "kling-o1-text-to-image", "t2i"),
    MuAPIModel("z-image-turbo", "Z-Image Turbo", "z-image-turbo", "t2i"),
    MuAPIModel("z-image-base", "Z-Image Base", "z-image-base", "t2i"),
    MuAPIModel("vidu-q2-text-to-image", "Vidu Q2 T2I", "vidu-q2-text-to-image", "t2i"),
    MuAPIModel("minimax-image-01", "MiniMax Image 01", "minimax-image-01", "t2i"),
]

# ─── Image-to-Image (I2I) ───────────────────────────────────────────────────

I2I_MODELS = [
    MuAPIModel("flux-kontext-dev-i2i", "Flux Kontext Dev I2I", "flux-kontext-dev-i2i", "i2i"),
    MuAPIModel("flux-kontext-pro-i2i", "Flux Kontext Pro I2I", "flux-kontext-pro-i2i", "i2i"),
    MuAPIModel("flux-kontext-max-i2i", "Flux Kontext Max I2I", "flux-kontext-max-i2i", "i2i"),
    MuAPIModel("nano-banana-i2i", "Nano Banana I2I", "nano-banana-i2i", "i2i"),
    MuAPIModel("flux-krea-dev-i2i", "Flux Krea Dev I2I", "flux-krea-dev-i2i", "i2i"),
    MuAPIModel("gpt-image-1.5-i2i", "GPT Image 1.5 I2I", "gpt-image-1.5-i2i", "i2i"),
    MuAPIModel("gpt-image-2-i2i", "GPT Image 2 I2I", "gpt-image-2-i2i", "i2i"),
]

# ─── Text-to-Video (T2V) ───────────────────────────────────────────────────

T2V_MODELS = [
    MuAPIModel("seedance-lite-t2v", "Seedance Lite T2V", "seedance-lite-t2v", "t2v"),
    MuAPIModel("seedance-pro-t2v", "Seedance Pro T2V", "seedance-pro-t2v", "t2v"),
    MuAPIModel("seedance-pro-t2v-fast", "Seedance Pro T2V Fast", "seedance-pro-t2v-fast", "t2v"),
    MuAPIModel("seedance-v1.5-pro-t2v", "Seedance V1.5 Pro T2V", "seedance-v1.5-pro-t2v", "t2v"),
    MuAPIModel("seedance-v1.5-pro-t2v-fast", "Seedance V1.5 Pro T2V Fast", "seedance-v1.5-pro-t2v-fast", "t2v"),
    MuAPIModel("seedance-v2.0-t2v", "Seedance V2.0 T2V", "seedance-v2.0-t2v", "t2v"),
    MuAPIModel("seedance-v2.0-extend", "Seedance V2.0 Extend", "seedance-v2.0-extend", "t2v"),
    MuAPIModel("kling-v2.1-master-t2v", "Kling V2.1 Master T2V", "kling-v2.1-master-t2v", "t2v"),
    MuAPIModel("kling-v2.5-turbo-pro-t2v", "Kling V2.5 Turbo Pro T2V", "kling-v2.5-turbo-pro-t2v", "t2v"),
    MuAPIModel("kling-v2.6-pro-t2v", "Kling V2.6 Pro T2V", "kling-v2.6-pro-t2v", "t2v"),
    MuAPIModel("kling-o1-text-to-video", "Kling O1 T2V", "kling-o1-text-to-video", "t2v"),
    MuAPIModel("kling-v3.0-pro-text-to-video", "Kling V3.0 Pro T2V", "kling-v3.0-pro-text-to-video", "t2v"),
    MuAPIModel("kling-v3.0-standard-text-to-video", "Kling V3.0 Standard T2V", "kling-v3.0-standard-text-to-video", "t2v"),
    MuAPIModel("veo3-text-to-video", "Veo3 T2V", "veo3-text-to-video", "t2v"),
    MuAPIModel("veo3-fast-text-to-video", "Veo3 Fast T2V", "veo3-fast-text-to-video", "t2v"),
    MuAPIModel("veo3.1-text-to-video", "Veo3.1 T2V", "veo3.1-text-to-video", "t2v"),
    MuAPIModel("veo3.1-fast-text-to-video", "Veo3.1 Fast T2V", "veo3.1-fast-text-to-video", "t2v"),
    MuAPIModel("veo3.1-lite-text-to-video", "Veo3.1 Lite T2V", "veo3.1-lite-text-to-video", "t2v"),
    MuAPIModel("runway-text-to-video", "Runway T2V", "runway-text-to-video", "t2v"),
    MuAPIModel("wan2.1-text-to-video", "Wan 2.1 T2V", "wan2.1-text-to-video", "t2v"),
    MuAPIModel("wan2.2-text-to-video", "Wan 2.2 T2V", "wan2.2-text-to-video", "t2v"),
    MuAPIModel("wan2.2-5b-fast-t2v", "Wan 2.2 5B Fast T2V", "wan2.2-5b-fast-t2v", "t2v"),
    MuAPIModel("wan2.5-text-to-video", "Wan 2.5 T2V", "wan2.5-text-to-video", "t2v"),
    MuAPIModel("wan2.5-text-to-video-fast", "Wan 2.5 T2V Fast", "wan2.5-text-to-video-fast", "t2v"),
    MuAPIModel("wan2.6-text-to-video", "Wan 2.6 T2V", "wan2.6-text-to-video", "t2v"),
    MuAPIModel("hunyuan-text-to-video", "Hunyuan T2V", "hunyuan-text-to-video", "t2v"),
    MuAPIModel("hunyuan-fast-text-to-video", "Hunyuan Fast T2V", "hunyuan-fast-text-to-video", "t2v"),
]

# ─── Image-to-Video (I2V) ───────────────────────────────────────────────────

I2V_MODELS = [
    MuAPIModel("wan2.1-image-to-video", "Wan 2.1 I2V", "wan2.1-image-to-video", "i2v"),
    MuAPIModel("wan2.2-image-to-video", "Wan 2.2 I2V", "wan2.2-image-to-video", "i2v"),
    MuAPIModel("wan2.5-image-to-video", "Wan 2.5 I2V", "wan2.5-image-to-video", "i2v"),
    MuAPIModel("wan2.5-image-to-video-fast", "Wan 2.5 I2V Fast", "wan2.5-image-to-video-fast", "i2v"),
    MuAPIModel("wan2.6-image-to-video", "Wan 2.6 I2V", "wan2.6-image-to-video", "i2v"),
    MuAPIModel("wan2.2-spicy-image-to-video", "Wan 2.2 Spicy I2V", "wan2.2-spicy-image-to-video", "i2v"),
    MuAPIModel("midjourney-v7-image-to-video", "Midjourney V7 I2V", "midjourney-v7-image-to-video", "i2v"),
    MuAPIModel("hunyuan-image-to-video", "Hunyuan I2V", "hunyuan-image-to-video", "i2v"),
    MuAPIModel("kling-v2.1-master-i2v", "Kling V2.1 Master I2V", "kling-v2.1-master-i2v", "i2v"),
    MuAPIModel("kling-v2.1-standard-i2v", "Kling V2.1 Standard I2V", "kling-v2.1-standard-i2v", "i2v"),
    MuAPIModel("kling-v2.1-pro-i2v", "Kling V2.1 Pro I2V", "kling-v2.1-pro-i2v", "i2v"),
    MuAPIModel("kling-v2.5-turbo-pro-i2v", "Kling V2.5 Turbo Pro I2V", "kling-v2.5-turbo-pro-i2v", "i2v"),
    MuAPIModel("kling-v2.5-turbo-std-i2v", "Kling V2.5 Turbo Std I2V", "kling-v2.5-turbo-std-i2v", "i2v"),
    MuAPIModel("kling-v2.6-pro-i2v", "Kling V2.6 Pro I2V", "kling-v2.6-pro-i2v", "i2v"),
    MuAPIModel("kling-o1-image-to-video", "Kling O1 I2V", "kling-o1-image-to-video", "i2v"),
    MuAPIModel("kling-o1-standard-image-to-video", "Kling O1 Standard I2V", "kling-o1-standard-image-to-video", "i2v"),
    MuAPIModel("kling-v3.0-pro-image-to-video", "Kling V3.0 Pro I2V", "kling-v3.0-pro-image-to-video", "i2v"),
    MuAPIModel("kling-v3.0-standard-image-to-video", "Kling V3.0 Standard I2V", "kling-v3.0-standard-image-to-video", "i2v"),
    MuAPIModel("runway-act-two-i2v", "Runway Act Two I2V", "runway-act-two-i2v", "i2v"),
    MuAPIModel("pixverse-v4.5-i2v", "PixVerse V4.5 I2V", "pixverse-v4.5-i2v", "i2v"),
    MuAPIModel("pixverse-v5-i2v", "PixVerse V5 I2V", "pixverse-v5-i2v", "i2v"),
    MuAPIModel("pixverse-v5.5-i2v", "PixVerse V5.5 I2V", "pixverse-v5.5-i2v", "i2v"),
    MuAPIModel("vidu-v2.0-i2v", "Vidu V2.0 I2V", "vidu-v2.0-i2v", "i2v"),
    MuAPIModel("vidu-q1-reference", "Vidu Q1 Reference", "vidu-q1-reference", "i2v"),
    MuAPIModel("vidu-q2-reference", "Vidu Q2 Reference", "vidu-q2-reference", "i2v"),
    MuAPIModel("minimax-hailuo-02-standard-i2v", "Hailuo 02 Standard I2V", "minimax-hailuo-02-standard-i2v", "i2v"),
    MuAPIModel("minimax-hailuo-02-pro-i2v", "Hailuo 02 Pro I2V", "minimax-hailuo-02-pro-i2v", "i2v"),
    MuAPIModel("minimax-hailuo-2.3-pro-i2v", "Hailuo 2.3 Pro I2V", "minimax-hailuo-2.3-pro-i2v", "i2v"),
    MuAPIModel("minimax-hailuo-2.3-standard-i2v", "Hailuo 2.3 Standard I2V", "minimax-hailuo-2.3-standard-i2v", "i2v"),
    MuAPIModel("minimax-hailuo-2.3-fast", "Hailuo 2.3 Fast", "minimax-hailuo-2.3-fast", "i2v"),
    MuAPIModel("seedance-lite-i2v", "Seedance Lite I2V", "seedance-lite-i2v", "i2v"),
    MuAPIModel("seedance-pro-i2v", "Seedance Pro I2V", "seedance-pro-i2v", "i2v"),
    MuAPIModel("seedance-pro-i2v-fast", "Seedance Pro I2V Fast", "seedance-pro-i2v-fast", "i2v"),
    MuAPIModel("seedance-v1.5-pro-i2v", "Seedance V1.5 Pro I2V", "seedance-v1.5-pro-i2v", "i2v"),
    MuAPIModel("seedance-v1.5-pro-i2v-fast", "Seedance V1.5 Pro I2V Fast", "seedance-v1.5-pro-i2v-fast", "i2v"),
    MuAPIModel("seedance-v2.0-i2v", "Seedance V2.0 I2V", "seedance-v2.0-i2v", "i2v"),
    MuAPIModel("openai-sora-2-image-to-video", "Sora 2 I2V", "openai-sora-2-image-to-video", "i2v"),
    MuAPIModel("openai-sora-2-pro-image-to-video", "Sora 2 Pro I2V", "openai-sora-2-pro-image-to-video", "i2v"),
    MuAPIModel("ovi-image-to-video", "OVI I2V", "ovi-image-to-video", "i2v"),
    MuAPIModel("leonardoai-motion-2.0", "Leonardo Motion 2.0", "leonardoai-motion-2.0", "i2v"),
    MuAPIModel("veo3.1-image-to-video", "Veo3.1 I2V", "veo3.1-image-to-video", "i2v"),
    MuAPIModel("veo3.1-fast-image-to-video", "Veo3.1 Fast I2V", "veo3.1-fast-image-to-video", "i2v"),
    MuAPIModel("veo3.1-lite-image-to-video", "Veo3.1 Lite I2V", "veo3.1-lite-image-to-video", "i2v"),
    MuAPIModel("veo3.1-reference-to-video", "Veo3.1 Reference", "veo3.1-reference-to-video", "i2v"),
    MuAPIModel("ltx-2-pro-image-to-video", "LTX 2 Pro I2V", "ltx-2-pro-image-to-video", "i2v"),
    MuAPIModel("ltx-2-fast-image-to-video", "LTX 2 Fast I2V", "ltx-2-fast-image-to-video", "i2v"),
    MuAPIModel("ltx-2-19b-image-to-video", "LTX 2 19B I2V", "ltx-2-19b-image-to-video", "i2v"),
    MuAPIModel("grok-imagine-image-to-video", "Grok Imagine I2V", "grok-imagine-image-to-video", "i2v"),
]

# ─── Video-to-Video (V2V) ───────────────────────────────────────────────────

V2V_MODELS = [
    MuAPIModel("video-watermark-remover", "Watermark Remover", "video-watermark-remover", "v2v"),
    MuAPIModel("video-effects", "Video Effects", "video-effects", "v2v"),
    MuAPIModel("kling-v2.6-std-motion-control", "Kling V2.6 Motion Control", "kling-v2.6-std-motion-control", "v2v"),
    MuAPIModel("kling-v3.0-std-motion-control", "Kling V3.0 Std Motion Control", "kling-v3.0-std-motion-control", "v2v"),
    MuAPIModel("kling-v3.0-pro-motion-control", "Kling V3.0 Pro Motion Control", "kling-v3.0-pro-motion-control", "v2v"),
]

# ─── Lip Sync ────────────────────────────────────────────────────────────────

LIPSYNC_MODELS = [
    MuAPIModel("infinitetalk-image-to-video", "InfiniteTalk I2V", "infinitetalk-image-to-video", "lipsync"),
    MuAPIModel("infinitetalk-video-to-video", "InfiniteTalk V2V", "infinitetalk-video-to-video", "lipsync"),
    MuAPIModel("wan2.2-speech-to-video", "Wan 2.2 Speech to Video", "wan2.2-speech-to-video", "lipsync"),
    MuAPIModel("ltx-2.3-lipsync", "LTX 2.3 LipSync", "ltx-2.3-lipsync", "lipsync"),
    MuAPIModel("ltx-2-19b-lipsync", "LTX 2 19B LipSync", "ltx-2-19b-lipsync", "lipsync"),
    MuAPIModel("sync-lipsync", "Sync LipSync", "sync-lipsync", "lipsync"),
    MuAPIModel("latent-sync", "Latent Sync", "latent-sync", "lipsync"),
    MuAPIModel("creatify-lipsync", "Creatify LipSync", "creatify-lipsync", "lipsync"),
    MuAPIModel("veed-lipsync", "VEED LipSync", "veed-lipsync", "lipsync"),
]

# ─── Audio ───────────────────────────────────────────────────────────────────

AUDIO_MODELS = [
    MuAPIModel("suno-create-music", "Suno Create Music", "suno-create-music", "audio"),
    MuAPIModel("suno-remix-music", "Suno Remix Music", "suno-remix-music", "audio"),
    MuAPIModel("suno-extend-music", "Suno Extend Music", "suno-extend-music", "audio"),
    MuAPIModel("suno-generate-sounds", "Suno Generate Sounds", "suno-generate-sounds", "audio"),
    MuAPIModel("suno-add-vocals", "Suno Add Vocals", "suno-add-vocals", "audio"),
    MuAPIModel("suno-generate-mashup", "Suno Generate Mashup", "suno-generate-mashup", "audio"),
    MuAPIModel("suno-add-instrumental", "Suno Add Instrumental", "suno-add-instrumental", "audio"),
    MuAPIModel("suno-voice-clone", "Suno Voice Clone", "suno-voice-clone", "audio"),
    MuAPIModel("minimax-voice-clone", "MiniMax Voice Clone", "minimax-voice-clone", "audio"),
    MuAPIModel("minimax-speech-2.6-hd", "MiniMax Speech 2.6 HD", "minimax-speech-2.6-hd", "audio"),
    MuAPIModel("minimax-speech-2.6-turbo", "MiniMax Speech 2.6 Turbo", "minimax-speech-2.6-turbo", "audio"),
    MuAPIModel("mmaudio-v2-text-to-audio", "MMAudio V2 T2A", "mmaudio-v2-text-to-audio", "audio"),
]

# ─── Reference / Special ─────────────────────────────────────────────────────

REFERENCE_MODELS = [
    MuAPIModel("seedance-lite-reference-video", "Seedance Lite Reference", "seedance-lite-reference-video", "reference"),
    MuAPIModel("wan2.1-reference-video", "Wan 2.1 Reference", "wan2.1-reference-video", "reference"),
    MuAPIModel("vidu-q2-turbo-start-end-video", "Vidu Q2 Turbo Start/End", "vidu-q2-turbo-start-end-video", "reference"),
    MuAPIModel("vidu-q2-pro-start-end-video", "Vidu Q2 Pro Start/End", "vidu-q2-pro-start-end-video", "reference"),
]

# ─── Registry ────────────────────────────────────────────────────────────────

ALL_MODELS: list[MuAPIModel] = (
    T2I_MODELS + I2I_MODELS + T2V_MODELS + I2V_MODELS +
    V2V_MODELS + LIPSYNC_MODELS + AUDIO_MODELS + REFERENCE_MODELS
)

_MODEL_BY_ID: Dict[str, MuAPIModel] = {m.id: m for m in ALL_MODELS}

# ─── Public API ──────────────────────────────────────────────────────────────


def get_model_by_id(model_id: str) -> Optional[MuAPIModel]:
    """Lookup model by ID. Returns None if not found."""
    return _MODEL_BY_ID.get(model_id)


def get_models_by_category(category: str) -> list[MuAPIModel]:
    """Return all models in a category."""
    return [m for m in ALL_MODELS if m.category == category]


def list_all_model_ids() -> list[str]:
    """Return all model IDs."""
    return [m.id for m in ALL_MODELS]


# Category aliases for backward compatibility
CATEGORY_MAP = {
    "image": "t2i",
    "video": "t2v",
    "audio": "audio",
    "lip_sync": "lipsync",
    "image_to_image": "i2i",
    "image_to_video": "i2v",
    "video_to_video": "v2v",
    "audio_tts": "audio",
    "clipping": "audio",
    "motion_graphics": "v2v",
}
