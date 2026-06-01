"""
Resonance Engine — Layer 3 of the Wittgensteinian Language Games Engine.
Learns which discourse structures generate market response.

Combines PostgreSQL for persistence, Redis for caching, and Qdrant for
similarity search to build adaptive commercial intelligence.
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from . import runtime
from .factory import ServiceFactory
from .ports.llm_client import LLMMessage
from .discourse_templates import build_resonance_prompt, build_prospect_prompt
from .metrics import kirin_resonance_lookup_total, kirin_prospect_generated_total

logger = logging.getLogger(__name__)

# Configuration
RESONANCE_TIMEOUT = 120.0  # 2 minutes — complex pattern analysis
MAX_RETRIES = 2
RETRY_DELAY = 5.0
CACHE_TTL = 3600  # 1 hour for resonance cache

# Valid signal types for market response signals
VALID_SIGNAL_TYPES = [
    "engagement", "conversion", "reply", "ctr", "ignore", "negative",
]

# Cluster fields expected from the LLM
CLUSTER_FIELDS = [
    "market_cluster", "high_resonance_patterns", "low_resonance_patterns",
    "effective_hooks", "failed_hooks", "belief_density", "tension_score",
]

# Prospect profile fields expected from the LLM
PROSPECT_FIELDS = [
    "belief", "identity", "objection", "resonance_pattern",
    "narrative", "outreach_angle", "market_cluster", "confidence",
]


# ─── Main Entry Points ──────────────────────────────────────────────────────

async def analyze_resonance(
    analyses: List[Dict[str, Any]],
    market_cluster: str = "",
    litellm_url: str = "",
    api_key: str = "",
) -> Dict[str, Any]:
    """
    Analyze a set of LanguageGameAnalysis dicts to discover resonance patterns.

    Takes the output from Layer 2 (language game analysis) and asks the LLM
    to synthesize cross-fragment patterns — identifying what resonates, what
    falls flat, and what hooks work for a given market segment. The result
    is a ResonanceCluster stored in PostgreSQL and Qdrant.

    Args:
        analyses: List of LanguageGameAnalysis dicts from Layer 2.
        market_cluster: Optional market vertical filter / classification anchor.
        litellm_url: URL of the LiteLLM service (deprecated, use ServiceFactory).
        api_key: API key for the deepseek-chat model (deprecated, use ServiceFactory).

    Returns:
        Full ResonanceCluster dict with cluster_id assigned.
    """
    if not analyses:
        logger.warning("analyze_resonance called with empty analyses list")
        return _build_fallback_cluster([], "Empty analyses list")

    llm = ServiceFactory.get_llm_client()

    # Build prompt via discourse_templates
    prompt = build_resonance_prompt(analyses, market_cluster)

    messages = [LLMMessage(role="user", content=prompt)]

    # Call LLM with retries
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = await llm.complete(
                messages=messages,
                model="deepseek-chat",
                temperature=0.3,
                max_tokens=1500,
            )

            if response.success:
                content = response.content

                # Parse LLM response
                parsed = _parse_cluster_response(content)

                # Validate fields
                cluster = _validate_cluster(parsed)

                # Attach source analysis count
                cluster["source_analysis_count"] = len(analyses)

                # Store in PostgreSQL
                cluster_id = await _store_cluster(cluster)
                cluster["cluster_id"] = cluster_id

                # Store in Qdrant for similarity search
                # Note: vector search will be enabled when an embedding model
                # is integrated. For now, we store payload only for filtering.
                await _store_cluster_qdrant(cluster_id, cluster)

                # Cache in Redis
                await _cache_cluster(cluster_id, cluster)

                # Increment metrics
                kirin_resonance_lookup_total.labels(market_cluster=cluster.get("market_cluster", "unknown")).inc()

                return cluster

            else:
                if attempt < MAX_RETRIES:
                    logger.warning(
                        f"LLM error on attempt {attempt + 1}: {response.error}, "
                        f"retrying in {RETRY_DELAY}s"
                    )
                    await asyncio.sleep(RETRY_DELAY)
                    continue
                else:
                    return _build_fallback_cluster(
                        analyses, f"LLM error: {response.error}"
                    )

        except Exception as e:
            if attempt < MAX_RETRIES:
                logger.warning(
                    f"LLM error on attempt {attempt + 1}: {e}, "
                    f"retrying in {RETRY_DELAY}s"
                )
                await asyncio.sleep(RETRY_DELAY)
                continue
            else:
                return _build_fallback_cluster(
                    analyses, f"Resonance analysis error: {str(e)}"
                )

    # Should not reach here, but just in case
    return _build_fallback_cluster(analyses, "Unknown resonance analysis error")


async def lookup_resonance(
    query: str,
    litellm_url: str = "",
    api_key: str = "",
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """
    Search for similar resonance patterns using Qdrant, falling back to
    PostgreSQL if Qdrant is unavailable.

    Uses payload filtering (scroll + filter) rather than vector search,
    since no embedding model is integrated yet. When an embedding model
    is added, this will switch to vector similarity search.

    Args:
        query: Free-text query describing the resonance pattern to search for.
        litellm_url: URL of the LiteLLM service (reserved for future embedding calls).
        api_key: API key for the LLM service (reserved for future embedding calls).
        limit: Maximum number of results to return.

    Returns:
        List of matching ResonanceCluster dicts, most relevant first.
    """
    # Check Redis cache first
    cache_key = f"resonance:lookup:{query}:{limit}"
    cached = await _get_cached_lookup(cache_key)
    if cached is not None:
        return cached

    # Try Qdrant first, then fall back to PostgreSQL
    results = await _search_qdrant_clusters(query, limit)
    if not results:
        results = await _search_postgres_clusters(query, limit)

    # Cache the lookup results
    if results:
        await _cache_lookup(cache_key, results)

    # Increment metrics
    kirin_resonance_lookup_total.labels(market_cluster="lookup").inc()

    return results


async def record_signal(
    cluster_id: str,
    signal_type: str,
    strength: float,
    metadata: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    Record a market response signal for a resonance cluster.

    Signals accumulate over time to refine the cluster's resonance model.
    Stored in PostgreSQL as part of the cluster's signal history and
    reflected in the Redis cache.

    Args:
        cluster_id: The ResonanceCluster this signal belongs to.
        signal_type: Type of market response: engagement, conversion, reply,
            ctr, ignore, or negative.
        strength: Signal strength from 0.0 (negligible) to 1.0 (maximum).
        metadata: Optional key-value pairs for signal-specific data.

    Returns:
        The recorded signal dict with signal_id and timestamp assigned.
    """
    # Validate signal_type
    if signal_type not in VALID_SIGNAL_TYPES:
        logger.warning(
            f"Invalid signal_type '{signal_type}', normalizing to 'engagement'"
        )
        signal_type = "engagement"

    # Clamp strength to 0.0–1.0
    strength = max(0.0, min(1.0, float(strength)))

    # Build signal dict
    signal: Dict[str, Any] = {
        "signal_id": uuid.uuid4().hex[:16],
        "cluster_id": cluster_id,
        "signal_type": signal_type,
        "strength": strength,
        "metadata": metadata or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Store in PostgreSQL
    await _store_signal_postgres(signal)

    # Update cluster signal history in PostgreSQL
    await _update_cluster_signals(cluster_id, signal)

    # Invalidate / update Redis cache for this cluster
    await _invalidate_cluster_cache(cluster_id)

    return signal


async def generate_prospect(
    analysis: Dict[str, Any],
    resonance: Optional[Dict[str, Any]] = None,
    litellm_url: str = "",
    api_key: str = "",
) -> Dict[str, Any]:
    """
    Generate a ProspectProfile from a single LanguageGameAnalysis and
    an optional ResonanceCluster.

    Calls LLM with the prospect prompt to craft an actionable outreach
    strategy that plays the right language game with the right frame.

    Args:
        analysis: A LanguageGameAnalysis dict from Layer 2.
        resonance: Optional ResonanceCluster dict from analyze_resonance.
        litellm_url: URL of the LiteLLM service (deprecated, use ServiceFactory).
        api_key: API key for the deepseek-chat model (deprecated, use ServiceFactory).

    Returns:
        ProspectProfile dict with all required fields.
    """
    if not analysis:
        logger.warning("generate_prospect called with empty analysis")
        return _build_fallback_prospect({}, "Empty analysis input")

    llm = ServiceFactory.get_llm_client()

    # Build prompt via discourse_templates
    prompt = build_prospect_prompt(analysis, resonance)

    messages = [LLMMessage(role="user", content=prompt)]

    # Call LLM with retries
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = await llm.complete(
                messages=messages,
                model="deepseek-chat",
                temperature=0.5,
                max_tokens=800,
            )

            if response.success:
                content = response.content

                # Parse LLM response
                parsed = _parse_prospect_response(content)

                # Validate fields
                prospect = _validate_prospect(parsed)

                # Increment metrics
                kirin_prospect_generated_total.inc()

                return prospect

            else:
                if attempt < MAX_RETRIES:
                    logger.warning(
                        f"LLM error on attempt {attempt + 1}: {response.error}, "
                        f"retrying in {RETRY_DELAY}s"
                    )
                    await asyncio.sleep(RETRY_DELAY)
                    continue
                else:
                    return _build_fallback_prospect(
                        analysis, f"LLM error: {response.error}"
                    )

        except Exception as e:
            if attempt < MAX_RETRIES:
                logger.warning(
                    f"LLM error on attempt {attempt + 1}: {e}, "
                    f"retrying in {RETRY_DELAY}s"
                )
                await asyncio.sleep(RETRY_DELAY)
                continue
            else:
                return _build_fallback_prospect(
                    analysis, f"Prospect generation error: {str(e)}"
                )

    # Should not reach here, but just in case
    return _build_fallback_prospect(analysis, "Unknown prospect generation error")


# ─── Validation ──────────────────────────────────────────────────────────────

def _validate_cluster(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and normalize a parsed ResonanceCluster, filling defaults
    for missing fields.

    Ensures all list fields are lists, numeric fields are 0.0–1.0, and
    string fields have sensible defaults.

    Args:
        data: Raw parsed cluster data from the LLM.

    Returns:
        Validated cluster dictionary with all required fields properly typed.
    """
    cluster: Dict[str, Any] = {}

    # String field with default
    cluster["market_cluster"] = str(
        data.get("market_cluster", "") or "unknown"
    ).strip() or "unknown"

    # List fields — must be lists of strings
    list_fields = [
        "high_resonance_patterns", "low_resonance_patterns",
        "effective_hooks", "failed_hooks",
    ]
    for field_name in list_fields:
        raw = data.get(field_name, [])
        if isinstance(raw, list):
            cluster[field_name] = [
                str(item).strip() for item in raw
                if item and str(item).strip()
            ]
        elif isinstance(raw, str) and raw.strip():
            cluster[field_name] = [raw.strip()]
        else:
            cluster[field_name] = []

    # Float fields — clamp to 0.0–1.0
    belief_density = data.get("belief_density", 0.5)
    try:
        cluster["belief_density"] = max(0.0, min(1.0, float(belief_density)))
    except (ValueError, TypeError):
        cluster["belief_density"] = 0.5

    tension_score = data.get("tension_score", 0.5)
    try:
        cluster["tension_score"] = max(0.0, min(1.0, float(tension_score)))
    except (ValueError, TypeError):
        cluster["tension_score"] = 0.5

    return cluster


def _validate_prospect(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and normalize a parsed ProspectProfile, filling defaults
    for missing fields.

    Ensures confidence is 0.0–1.0 and all string fields have defaults.

    Args:
        data: Raw parsed prospect data from the LLM.

    Returns:
        Validated prospect profile dictionary with all required fields.
    """
    prospect: Dict[str, Any] = {}

    # String fields with defaults
    string_defaults = {
        "belief": "unknown",
        "identity": "unknown",
        "objection": "unknown",
        "resonance_pattern": "unknown",
        "narrative": "",
        "outreach_angle": "unknown",
        "market_cluster": "",
    }
    for field_name, default_val in string_defaults.items():
        value = data.get(field_name, "")
        if value and str(value).strip():
            prospect[field_name] = str(value).strip()
        else:
            prospect[field_name] = default_val

    # Confidence — clamp to 0.0–1.0
    confidence = data.get("confidence", 0.5)
    try:
        prospect["confidence"] = max(0.0, min(1.0, float(confidence)))
    except (ValueError, TypeError):
        prospect["confidence"] = 0.5

    return prospect


# ─── Parsing ─────────────────────────────────────────────────────────────────

def _parse_cluster_response(content: str) -> Dict[str, Any]:
    """
    Parse the LLM response into a resonance cluster dictionary.

    Attempts JSON parsing first; falls back to heuristic text extraction.

    Args:
        content: Raw text content from the LLM response.

    Returns:
        Dictionary with ResonanceCluster fields.
    """
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, TypeError):
        pass

    return _parse_cluster_text(content)


def _parse_cluster_text(text: str) -> Dict[str, Any]:
    """
    Extract cluster fields from plain text using heuristics.

    Args:
        text: Plain text response from the LLM.

    Returns:
        Dictionary with ResonanceCluster fields, using defaults for missing values.
    """
    result: Dict[str, Any] = {
        "market_cluster": "unknown",
        "high_resonance_patterns": [],
        "low_resonance_patterns": [],
        "effective_hooks": [],
        "failed_hooks": [],
        "belief_density": 0.5,
        "tension_score": 0.5,
    }

    lines = text.split("\n")
    current_field: Optional[str] = None
    collecting_list: Optional[str] = None
    list_items: List[str] = []

    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue

        lower_line = line_stripped.lower()

        # Stop collecting a list if we hit a new field or closing bracket
        if collecting_list:
            if line_stripped in ("]", "}"):
                result[collecting_list] = list_items
                collecting_list = None
                list_items = []
                continue
            # Strip list markers and add item
            import re
            cleaned = re.sub(r"^[-\*\d\.\s]+", "", line_stripped).strip()
            cleaned = cleaned.strip('"\'')
            if cleaned and cleaned not in ("[]", "[ ]"):
                list_items.append(cleaned)
            continue
        
        # Detect numeric fields
        for num_field in ["belief_density", "tension_score"]:
            if num_field in lower_line and (":" in line_stripped or "=" in line_stripped):
                sep = ":" if ":" in line_stripped else "="
                val_str = line_stripped.split(sep, 1)[1].strip()
                try:
                    result[num_field] = max(0.0, min(1.0, float(val_str)))
                except (ValueError, TypeError):
                    pass
                current_field = None
                break
        else:
            # Detect string/list fields
            field_map = {
                "market_cluster": "market_cluster",
                "high_resonance": "high_resonance_patterns",
                "low_resonance": "low_resonance_patterns",
                "effective_hook": "effective_hooks",
                "failed_hook": "failed_hooks",
            }
            matched = False
            for key, canonical in field_map.items():
                if key in lower_line:
                    if ":" in line_stripped:
                        after_colon = line_stripped.split(":", 1)[1].strip()
                        if canonical == "market_cluster":
                            result[canonical] = after_colon.strip('"\'') or "unknown"
                        else:
                            # Try to parse as JSON array
                            try:
                                parsed = json.loads(after_colon)
                                if isinstance(parsed, list):
                                    result[canonical] = [
                                        str(s).strip() for s in parsed if s and str(s).strip()
                                    ]
                                else:
                                    result[canonical] = [str(parsed)]
                            except (json.JSONDecodeError, TypeError):
                                if after_colon and after_colon not in ("[]", "[ ]"):
                                    result[canonical] = [after_colon.strip('"\'')]
                                else:
                                    # Start collecting list items from subsequent lines
                                    collecting_list = canonical
                                    list_items = []
                    matched = True
                    current_field = None
                    break

    # Flush any remaining list
    if collecting_list and list_items:
        result[collecting_list] = list_items

    return result


def _parse_prospect_response(content: str) -> Dict[str, Any]:
    """
    Parse the LLM response into a prospect profile dictionary.

    Attempts JSON parsing first; falls back to heuristic text extraction.

    Args:
        content: Raw text content from the LLM response.

    Returns:
        Dictionary with ProspectProfile fields.
    """
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, TypeError):
        pass

    return _parse_prospect_text(content)


def _parse_prospect_text(text: str) -> Dict[str, Any]:
    """
    Extract prospect profile fields from plain text using heuristics.

    Args:
        text: Plain text response from the LLM.

    Returns:
        Dictionary with ProspectProfile fields, using defaults for missing values.
    """
    result: Dict[str, Any] = {
        "belief": "unknown",
        "identity": "unknown",
        "objection": "unknown",
        "resonance_pattern": "unknown",
        "narrative": "",
        "outreach_angle": "unknown",
        "market_cluster": "",
        "confidence": 0.5,
    }

    lines = text.split("\n")
    current_field: Optional[str] = None

    field_aliases: Dict[str, str] = {}
    for field in PROSPECT_FIELDS:
        field_aliases[field] = field
        field_aliases[field.replace("_", "")] = field
        field_aliases[field.replace("_", "-")] = field

    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue

        lower_line = line_stripped.lower()

        # Detect confidence (numeric)
        if "confidence" in lower_line and (":" in line_stripped or "=" in line_stripped):
            sep = ":" if ":" in line_stripped else "="
            val_str = line_stripped.split(sep, 1)[1].strip()
            try:
                result["confidence"] = max(0.0, min(1.0, float(val_str)))
            except (ValueError, TypeError):
                pass
            current_field = None
            continue

        # Detect string fields
        matched = False
        for alias, canonical in field_aliases.items():
            if canonical == "confidence":
                continue  # Already handled above
            patterns = [f'"{alias}"', f"'{alias}'", f"{alias}:", f"{alias} :"]
            for pattern in patterns:
                if lower_line.startswith(pattern.lower()):
                    current_field = canonical
                    matched = True
                    for sep in [": ", ":", '\":\"', '\": ']:
                        if sep in line_stripped:
                            value = line_stripped.split(sep, 1)[1].strip()
                            value = value.strip('"').strip("'")
                            if value:
                                result[canonical] = value
                                current_field = None
                            break
                    break
            if matched:
                break

        # Append continuation text to current field
        if current_field and current_field in result:
            if result[current_field] in ("", "unknown"):
                result[current_field] = line_stripped
            else:
                result[current_field] += " " + line_stripped

    return result


# ─── Storage: PostgreSQL ─────────────────────────────────────────────────────

async def _store_cluster(cluster: Dict[str, Any]) -> str:
    """
    Store a ResonanceCluster in PostgreSQL.

    Uses the lead_memory table with memory_type "resonance_cluster".
    Generates a cluster_id (uuid4 hex[:16]) if not present.

    Args:
        cluster: The validated ResonanceCluster dictionary.

    Returns:
        The cluster_id assigned to this cluster.
    """
    cluster_id = cluster.get("cluster_id") or uuid.uuid4().hex[:16]
    cluster["cluster_id"] = cluster_id

    try:
        postgres_mem = runtime.get_postgres_memory()
        if postgres_mem:
            # Store the full cluster as JSONB in lead_memory
            store_data = cluster.copy()
            store_data["stored_at"] = datetime.now(timezone.utc).isoformat()
            await postgres_mem.store_lead_memory(
                cluster_id, "resonance_cluster", store_data
            )
            logger.info(f"Stored resonance cluster {cluster_id} in PostgreSQL")
    except Exception as e:
        logger.warning(
            f"Failed to store resonance cluster {cluster_id} in PostgreSQL: {e}"
        )

    return cluster_id


async def _store_signal_postgres(signal: Dict[str, Any]) -> None:
    """
    Store a resonance signal in PostgreSQL using the lead_memory table.

    Uses lead_id = cluster_id, memory_type = "resonance_signal:{signal_id}"
    so each signal is a separate row. Graceful failure.

    Args:
        signal: The validated signal dictionary.
    """
    try:
        postgres_mem = runtime.get_postgres_memory()
        if postgres_mem:
            cluster_id = signal["cluster_id"]
            signal_id = signal["signal_id"]
            await postgres_mem.store_lead_memory(
                cluster_id, f"resonance_signal:{signal_id}", signal
            )
            logger.info(
                f"Stored signal {signal_id} for cluster {cluster_id} in PostgreSQL"
            )
    except Exception as e:
        logger.warning(
            f"Failed to store signal {signal.get('signal_id', '?')} "
            f"in PostgreSQL: {e}"
        )


async def _update_cluster_signals(cluster_id: str, signal: Dict[str, Any]) -> None:
    """
    Append a signal to a cluster's signal history in PostgreSQL.

    Retrieves the existing cluster, appends the new signal to its
    signal_history list, and re-stores it. Graceful failure.

    Args:
        cluster_id: The ResonanceCluster identifier.
        signal: The signal dict to append.
    """
    try:
        postgres_mem = runtime.get_postgres_memory()
        if not postgres_mem:
            return

        # Retrieve existing cluster
        existing = await postgres_mem.retrieve_lead_memory(
            cluster_id, "resonance_cluster"
        )
        if existing:
            # Append signal to history
            history = existing.get("signal_history", [])
            history.append(signal)
            # Keep only the last 100 signals to prevent unbounded growth
            existing["signal_history"] = history[-100:]
            existing["signal_count"] = len(existing["signal_history"])
            existing["last_signal_at"] = signal.get("timestamp", "")

            # Re-store updated cluster
            await postgres_mem.store_lead_memory(
                cluster_id, "resonance_cluster", existing
            )
    except Exception as e:
        logger.warning(
            f"Failed to update cluster signals for {cluster_id}: {e}"
        )


# ─── Storage: Qdrant ────────────────────────────────────────────────────────

async def _store_cluster_qdrant(cluster_id: str, cluster: Dict[str, Any]) -> None:
    """
    Store a ResonanceCluster in Qdrant for similarity search.

    Stores the cluster using the memory manager's store_text() method.
    Vector search will be enabled when an embedding model is integrated.

    Args:
        cluster_id: The cluster identifier.
        cluster: The validated ResonanceCluster dictionary.
    """
    try:
        qdrant_mem = runtime.get_qdrant_memory()
        if not qdrant_mem:
            return

        # Build a text representation for future embedding
        text_repr = _build_cluster_text_representation(cluster)

        payload = {
            "cluster_id": cluster_id,
            "type": "resonance_cluster",
            "market_cluster": cluster.get("market_cluster", "unknown"),
            "belief_density": cluster.get("belief_density", 0.5),
            "tension_score": cluster.get("tension_score", 0.5),
            "high_resonance_patterns": cluster.get("high_resonance_patterns", []),
            "low_resonance_patterns": cluster.get("low_resonance_patterns", []),
            "effective_hooks": cluster.get("effective_hooks", []),
            "failed_hooks": cluster.get("failed_hooks", []),
            "text_representation": text_repr,
        }

        # Use a deterministic point ID based on cluster_id
        point_id = abs(hash(cluster_id)) % (2**63)

        success = await qdrant_mem.store_text(
            collection_name="kirin_discourse",
            text=text_repr,
            payload=payload,
            point_id=point_id,
        )

        if success:
            logger.info(f"Stored resonance cluster {cluster_id} in Qdrant")

    except Exception as e:
        logger.warning(
            f"Failed to store resonance cluster {cluster_id} in Qdrant: {e}"
        )


def _build_cluster_text_representation(cluster: Dict[str, Any]) -> str:
    """
    Build a text representation of a cluster for future embedding.

    Concatenates the cluster's key patterns and hooks into a single
    text block that can be embedded for vector similarity search.

    Args:
        cluster: The ResonanceCluster dictionary.

    Returns:
        A text string summarizing the cluster.
    """
    parts = [f"Market: {cluster.get('market_cluster', 'unknown')}"]

    for pattern in cluster.get("high_resonance_patterns", []):
        parts.append(f"High resonance: {pattern}")
    for pattern in cluster.get("effective_hooks", []):
        parts.append(f"Effective hook: {pattern}")
    for pattern in cluster.get("low_resonance_patterns", []):
        parts.append(f"Low resonance: {pattern}")
    for pattern in cluster.get("failed_hooks", []):
        parts.append(f"Failed hook: {pattern}")

    return " | ".join(parts)


# ─── Search: Qdrant ─────────────────────────────────────────────────────────

async def _search_qdrant_clusters(query: str, limit: int) -> List[Dict[str, Any]]:
    """
    Search Qdrant kirin_discourse collection for similar clusters.

    Uses the memory manager's search_text() method to find clusters.

    Args:
        query: Free-text query for text-based filtering.
        limit: Maximum number of results.

    Returns:
        List of matching cluster dicts.
    """
    try:
        qdrant_mem = runtime.get_qdrant_memory()
        if not qdrant_mem:
            return []

        results = await qdrant_mem.search_text(
            collection_name="kirin_discourse",
            query=query,
            limit=limit,
        )

        # Filter for resonance_cluster type only
        clusters = [
            r for r in results
            if r.get("type") == "resonance_cluster"
        ]

        return clusters

    except Exception as e:
        logger.warning(f"Qdrant search failed: {e}")
        return []


# ─── Search: PostgreSQL (fallback) ──────────────────────────────────────────

async def _search_postgres_clusters(query: str, limit: int) -> List[Dict[str, Any]]:
    """
    Fallback: search PostgreSQL for resonance clusters matching text patterns.

    Uses the memory manager's search_by_text() method to query for
    resonance clusters.

    Args:
        query: Free-text query for text matching.
        limit: Maximum number of results.

    Returns:
        List of matching cluster dicts.
    """
    try:
        postgres_mem = runtime.get_postgres_memory()
        if not postgres_mem:
            return []

        return await postgres_mem.search_by_text("resonance_cluster", query, limit)

    except Exception as e:
        logger.warning(f"PostgreSQL cluster search failed: {e}")
        return []


# ─── Cache: Redis ────────────────────────────────────────────────────────────

async def _cache_cluster(cluster_id: str, cluster: Dict[str, Any]) -> None:
    """
    Cache a resonance cluster in Redis with CACHE_TTL.

    Args:
        cluster_id: The cluster identifier.
        cluster: The cluster dictionary to cache.
    """
    try:
        redis_mem = runtime.get_redis_memory()
        if not redis_mem:
            return

        key = f"resonance:cluster:{cluster_id}"
        await redis_mem.cache_set(key, cluster, ttl_seconds=CACHE_TTL)
    except Exception as e:
        logger.warning(
            f"Failed to cache resonance cluster {cluster_id} in Redis: {e}"
        )


async def _get_cached_cluster(cluster_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a resonance cluster from Redis cache.

    Args:
        cluster_id: The cluster identifier.

    Returns:
        The cached cluster dict, or None if not cached.
    """
    try:
        redis_mem = runtime.get_redis_memory()
        if not redis_mem:
            return None

        key = f"resonance:cluster:{cluster_id}"
        return await redis_mem.cache_get(key)
    except Exception as e:
        logger.warning(
            f"Failed to retrieve cached cluster {cluster_id} from Redis: {e}"
        )
        return None


async def _get_cached_lookup(cache_key: str) -> Optional[List[Dict[str, Any]]]:
    """
    Retrieve cached lookup results from Redis.

    Args:
        cache_key: The Redis cache key.

    Returns:
        List of cached cluster dicts, or None if not cached.
    """
    try:
        redis_mem = runtime.get_redis_memory()
        if not redis_mem:
            return None

        return await redis_mem.cache_get(cache_key)
    except Exception as e:
        logger.warning(f"Failed to retrieve cached lookup from Redis: {e}")
        return None


async def _cache_lookup(cache_key: str, results: List[Dict[str, Any]]) -> None:
    """
    Cache lookup results in Redis with CACHE_TTL.

    Args:
        cache_key: The Redis cache key.
        results: The results list to cache.
    """
    try:
        redis_mem = runtime.get_redis_memory()
        if not redis_mem:
            return

        await redis_mem.cache_set(cache_key, results, ttl_seconds=CACHE_TTL)
    except Exception as e:
        logger.warning(f"Failed to cache lookup results in Redis: {e}")


async def _invalidate_cluster_cache(cluster_id: str) -> None:
    """
    Invalidate the Redis cache for a cluster after a signal update.

    Deletes the cluster cache key so the next retrieval fetches fresh
    data from PostgreSQL.

    Args:
        cluster_id: The cluster identifier whose cache to invalidate.
    """
    try:
        redis_mem = runtime.get_redis_memory()
        if not redis_mem:
            return

        key = f"resonance:cluster:{cluster_id}"
        await redis_mem.cache_delete(key)
    except Exception as e:
        logger.warning(
            f"Failed to invalidate cache for cluster {cluster_id}: {e}"
        )


# ─── Fallbacks ───────────────────────────────────────────────────────────────

def _build_fallback_cluster(
    analyses: List[Dict[str, Any]],
    error_reason: str,
) -> Dict[str, Any]:
    """
    Build a minimal ResonanceCluster from raw analyses when the LLM fails.

    Extracts common themes using simple set intersection of language games,
    objection types, and framing patterns found across analyses.

    Args:
        analyses: The input analysis list (may be empty).
        error_reason: Description of the failure.

    Returns:
        A ResonanceCluster-compatible dict with fallback values.
    """
    # Extract common patterns from analyses
    language_games: List[str] = []
    objection_types: List[str] = []
    framing_patterns: List[str] = []
    identity_markers: List[str] = []
    tensions: List[str] = []
    beliefs: List[str] = []

    for analysis in analyses:
        if analysis.get("language_game") and analysis["language_game"] != "unknown":
            language_games.append(analysis["language_game"])
        if analysis.get("objection_type") and analysis["objection_type"] != "unknown":
            objection_types.append(analysis["objection_type"])
        if analysis.get("framing_pattern") and analysis["framing_pattern"] != "unknown":
            framing_patterns.append(analysis["framing_pattern"])
        if analysis.get("identity_marker") and analysis["identity_marker"] != "unknown":
            identity_markers.append(analysis["identity_marker"])
        if analysis.get("tension") and analysis["tension"] != "unknown":
            tensions.append(analysis["tension"])
        if analysis.get("belief") and analysis["belief"] != "unknown":
            beliefs.append(analysis["belief"])

    # Find repeated patterns (frequency >= 2 or all unique patterns if fewer analyses)
    from collections import Counter

    def _frequent(items: List[str], min_count: int = 1) -> List[str]:
        counts = Counter(items)
        return list(dict.fromkeys(
            item for item, count in counts.items() if count >= min_count
        ))

    # Use patterns that appear at least once (since we may have few analyses)
    high_patterns = _frequent(
        language_games + framing_patterns, min_count=1
    )[:5]
    effective_hooks = _frequent(
        identity_markers + tensions, min_count=1
    )[:5]

    cluster: Dict[str, Any] = {
        "cluster_id": None,  # Will be set by _store_cluster
        "market_cluster": "unknown",
        "high_resonance_patterns": high_patterns or ["unknown"],
        "low_resonance_patterns": [],
        "effective_hooks": effective_hooks or ["unknown"],
        "failed_hooks": [],
        "belief_density": 0.3 if len(beliefs) < 2 else 0.6,
        "tension_score": 0.3 if len(tensions) < 2 else 0.6,
        "source_analysis_count": len(analyses),
        "cluster_fallback": True,
        "cluster_error": error_reason,
    }

    return cluster


def _build_fallback_prospect(
    analysis: Dict[str, Any],
    error_reason: str,
) -> Dict[str, Any]:
    """
    Build a minimal ProspectProfile from raw analysis when the LLM fails.

    Extracts whatever is available from the analysis and constructs a
    bare-bones outreach profile.

    Args:
        analysis: The LanguageGameAnalysis dict (may be empty).
        error_reason: Description of the failure.

    Returns:
        A ProspectProfile-compatible dict with fallback values.
    """
    belief = analysis.get("belief", "unknown") or "unknown"
    identity = analysis.get("identity_marker", "unknown") or "unknown"
    objection = analysis.get("objection_type", "unknown") or "unknown"
    tension = analysis.get("tension", "unknown") or "unknown"
    market_cluster = ""  # Prospect profiles don't always carry cluster info

    # Build a minimal narrative from available signals
    narrative_parts: List[str] = []
    if belief != "unknown":
        narrative_parts.append(f"Addressing belief: {belief}")
    if tension != "unknown":
        narrative_parts.append(f"Core tension: {tension}")
    narrative = " | ".join(narrative_parts) if narrative_parts else "No narrative available — LLM fallback."

    # Determine confidence based on data availability
    signal_count = sum(
        1 for v in [belief, identity, objection, tension]
        if v and v != "unknown"
    )
    confidence = min(1.0, signal_count * 0.2)

    prospect: Dict[str, Any] = {
        "belief": belief,
        "identity": identity,
        "objection": objection,
        "resonance_pattern": "unknown",
        "narrative": narrative,
        "outreach_angle": "unknown",
        "market_cluster": market_cluster,
        "confidence": round(confidence, 2),
        "prospect_fallback": True,
        "prospect_error": error_reason,
    }

    return prospect
