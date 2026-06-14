"""
Resonance Engine — Layer 3 of the Wittgensteinian Language Games Engine.
Cross-fragment pattern detection, resonance clustering, and prospect generation.

Uses LLM for synthesis and ChromaStore for persistence + vector search.
No more Qdrant, no more Redis — just ChromaDB.
"""
import asyncio
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from src.analysis.templates import build_resonance_prompt, build_prospect_prompt
from agents.factory import ServiceFactory
from agents.ports.llm_client import LLMMessage
from agents.metrics import kirin_resonance_lookup_total, kirin_prospect_generated_total
from src.store import ChromaStore

logger = logging.getLogger(__name__)

RESONANCE_TIMEOUT = 120.0
MAX_RETRIES = 2
RETRY_DELAY = 5.0

VALID_SIGNAL_TYPES = ["engagement", "conversion", "reply", "ctr", "ignore", "negative"]

CLUSTER_FIELDS = [
    "market_cluster", "high_resonance_patterns", "low_resonance_patterns",
    "effective_hooks", "failed_hooks", "belief_density", "tension_score",
]

PROSPECT_FIELDS = [
    "belief", "identity", "objection", "resonance_pattern",
    "narrative", "outreach_angle", "market_cluster", "confidence",
]


# ─── Main Entry Points ────────────────────────────────────────────────

async def analyze_resonance(
    analyses: List[Dict[str, Any]],
    market_cluster: str = "",
    litellm_url: str = "",
    api_key: str = "",
    store: Optional[ChromaStore] = None,
) -> Dict[str, Any]:
    if not analyses:
        logger.warning("analyze_resonance called with empty analyses list")
        return _build_fallback_cluster([], "Empty analyses list")

    llm = ServiceFactory.get_llm_client()
    prompt = build_resonance_prompt(analyses, market_cluster)
    messages = [LLMMessage(role="user", content=prompt)]

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = await llm.complete(
                messages=messages,
                model="deepseek-chat",
                temperature=0.3,
                max_tokens=1500,
            )

            if response.success:
                parsed = _parse_cluster_response(response.content)
                cluster = _validate_cluster(parsed)
                cluster["source_analysis_count"] = len(analyses)

                if store:
                    cluster_id = uuid.uuid4().hex[:16]
                    cluster["cluster_id"] = cluster_id
                    await store.store_lead_memory(cluster_id, "resonance_cluster", cluster)
                    text_repr = _build_cluster_text(cluster)
                    await store.store_text("kirin_discourse", text_repr, {
                        "cluster_id": cluster_id,
                        "type": "resonance_cluster",
                        "market_cluster": cluster.get("market_cluster", "unknown"),
                    })

                kirin_resonance_lookup_total.labels(
                    market_cluster=cluster.get("market_cluster", "unknown")
                ).inc()
                return cluster

            if attempt < MAX_RETRIES:
                logger.warning(f"LLM error attempt {attempt + 1}: {response.error}, retrying...")
                await asyncio.sleep(RETRY_DELAY)
                continue
            return _build_fallback_cluster(analyses, f"LLM error: {response.error}")

        except Exception as e:
            if attempt < MAX_RETRIES:
                logger.warning(f"Error attempt {attempt + 1}: {e}, retrying...")
                await asyncio.sleep(RETRY_DELAY)
                continue
            return _build_fallback_cluster(analyses, f"Resonance error: {e}")

    return _build_fallback_cluster(analyses, "Unknown error")


async def lookup_resonance(
    query: str,
    litellm_url: str = "",
    api_key: str = "",
    limit: int = 5,
    store: Optional[ChromaStore] = None,
) -> List[Dict[str, Any]]:
    if not store:
        return []

    cached = await store.cache_get(f"resonance:lookup:{query}:{limit}")
    if cached is not None:
        return cached

    results = await store.search_text("kirin_discourse", query, limit)
    clusters = [r for r in results if r.get("type") == "resonance_cluster"]

    if clusters:
        await store.cache_set(f"resonance:lookup:{query}:{limit}", clusters, 3600)

    kirin_resonance_lookup_total.labels(market_cluster="lookup").inc()
    return clusters


async def record_signal(
    cluster_id: str,
    signal_type: str,
    strength: float,
    metadata: Dict[str, Any] = None,
    store: Optional[ChromaStore] = None,
) -> Dict[str, Any]:
    if signal_type not in VALID_SIGNAL_TYPES:
        logger.warning(f"Invalid signal_type '{signal_type}', defaulting to 'engagement'")
        signal_type = "engagement"

    strength = max(0.0, min(1.0, float(strength)))

    signal = {
        "signal_id": uuid.uuid4().hex[:16],
        "cluster_id": cluster_id,
        "signal_type": signal_type,
        "strength": strength,
        "metadata": metadata or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if store:
        await store.store_lead_memory(cluster_id, f"resonance_signal:{signal['signal_id']}", signal)
        existing = await store.retrieve_lead_memory(cluster_id, "resonance_cluster")
        if existing:
            history = existing.get("signal_history", [])
            history.append(signal)
            existing["signal_history"] = history[-100:]
            existing["signal_count"] = len(existing["signal_history"])
            existing["last_signal_at"] = signal.get("timestamp", "")
            await store.store_lead_memory(cluster_id, "resonance_cluster", existing)
        await store.cache_delete(f"resonance:cluster:{cluster_id}")

    return signal


async def generate_prospect(
    analysis: Dict[str, Any],
    resonance: Optional[Dict[str, Any]] = None,
    litellm_url: str = "",
    api_key: str = "",
    store: Optional[ChromaStore] = None,
) -> Dict[str, Any]:
    if not analysis:
        logger.warning("generate_prospect called with empty analysis")
        return _build_fallback_prospect({}, "Empty analysis input")

    llm = ServiceFactory.get_llm_client()
    prompt = build_prospect_prompt(analysis, resonance)
    messages = [LLMMessage(role="user", content=prompt)]

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = await llm.complete(
                messages=messages,
                model="deepseek-chat",
                temperature=0.5,
                max_tokens=800,
            )

            if response.success:
                parsed = _parse_prospect_response(response.content)
                prospect = _validate_prospect(parsed)
                kirin_prospect_generated_total.inc()
                return prospect

            if attempt < MAX_RETRIES:
                logger.warning(f"LLM error attempt {attempt + 1}: {response.error}, retrying...")
                await asyncio.sleep(RETRY_DELAY)
                continue
            return _build_fallback_prospect(analysis, f"LLM error: {response.error}")

        except Exception as e:
            if attempt < MAX_RETRIES:
                logger.warning(f"Error attempt {attempt + 1}: {e}, retrying...")
                await asyncio.sleep(RETRY_DELAY)
                continue
            return _build_fallback_prospect(analysis, f"Prospect error: {e}")

    return _build_fallback_prospect(analysis, "Unknown error")


# ─── Validation ───────────────────────────────────────────────────────

def _validate_cluster(data: Dict[str, Any]) -> Dict[str, Any]:
    cluster: Dict[str, Any] = {}
    cluster["market_cluster"] = str(data.get("market_cluster", "") or "").strip() or "unknown"

    for field in ["high_resonance_patterns", "low_resonance_patterns", "effective_hooks", "failed_hooks"]:
        raw = data.get(field, [])
        if isinstance(raw, list):
            cluster[field] = [str(i).strip() for i in raw if i and str(i).strip()]
        elif isinstance(raw, str) and raw.strip():
            cluster[field] = [raw.strip()]
        else:
            cluster[field] = []

    for field in ["belief_density", "tension_score"]:
        val = data.get(field, 0.5)
        try:
            cluster[field] = max(0.0, min(1.0, float(val)))
        except (ValueError, TypeError):
            cluster[field] = 0.5

    return cluster


def _validate_prospect(data: Dict[str, Any]) -> Dict[str, Any]:
    prospect: Dict[str, Any] = {}
    defaults = {
        "belief": "unknown", "identity": "unknown", "objection": "unknown",
        "resonance_pattern": "unknown", "narrative": "", "outreach_angle": "unknown",
        "market_cluster": "",
    }
    for field, default in defaults.items():
        val = data.get(field, "")
        prospect[field] = str(val).strip() if val and str(val).strip() else default

    conf = data.get("confidence", 0.5)
    try:
        prospect["confidence"] = max(0.0, min(1.0, float(conf)))
    except (ValueError, TypeError):
        prospect["confidence"] = 0.5

    return prospect


# ─── Parsing ──────────────────────────────────────────────────────────

def _parse_cluster_response(content: str) -> Dict[str, Any]:
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, TypeError):
        pass
    return _parse_cluster_text(content)


def _parse_cluster_text(text: str) -> Dict[str, Any]:
    result = {
        "market_cluster": "unknown",
        "high_resonance_patterns": [],
        "low_resonance_patterns": [],
        "effective_hooks": [],
        "failed_hooks": [],
        "belief_density": 0.5,
        "tension_score": 0.5,
    }
    lines = text.split("\n")
    collecting = None
    items = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        lower = stripped.lower()

        if collecting:
            if stripped in ("]", "}"):
                result[collecting] = items
                collecting = None
                items = []
                continue
            cleaned = re.sub(r"^[-\*\d\.\s]+", "", stripped).strip().strip('"\'')
            if cleaned and cleaned not in ("[]", "[ ]"):
                items.append(cleaned)
            continue

        for num_field in ["belief_density", "tension_score"]:
            if num_field in lower and (":" in stripped or "=" in stripped):
                sep = ":" if ":" in stripped else "="
                try:
                    result[num_field] = max(0.0, min(1.0, float(stripped.split(sep, 1)[1].strip())))
                except (ValueError, TypeError):
                    pass
                break
        else:
            field_map = {
                "market_cluster": "market_cluster",
                "high_resonance": "high_resonance_patterns",
                "low_resonance": "low_resonance_patterns",
                "effective_hook": "effective_hooks",
                "failed_hook": "failed_hooks",
            }
            for key, canonical in field_map.items():
                if key in lower:
                    if ":" in stripped:
                        after = stripped.split(":", 1)[1].strip()
                        if canonical == "market_cluster":
                            result[canonical] = after.strip('"\'') or "unknown"
                        else:
                            try:
                                parsed = json.loads(after)
                                if isinstance(parsed, list):
                                    result[canonical] = [str(s).strip() for s in parsed if s and str(s).strip()]
                                else:
                                    result[canonical] = [str(parsed)]
                            except (json.JSONDecodeError, TypeError):
                                if after and after not in ("[]", "[ ]"):
                                    result[canonical] = [after.strip('"\'')]
                                else:
                                    collecting = canonical
                                    items = []
                    break

    if collecting and items:
        result[collecting] = items

    return result


def _parse_prospect_response(content: str) -> Dict[str, Any]:
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, TypeError):
        pass
    return _parse_prospect_text(content)


def _parse_prospect_text(text: str) -> Dict[str, Any]:
    result = {
        "belief": "unknown", "identity": "unknown", "objection": "unknown",
        "resonance_pattern": "unknown", "narrative": "", "outreach_angle": "unknown",
        "market_cluster": "", "confidence": 0.5,
    }
    lines = text.split("\n")
    current_field = None

    aliases = {}
    for field in PROSPECT_FIELDS:
        aliases[field] = field
        aliases[field.replace("_", "")] = field
        aliases[field.replace("_", "-")] = field

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        lower = stripped.lower()

        if "confidence" in lower and (":" in stripped or "=" in stripped):
            sep = ":" if ":" in stripped else "="
            try:
                result["confidence"] = max(0.0, min(1.0, float(stripped.split(sep, 1)[1].strip())))
            except (ValueError, TypeError):
                pass
            current_field = None
            continue

        for alias, canonical in aliases.items():
            if canonical == "confidence":
                continue
            patterns = [f'"{alias}"', f"'{alias}'", f"{alias}:", f"{alias} :"]
            for pattern in patterns:
                if lower.startswith(pattern.lower()):
                    current_field = canonical
                    for sep in [": ", ":", '":"', '" ']:
                        if sep in stripped:
                            val = stripped.split(sep, 1)[1].strip().strip('"').strip("'")
                            if val:
                                result[canonical] = val
                                current_field = None
                            break
                    break
            if current_field:
                break

        if current_field and current_field in result:
            if result[current_field] in ("", "unknown"):
                result[current_field] = stripped
            else:
                result[current_field] += " " + stripped

    return result


# ─── Helpers ──────────────────────────────────────────────────────────

def _build_cluster_text(cluster: Dict[str, Any]) -> str:
    parts = [f"Market: {cluster.get('market_cluster', 'unknown')}"]
    for p in cluster.get("high_resonance_patterns", []):
        parts.append(f"High resonance: {p}")
    for p in cluster.get("effective_hooks", []):
        parts.append(f"Effective hook: {p}")
    for p in cluster.get("low_resonance_patterns", []):
        parts.append(f"Low resonance: {p}")
    for p in cluster.get("failed_hooks", []):
        parts.append(f"Failed hook: {p}")
    return " | ".join(parts)


# ─── Fallbacks ────────────────────────────────────────────────────────

def _build_fallback_cluster(analyses: List[Dict[str, Any]], error_reason: str) -> Dict[str, Any]:
    from collections import Counter

    games, objections, framings, identities, tensions, beliefs = [], [], [], [], [], []

    for a in analyses:
        if a.get("language_game") and a["language_game"] != "unknown":
            games.append(a["language_game"])
        if a.get("objection_type") and a["objection_type"] != "unknown":
            objections.append(a["objection_type"])
        if a.get("framing_pattern") and a["framing_pattern"] != "unknown":
            framings.append(a["framing_pattern"])
        if a.get("identity_marker") and a["identity_marker"] != "unknown":
            identities.append(a["identity_marker"])
        if a.get("tension") and a["tension"] != "unknown":
            tensions.append(a["tension"])
        if a.get("belief") and a["belief"] != "unknown":
            beliefs.append(a["belief"])

    def freq(items, min_count=1):
        counts = Counter(items)
        return list(dict.fromkeys(i for i, c in counts.items() if c >= min_count))

    return {
        "cluster_id": None,
        "market_cluster": "unknown",
        "high_resonance_patterns": freq(games + framings, 1)[:5] or ["unknown"],
        "low_resonance_patterns": [],
        "effective_hooks": freq(identities + tensions, 1)[:5] or ["unknown"],
        "failed_hooks": [],
        "belief_density": 0.3 if len(beliefs) < 2 else 0.6,
        "tension_score": 0.3 if len(tensions) < 2 else 0.6,
        "source_analysis_count": len(analyses),
        "cluster_fallback": True,
        "cluster_error": error_reason,
    }


def _build_fallback_prospect(analysis: Dict[str, Any], error_reason: str) -> Dict[str, Any]:
    belief = analysis.get("belief", "unknown") or "unknown"
    identity = analysis.get("identity_marker", "unknown") or "unknown"
    objection = analysis.get("objection_type", "unknown") or "unknown"
    tension = analysis.get("tension", "unknown") or "unknown"

    parts = []
    if belief != "unknown":
        parts.append(f"Addressing belief: {belief}")
    if tension != "unknown":
        parts.append(f"Core tension: {tension}")
    narrative = " | ".join(parts) if parts else "No narrative available — LLM fallback."

    signal_count = sum(1 for v in [belief, identity, objection, tension] if v and v != "unknown")
    confidence = min(1.0, signal_count * 0.2)

    return {
        "belief": belief,
        "identity": identity,
        "objection": objection,
        "resonance_pattern": "unknown",
        "narrative": narrative,
        "outreach_angle": "unknown",
        "market_cluster": "",
        "confidence": round(confidence, 2),
        "prospect_fallback": True,
        "prospect_error": error_reason,
    }
