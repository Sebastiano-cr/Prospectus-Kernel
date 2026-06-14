"""
Analyzer — Layer 1 (Ingestion) + Layer 2 (Language Game) of the analysis pipeline.

Ingests raw discourse, normalizes into DiscourseFragment via LLM,
then performs Wittgensteinian semantic analysis (LanguageGameAnalysis).

Accepts an optional ChromaStore for persistence. When not provided,
LLM analysis still works but results are not persisted.
"""
import asyncio
import json
import logging
import re
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from src.analysis.templates import (
    build_ingestion_prompt,
    build_language_game_prompt,
)
from agents.factory import ServiceFactory
from agents.ports.llm_client import LLMMessage, LLMError
from agents.metrics import (
    kirin_discourse_ingested_total,
    kirin_language_game_analyzed_total,
)
from src.store import ChromaStore
from src.locale import get_locale, LocalePort

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────

VALID_SOURCES = [
    "reddit", "youtube", "linkedin", "telegram",
    "sales_call", "dm", "landing_page", "community", "other",
]

VALID_OBJECTION_TYPES = [
    "price", "timing", "trust", "complexity", "authority", "need",
    "risk", "effort", "priority", "fit", "competence", "social_proof",
]

VALID_MARKET_STAGES = ["emerging", "growing", "saturated", "commoditized"]

VALID_FRAMING_PATTERNS = [
    "blame", "aspiration", "victimhood", "expertise", "denial",
    "pragmatism", "urgency", "fear_appeal", "social_proof", "innovation",
]

VALID_DISCOURSE_ROLES = [
    "critic", "evangelist", "skeptic", "educator", "buyer", "seller",
    "observer", "gatekeeper", "champion", "detractor",
]

ANALYSIS_FIELDS = [
    "surface_problem", "hidden_problem", "belief", "fear", "hidden_desire",
    "objection_type", "identity_marker", "market_stage", "tension",
    "framing_pattern", "social_context", "discourse_role", "language_game",
    "possible_solutions",
]

INGESTION_TIMEOUT = 60.0
ANALYSIS_TIMEOUT = 90.0
MAX_RETRIES = 2
RETRY_DELAY = 5.0


# ═══════════════════════════════════════════════════════════════════════
# Layer 1: Discourse Ingestion
# ═══════════════════════════════════════════════════════════════════════

async def ingest_discourse(
    text: str,
    source: str,
    context: str = "",
    litellm_url: str = None,
    api_key: str = None,
    store: Optional[ChromaStore] = None,
    locale: Optional["LocalePort"] = None,
) -> Dict[str, Any]:
    if not text or not text.strip():
        raise ValueError("Discourse text must not be empty")

    source = _validate_source(source)
    if store is None:
        from agents import runtime
        store = runtime.get_store()

    if store:
        if await store.check_duplicate(_fragment_id(text, source)):
            logger.info(f"Duplicate fragment (source={source}), returning cached")
            cached = await store.get_dedup(_fragment_id(text, source))
            if cached is not None:
                return cached

    llm = ServiceFactory.get_llm_client()
    prompt = build_ingestion_prompt(text, source, context)
    messages = [LLMMessage(role="user", content=prompt)]
    timestamp = datetime.now(timezone.utc).isoformat()

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = await llm.complete(
                messages=messages,
                model="deepseek-chat",
                temperature=0.3,
                max_tokens=1000,
                response_format="json"
            )

            parsed = _parse_fragment_response(response.content)
            fragment = _validate_fragment(parsed, source, text)
            fragment["fragment_id"] = _fragment_id(text, source)
            fragment["timestamp"] = timestamp
            fragment["ingested_at"] = datetime.now(timezone.utc).isoformat()

            if locale is None:
                locale = get_locale("pt-BR")
            from agents.skeptic import check_agent_output as _check_output
            _report = _check_output("discourse_ingestor", fragment, {
                "text": text,
                "source": source,
            }, locale)
            if not _report.passed:
                fragment["skeptic_report"] = _report.to_dict()

            if store:
                await store.store_lead_memory(
                    fragment["fragment_id"], "discourse_fragment", fragment
                )
                await store.store_dedup(_fragment_id(text, source), fragment)

            kirin_discourse_ingested_total.labels(source=source).inc()
            return fragment

        except LLMError as e:
            if attempt < MAX_RETRIES:
                logger.warning(f"LLM error attempt {attempt + 1}: {e}, retrying...")
                await asyncio.sleep(RETRY_DELAY)
                continue
            return _build_fallback_fragment(text, source, context, timestamp, str(e))
        except Exception as e:
            if attempt < MAX_RETRIES:
                logger.warning(f"Error attempt {attempt + 1}: {e}, retrying...")
                await asyncio.sleep(RETRY_DELAY)
                continue
            return _build_fallback_fragment(text, source, context, timestamp, str(e))

    return _build_fallback_fragment(text, source, context, timestamp, "Unknown error")


def _fragment_id(text: str, source: str) -> str:
    return hashlib.sha256(f"{text}{source}".encode()).hexdigest()[:16]


def _validate_source(source: str) -> str:
    if not source or not isinstance(source, str):
        return "other"
    normalized = source.strip().lower()
    return normalized if normalized in VALID_SOURCES else "other"


def _parse_fragment_response(content: str) -> Dict[str, Any]:
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, TypeError):
        pass
    return _parse_fragment_text(content)


def _parse_fragment_text(text: str) -> Dict[str, Any]:
    result = {"text": "", "source": "", "context": "", "emotion": "neutral", "topic": "other"}
    lines = text.split("\n")
    current_field = None
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        lower = stripped.lower()
        for field in ["text", "source", "context", "emotion", "topic"]:
            if lower.startswith(f'"{field}"') or lower.startswith(f"{field}:"):
                current_field = field
                if ":" in stripped:
                    val = stripped.split(":", 1)[1].strip().strip('"').strip("'")
                    if val:
                        result[field] = val
                        current_field = None
                break
        else:
            if current_field and current_field in result:
                if result[current_field]:
                    result[current_field] += " " + stripped
                else:
                    result[current_field] = stripped
    return result


def _validate_fragment(data: Dict[str, Any], source: str, text: str) -> Dict[str, Any]:
    fragment = {
        "text": str(data.get("text", text) or text),
        "source": _validate_source(str(data.get("source", source) or source)),
        "context": str(data.get("context", "") or ""),
        "emotion": str(data.get("emotion", "neutral") or "neutral").lower().strip(),
        "topic": str(data.get("topic", "other") or "other").lower().strip(),
    }
    if not fragment["text"].strip():
        fragment["text"] = text
    if fragment["source"] not in VALID_SOURCES:
        fragment["source"] = "other"
    return fragment


def _build_fallback_fragment(
    text: str, source: str, context: str, timestamp: str, error_reason: str
) -> Dict[str, Any]:
    return {
        "fragment_id": _fragment_id(text, source),
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


# ═══════════════════════════════════════════════════════════════════════
# Layer 2: Language Game Analysis
# ═══════════════════════════════════════════════════════════════════════

async def analyze_language_game(
    fragment: Dict[str, Any],
    litellm_url: str = None,
    api_key: str = None,
    store: Optional[ChromaStore] = None,
    locale: Optional["LocalePort"] = None,
) -> Dict[str, Any]:
    text = fragment.get("text", "")
    source = fragment.get("source", "unknown")
    context = fragment.get("context", "")
    emotion = fragment.get("emotion", "neutral")
    topic = fragment.get("topic", "unknown")

    if not text or not text.strip():
        logger.warning("Empty text, building fallback analysis")
        return _build_fallback_analysis(fragment, "Empty discourse text")

    if store is None:
        from agents import runtime
        store = runtime.get_store()
    llm = ServiceFactory.get_llm_client()
    prompt = build_language_game_prompt(text, source, context, emotion, topic)
    messages = [LLMMessage(role="user", content=prompt)]

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = await llm.complete(
                messages=messages,
                model="deepseek-chat",
                temperature=0.3,
                max_tokens=1000,
                response_format="json",
            )

            parsed = _parse_analysis_response(response.content)
            analysis = _validate_analysis(parsed)
            analysis["tension_score"] = _calculate_tension_score(analysis)

            if locale is None:
                locale = get_locale("pt-BR")
            from agents.skeptic import check_agent_output as _check_output
            _report = _check_output("language_game", analysis, {
                "fragment": fragment,
            }, locale)
            if not _report.passed:
                analysis["skeptic_report"] = _report.to_dict()

            fragment_id = fragment.get("fragment_id", "")
            if fragment_id and store:
                await store.store_lead_memory(
                    fragment_id, "language_game_analysis", analysis
                )

            kirin_language_game_analyzed_total.inc()
            return analysis

        except LLMError as e:
            if attempt < MAX_RETRIES:
                logger.warning(f"LLM error attempt {attempt + 1}: {e}, retrying...")
                await asyncio.sleep(RETRY_DELAY)
                continue
            return _build_fallback_analysis(fragment, f"Analysis error: {e}")
        except Exception as e:
            if attempt < MAX_RETRIES:
                logger.warning(f"Error attempt {attempt + 1}: {e}, retrying...")
                await asyncio.sleep(RETRY_DELAY)
                continue
            return _build_fallback_analysis(fragment, f"Analysis error: {e}")

    return _build_fallback_analysis(fragment, "Unknown analysis error")


async def batch_analyze(
    fragments: List[Dict[str, Any]],
    litellm_url: str,
    api_key: str,
    store: Optional[ChromaStore] = None,
) -> List[Dict[str, Any]]:
    semaphore = asyncio.Semaphore(limit=3)

    async def _analyze_one(frag: Dict[str, Any]) -> Dict[str, Any]:
        async with semaphore:
            return await analyze_language_game(frag, litellm_url, api_key, store)

    tasks = [_analyze_one(frag) for frag in fragments]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    output: List[Dict[str, Any]] = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Batch analysis failed for fragment {i}: {result}")
            output.append(_build_fallback_analysis(fragments[i], f"Batch exception: {result}"))
        else:
            output.append(result)
    return output


# ─── Validation ───────────────────────────────────────────────────────

def _validate_analysis(data: Dict[str, Any]) -> Dict[str, Any]:
    analysis: Dict[str, Any] = {}

    string_defaults = {
        "surface_problem": "unknown", "hidden_problem": "unknown",
        "belief": "unknown", "fear": "unknown", "hidden_desire": "unknown",
        "identity_marker": "unknown", "tension": "unknown",
        "social_context": "unknown", "language_game": "unknown",
    }
    for field, default in string_defaults.items():
        val = data.get(field, "")
        analysis[field] = default if not val or not str(val).strip() else str(val).strip()

    analysis["objection_type"] = _validate_enum(str(data.get("objection_type", "") or ""), VALID_OBJECTION_TYPES)
    analysis["market_stage"] = _validate_enum(str(data.get("market_stage", "") or ""), VALID_MARKET_STAGES)
    analysis["framing_pattern"] = _validate_enum(str(data.get("framing_pattern", "") or ""), VALID_FRAMING_PATTERNS)
    analysis["discourse_role"] = _validate_enum(str(data.get("discourse_role", "") or ""), VALID_DISCOURSE_ROLES)

    raw_solutions = data.get("possible_solutions", [])
    if isinstance(raw_solutions, list):
        solutions = [str(s).strip() for s in raw_solutions if s and str(s).strip()]
    elif isinstance(raw_solutions, str):
        solutions = [raw_solutions.strip()] if raw_solutions.strip() else []
    else:
        solutions = []
    analysis["possible_solutions"] = solutions or ["unknown"]

    for field in ANALYSIS_FIELDS:
        if field != "possible_solutions" and not analysis.get(field):
            analysis[field] = "unknown"

    return analysis


def _validate_enum(value: str, valid: List[str], default: str = "unknown") -> str:
    if not value or not isinstance(value, str):
        return default
    normalized = value.strip().lower()
    if normalized in valid:
        return normalized
    for v in valid:
        if v in normalized or normalized in v:
            return v
    return default


# ─── Parsing ──────────────────────────────────────────────────────────

def _parse_analysis_response(content: str) -> Dict[str, Any]:
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, TypeError):
        pass
    return _parse_analysis_text(content)


def _parse_analysis_text(text: str) -> Dict[str, Any]:
    result = {f: "unknown" for f in ANALYSIS_FIELDS if f != "possible_solutions"}
    result["possible_solutions"] = []

    aliases = {}
    for field in ANALYSIS_FIELDS:
        aliases[field] = field
        aliases[field.replace("_", "")] = field
        aliases[field.replace("_", "-")] = field

    lines = text.split("\n")
    current_field = None
    in_solutions = False
    solutions = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        lower = stripped.lower()

        if "possible_solutions" in lower or "solutions" in lower:
            in_solutions = True
            current_field = None
            if ":" in stripped:
                after = stripped.split(":", 1)[1].strip()
                try:
                    parsed = json.loads(after)
                    if isinstance(parsed, list):
                        solutions = parsed
                        in_solutions = False
                except (json.JSONDecodeError, TypeError):
                    quoted = re.findall(r'[\"\']([^\"\']+)[\"\']', after)
                    if quoted:
                        solutions = quoted
                        in_solutions = False
                    elif after and after not in ("[]", "[ ]"):
                        solutions = [after]
                        in_solutions = False
            continue

        if in_solutions:
            if stripped in ("]", "}"):
                in_solutions = False
                continue
            cleaned = re.sub(r"^[-\*\d\.\s]+", "", stripped).strip().strip('"\'')
            if cleaned and cleaned not in ("[]", "[ ]"):
                solutions.append(cleaned)
            continue

        for alias, canonical in aliases.items():
            patterns = [f'"{alias}"', f"'{alias}'", f"{alias}:", f"{alias} :"]
            for pattern in patterns:
                if lower.startswith(pattern.lower()):
                    current_field = canonical
                    for sep in [": ", ":", '":"', '" ']:
                        if sep in stripped:
                            val = stripped.split(sep, 1)[1].strip().strip('"').strip("'")
                            if val and val not in ("[]", "{}", "[ ]"):
                                if canonical == "possible_solutions":
                                    try:
                                        parsed = json.loads(val)
                                        if isinstance(parsed, list):
                                            solutions = parsed
                                            in_solutions = False
                                    except (json.JSONDecodeError, TypeError):
                                        solutions = [val]
                                    in_solutions = False
                                else:
                                    result[canonical] = val
                                    current_field = None
                            break
                    break
            if current_field:
                break

        if current_field and current_field in result and current_field != "possible_solutions":
            if result.get(current_field) == "unknown":
                result[current_field] = stripped
            else:
                result[current_field] += " " + stripped

    if solutions:
        result["possible_solutions"] = [str(s).strip() for s in solutions if s and str(s).strip()]

    return result


# ─── Fallback ─────────────────────────────────────────────────────────

def _build_fallback_analysis(fragment: Dict[str, Any], error_reason: str) -> Dict[str, Any]:
    text = fragment.get("text", "")
    emotion = fragment.get("emotion", "unknown")
    topic = fragment.get("topic", "unknown")
    source = fragment.get("source", "unknown")

    surface = "unknown"
    if text and text.strip():
        first = text.strip().split(".")[0].strip()
        if first:
            surface = first[:200]

    return {
        "surface_problem": surface, "hidden_problem": "unknown",
        "belief": "unknown", "fear": "unknown", "hidden_desire": "unknown",
        "objection_type": "unknown", "identity_marker": "unknown",
        "market_stage": "unknown", "tension": "unknown",
        "framing_pattern": "unknown", "social_context": source if source != "unknown" else "unknown",
        "discourse_role": "unknown", "language_game": "unknown",
        "possible_solutions": ["unknown"], "tension_score": 0.0,
        "analysis_fallback": True, "analysis_error": error_reason,
        "fallback_emotion": emotion, "fallback_topic": topic,
    }


# ─── Tension Score ────────────────────────────────────────────────────

def _calculate_tension_score(analysis: Dict[str, Any]) -> float:
    score = 0.0

    string_fields = [
        "surface_problem", "hidden_problem", "belief", "fear",
        "hidden_desire", "objection_type", "identity_marker",
        "market_stage", "tension", "framing_pattern",
        "social_context", "discourse_role", "language_game",
    ]
    populated = sum(1 for f in string_fields if analysis.get(f) and analysis.get(f) != "unknown")
    score += (populated / len(string_fields)) * 0.3

    fear = analysis.get("fear", "unknown")
    if fear and fear != "unknown":
        score += 0.15

    desire = analysis.get("hidden_desire", "unknown")
    if desire and desire != "unknown":
        score += 0.10

    belief = analysis.get("belief", "unknown")
    if (belief and belief != "unknown" and desire and desire != "unknown"
            and belief.lower() != desire.lower()):
        score += 0.15

    identity = analysis.get("identity_marker", "unknown")
    if identity and identity != "unknown":
        score += 0.10

    tension = analysis.get("tension", "unknown")
    if tension and tension != "unknown":
        score += 0.10

    solutions = analysis.get("possible_solutions", [])
    if isinstance(solutions, list) and solutions:
        real = [s for s in solutions if s and s != "unknown"]
        if real:
            score += 0.10

    return round(min(1.0, max(0.0, score)), 2)
