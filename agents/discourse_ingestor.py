"""
Discourse Ingestor — Layer 1 of the Wittgensteinian Language Games Engine.
Normalizes raw discourse fragments from any source into structured DiscourseFragments.
"""
import asyncio
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import hashlib
from . import runtime
from .discourse_templates import build_ingestion_prompt
from .factory import ServiceFactory
from .ports.llm_client import LLMMessage, LLMError
from .metrics import kirin_discourse_ingested_total

logger = logging.getLogger(__name__)

# Configuration
INGESTION_TIMEOUT = 60.0
MAX_RETRIES = 2
RETRY_DELAY = 5.0

# Valid discourse sources
VALID_SOURCES = ["reddit", "youtube", "linkedin", "telegram", "sales_call", "dm", "landing_page", "community", "other"]


async def ingest_discourse(
    text: str,
    source: str,
    context: str = "",
    litellm_url: str = None,
    api_key: str = None,
) -> Dict[str, Any]:
    """
    Main entry point for discourse ingestion.

    Normalizes raw discourse text from any source platform into a structured
    DiscourseFragment via LLM-assisted analysis.

    Args:
        text: The raw discourse text exactly as it appeared in the source.
        source: The platform or channel this fragment originated from.
        context: Optional surrounding context (parent comment, thread, etc.).
        litellm_url: Deprecated -- kept for backward compatibility.
        api_key: Deprecated -- kept for backward compatibility.

    Returns:
        A dict containing all DiscourseFragment fields.
    """
    # Input validation
    if not text or not text.strip():
        raise ValueError("Discourse text must not be empty")

    source = _validate_source(source)

    # Dedup check
    if await _check_duplicate(text, source):
        logger.info(f"Duplicate discourse fragment detected (source={source}), returning cached")
        fragment_id = _generate_fragment_id(text, source)
        cached = await _retrieve_cached_fragment(fragment_id)
        if cached is not None:
            return cached

    # Build prompt
    llm = ServiceFactory.get_llm_client()
    prompt = build_ingestion_prompt(text, source, context)
    messages = [LLMMessage(role="user", content=prompt)]

    timestamp = datetime.now(timezone.utc).isoformat()

    # Call LLM via ILLMClient port with retries
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = await llm.complete(
                messages=messages,
                model="deepseek-chat",
                temperature=0.3,
                max_tokens=1000,
                response_format="json"
            )

            # Parse LLM response
            parsed = _parse_fragment_response(response.content)

            # Build and validate the full fragment
            fragment = _validate_fragment(parsed, source, text)
            fragment["fragment_id"] = _generate_fragment_id(text, source)
            fragment["timestamp"] = timestamp
            fragment["ingested_at"] = datetime.now(timezone.utc).isoformat()

            # Store in PostgreSQL
            await _store_fragment(fragment)

            # Cache in Redis for dedup
            await _cache_fragment(fragment["fragment_id"], fragment)

            # Increment metrics
            kirin_discourse_ingested_total.labels(source=source).inc()

            return fragment

        except LLMError as e:
            if attempt < MAX_RETRIES:
                logger.warning(
                    f"LLM error on attempt {attempt + 1}: {e}, retrying in {RETRY_DELAY}s"
                )
                await asyncio.sleep(RETRY_DELAY)
                continue
            else:
                return _build_fallback_fragment(
                    text, source, context, timestamp, f"Ingestion error: {str(e)}"
                )
        except Exception as e:
            if attempt < MAX_RETRIES:
                logger.warning(
                    f"LLM error on attempt {attempt + 1}: {e}, retrying in {RETRY_DELAY}s"
                )
                await asyncio.sleep(RETRY_DELAY)
                continue
            else:
                return _build_fallback_fragment(
                    text, source, context, timestamp, f"Ingestion error: {str(e)}"
                )

    # Should not reach here, but just in case
    return _build_fallback_fragment(
        text, source, context, timestamp, "Unknown ingestion error"
    )


def _generate_fragment_id(text: str, source: str) -> str:
    """
    Generate a deterministic fragment ID from content and source.

    Uses SHA-256 hash of the concatenation of text and source to produce
    a deterministic, collision-resistant identifier.

    Args:
        text: The raw discourse text.
        source: The validated source platform.

    Returns:
        First 16 hex characters of the SHA-256 hash.
    """
    content = f"{text}{source}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def _validate_source(source: str) -> str:
    """
    Validate and normalize a source string.

    Args:
        source: The raw source string.

    Returns:
        Lowercase, stripped source string. Returns "other" if not in VALID_SOURCES.
    """
    if not source or not isinstance(source, str):
        return "other"
    normalized = source.strip().lower()
    if normalized not in VALID_SOURCES:
        return "other"
    return normalized


def _parse_fragment_response(content: str) -> Dict[str, Any]:
    """
    Parse the LLM response into a fragment dictionary.

    Attempts JSON parsing first; falls back to heuristic text extraction
    when the response is not valid JSON.

    Args:
        content: Raw text content from the LLM response.

    Returns:
        Dictionary with text, source, context, emotion, and topic fields.
    """
    # Try JSON parse first
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, TypeError):
        pass

    # Fallback: heuristic text parsing
    return _parse_fragment_text(content)


def _parse_fragment_text(text: str) -> Dict[str, Any]:
    """
    Extract fragment fields from plain text using heuristics.

    Args:
        text: Plain text response from the LLM.

    Returns:
        Dictionary with fragment fields, using defaults for missing values.
    """
    result = {
        "text": "",
        "source": "",
        "context": "",
        "emotion": "neutral",
        "topic": "other",
    }

    lines = text.split("\n")
    current_field = None

    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue

        lower_line = line_stripped.lower()

        # Detect field labels
        if lower_line.startswith('"text"') or lower_line.startswith("text:"):
            current_field = "text"
            if ":" in line_stripped:
                value = line_stripped.split(":", 1)[1].strip().strip('"').strip("'")
                if value:
                    result["text"] = value
                    current_field = None
            continue
        elif lower_line.startswith('"source"') or lower_line.startswith("source:"):
            current_field = "source"
            if ":" in line_stripped:
                value = line_stripped.split(":", 1)[1].strip().strip('"').strip("'")
                if value:
                    result["source"] = value
                    current_field = None
            continue
        elif lower_line.startswith('"context"') or lower_line.startswith("context:"):
            current_field = "context"
            if ":" in line_stripped:
                value = line_stripped.split(":", 1)[1].strip().strip('"').strip("'")
                if value:
                    result["context"] = value
                    current_field = None
            continue
        elif lower_line.startswith('"emotion"') or lower_line.startswith("emotion:"):
            current_field = "emotion"
            if ":" in line_stripped:
                value = line_stripped.split(":", 1)[1].strip().strip('"').strip("'")
                if value:
                    result["emotion"] = value
                    current_field = None
            continue
        elif lower_line.startswith('"topic"') or lower_line.startswith("topic:"):
            current_field = "topic"
            if ":" in line_stripped:
                value = line_stripped.split(":", 1)[1].strip().strip('"').strip("'")
                if value:
                    result["topic"] = value
                    current_field = None
            continue

        # Append content to current field
        if current_field and current_field in result:
            if result[current_field]:
                result[current_field] += " " + line_stripped
            else:
                result[current_field] = line_stripped

    return result


def _validate_fragment(data: Dict[str, Any], source: str, text: str) -> Dict[str, Any]:
    """
    Validate and normalize a parsed fragment, filling defaults for missing fields.

    Args:
        data: Raw parsed fragment data from the LLM.
        source: The validated source platform.
        text: The original raw discourse text.

    Returns:
        Validated fragment dictionary with all required fields properly typed.
    """
    fragment = {
        "text": str(data.get("text", text) or text),
        "source": _validate_source(str(data.get("source", source) or source)),
        "context": str(data.get("context", "") or ""),
        "emotion": str(data.get("emotion", "neutral") or "neutral").lower().strip(),
        "topic": str(data.get("topic", "other") or "other").lower().strip(),
    }

    # Ensure text is never empty - fall back to original input
    if not fragment["text"].strip():
        fragment["text"] = text

    # Ensure source is valid
    if fragment["source"] not in VALID_SOURCES:
        fragment["source"] = "other"

    return fragment


def _build_fallback_fragment(
    text: str,
    source: str,
    context: str,
    timestamp: str,
    error_reason: str,
) -> Dict[str, Any]:
    """
    Build a fallback fragment when LLM ingestion fails.

    Preserves the original text and source metadata so the fragment is not
    lost, but marks it as having failed normalization.

    Args:
        text: The original raw discourse text.
        source: The validated source platform.
        context: The original surrounding context.
        timestamp: ISO timestamp of the ingestion attempt.
        error_reason: Description of the failure.

    Returns:
        A DiscourseFragment dict with fallback defaults.
    """
    fragment_id = _generate_fragment_id(text, source)
    return {
        "fragment_id": fragment_id,
        "text": text,
        "source": _validate_source(source),
        "context": context,
        "emotion": "unknown",
        "topic": "other",
        "timestamp": timestamp,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "ingestion_success": False,
        "ingestion_error": error_reason,
    }


async def _store_fragment(fragment: Dict[str, Any]) -> None:
    """
    Store a validated fragment in PostgreSQL for long-term retention.

    Uses the fragment_id as the lead_id and stores with memory_type
    "discourse_fragment".

    Args:
        fragment: The validated DiscourseFragment dictionary.
    """
    try:
        postgres_mem = runtime.get_postgres_memory()
        if postgres_mem:
            fragment_id = fragment.get("fragment_id")
            if fragment_id:
                await postgres_mem.store_lead_memory(
                    fragment_id, "discourse_fragment", fragment
                )
    except Exception as e:
        # Log the error but do not fail the ingestion because of storage issues
        fid = fragment.get("fragment_id", "unknown")
        logger.warning(
            f"Failed to store fragment in PostgreSQL for "
            f"fragment {fid}: {e}"
        )


async def _check_duplicate(text: str, source: str) -> bool:
    """
    Check Redis cache for an already-ingested text+source combination.

    Args:
        text: The raw discourse text.
        source: The validated source platform.

    Returns:
        True if a duplicate fragment was found, False otherwise.
    """
    try:
        redis_mem = runtime.get_redis_memory()
        if redis_mem and redis_mem.redis:
            fragment_id = _generate_fragment_id(text, source)
            key = f"discourse_dedup:{fragment_id}"
            value = await redis_mem.redis.get(key)
            return value is not None
    except Exception as e:
        # Redis failure should not block ingestion
        logger.warning(f"Redis dedup check failed: {e}")
    return False


async def _retrieve_cached_fragment(fragment_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a cached fragment from Redis by its ID.

    Args:
        fragment_id: The fragment identifier.

    Returns:
        The cached fragment dictionary, or None if not found.
    """
    try:
        redis_mem = runtime.get_redis_memory()
        if redis_mem and redis_mem.redis:
            key = f"discourse_dedup:{fragment_id}"
            value = await redis_mem.redis.get(key)
            if value:
                return json.loads(value)
    except Exception as e:
        logger.warning(f"Redis fragment retrieval failed for {fragment_id}: {e}")
    return None


async def _cache_fragment(
    fragment_id: str, fragment: Dict[str, Any], ttl: int = 86400
) -> None:
    """
    Cache a fragment in Redis with a TTL for deduplication.

    Uses the raw Redis setex command via the RedisMemoryManager
    connection to store with an expiration time.

    Args:
        fragment_id: The fragment identifier (used as cache key suffix).
        fragment: The full fragment dictionary to cache.
        ttl: Time-to-live in seconds (default 86400 = 24 hours).
    """
    try:
        redis_mem = runtime.get_redis_memory()
        if redis_mem and redis_mem.redis:
            key = f"discourse_dedup:{fragment_id}"
            value = json.dumps(fragment)
            await redis_mem.redis.setex(key, ttl, value)
    except Exception as e:
        # Cache failure should not block ingestion
        logger.warning(f"Redis cache failed for fragment {fragment_id}: {e}")
