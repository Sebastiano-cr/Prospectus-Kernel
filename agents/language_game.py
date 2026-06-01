"""
Language Games Engine — Layer 2 of the Wittgensteinian Language Games Engine.
Extracts operational semantic structures from discourse fragments.

This is the core Wittgensteinian layer. It interprets language by social use
and operational context, not by literal meaning. Every statement reveals
beliefs, fears, desires, identity markers, and the language game being played.
"""
import asyncio
import json
import logging
import re
from typing import Dict, Any, List, Optional
from . import runtime
from .discourse_templates import build_language_game_prompt
from .factory import ServiceFactory
from .ports.llm_client import LLMMessage, LLMError
from .metrics import kirin_language_game_analyzed_total

logger = logging.getLogger(__name__)

# Configuration
ANALYSIS_TIMEOUT = 90.0  # Longer than ingestion — deeper analysis
MAX_RETRIES = 2
RETRY_DELAY = 5.0

# Valid values for enumerated fields
VALID_OBJECTION_TYPES = [
    "price", "timing", "trust", "complexity", "authority", "need",
    "risk", "effort", "priority", "fit", "competence", "social_proof"
]
VALID_MARKET_STAGES = ["emerging", "growing", "saturated", "commoditized"]
VALID_FRAMING_PATTERNS = [
    "blame", "aspiration", "victimhood", "expertise", "denial",
    "pragmatism", "urgency", "fear_appeal", "social_proof", "innovation"
]
VALID_DISCOURSE_ROLES = [
    "critic", "evangelist", "skeptic", "educator", "buyer", "seller",
    "observer", "gatekeeper", "champion", "detractor"
]

# The 14 fields of a LanguageGameAnalysis
ANALYSIS_FIELDS = [
    "surface_problem", "hidden_problem", "belief", "fear", "hidden_desire",
    "objection_type", "identity_marker", "market_stage", "tension",
    "framing_pattern", "social_context", "discourse_role", "language_game",
    "possible_solutions",
]


# ─── Main Entry Point ───────────────────────────────────────────────────────

async def analyze_language_game(
    fragment: Dict[str, Any],
    litellm_url: str = None,
    api_key: str = None,
) -> Dict[str, Any]:
    """
    Analyze a DiscourseFragment using the Wittgensteinian language game framework.

    This is the core analysis function. It takes a normalized DiscourseFragment
    (output from the ingestion layer) and performs deep operational semantic
    analysis — extracting the belief-fear-desire triad, identity markers,
    objection mechanics, tension patterns, and the specific language game.

    Args:
        fragment: A DiscourseFragment dict (output from ingest_discourse).
            Must contain at least 'text', 'source', 'context', 'emotion', 'topic'.
        litellm_url: Deprecated -- kept for backward compatibility.
        api_key: Deprecated -- kept for backward compatibility.

    Returns:
        A dict containing all 14 LanguageGameAnalysis fields plus metadata.
    """
    text = fragment.get("text", "")
    source = fragment.get("source", "unknown")
    context = fragment.get("context", "")
    emotion = fragment.get("emotion", "neutral")
    topic = fragment.get("topic", "unknown")

    if not text or not text.strip():
        logger.warning("Empty text in fragment, building fallback analysis")
        return _build_fallback_analysis(fragment, "Empty discourse text")

    # Build prompt via discourse_templates
    llm = ServiceFactory.get_llm_client()
    prompt = build_language_game_prompt(text, source, context, emotion, topic)
    messages = [LLMMessage(role="user", content=prompt)]

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
            parsed = _parse_analysis_response(response.content)

            # Validate all fields
            analysis = _validate_analysis(parsed)

            # Calculate tension score
            analysis["tension_score"] = _calculate_tension_score(analysis)

            # Store in PostgreSQL
            fragment_id = fragment.get("fragment_id", "")
            if fragment_id:
                await _store_analysis(fragment_id, analysis)

            # Increment metrics
            kirin_language_game_analyzed_total.inc()

            return analysis

        except LLMError as e:
            if attempt < MAX_RETRIES:
                logger.warning(
                    f"LLM error on attempt {attempt + 1}: {e}, "
                    f"retrying in {RETRY_DELAY}s"
                )
                await asyncio.sleep(RETRY_DELAY)
                continue
            else:
                return _build_fallback_analysis(
                    fragment, f"Analysis error: {str(e)}"
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
                return _build_fallback_analysis(
                    fragment, f"Analysis error: {str(e)}"
                )

    # Should not reach here, but just in case
    return _build_fallback_analysis(fragment, "Unknown analysis error")


# ─── Batch Processing ───────────────────────────────────────────────────────

async def batch_analyze(
    fragments: List[Dict[str, Any]],
    litellm_url: str,
    api_key: str,
) -> List[Dict[str, Any]]:
    """
    Analyze multiple DiscourseFragments with controlled concurrency.

    Uses an asyncio.Semaphore to limit parallel LLM calls and avoid
    overwhelming the LiteLLM service.

    Args:
        fragments: List of DiscourseFragment dicts from the ingestion layer.
        litellm_url: URL of the LiteLLM service.
        api_key: API key for the deepseek-chat model.

    Returns:
        List of analysis result dicts, one per input fragment. Failed
        analyses return fallback results with error information.
    """
    semaphore = asyncio.Semaphore(limit=3)

    async def _analyze_with_semaphore(frag: Dict[str, Any]) -> Dict[str, Any]:
        async with semaphore:
            return await analyze_language_game(frag, litellm_url, api_key)

    tasks = [_analyze_with_semaphore(frag) for frag in fragments]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    output: List[Dict[str, Any]] = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(
                f"Batch analysis failed for fragment {i}: {result}"
            )
            output.append(
                _build_fallback_analysis(
                    fragments[i], f"Batch analysis exception: {str(result)}"
                )
            )
        else:
            output.append(result)

    return output


# ─── Validation ──────────────────────────────────────────────────────────────

def _validate_analysis(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and normalize a parsed analysis, filling defaults for missing fields.

    Ensures all 14 LanguageGameAnalysis fields exist with proper types.
    Validated enumerated fields against VALID_* constants. Fills defaults
    for missing string fields. Ensures possible_solutions is a list of strings.

    Args:
        data: Raw parsed analysis data from the LLM.

    Returns:
        Validated analysis dictionary with all required fields properly typed.
    """
    analysis: Dict[str, Any] = {}

    # String fields with "unknown" defaults
    string_defaults = {
        "surface_problem": "unknown",
        "hidden_problem": "unknown",
        "belief": "unknown",
        "fear": "unknown",
        "hidden_desire": "unknown",
        "identity_marker": "unknown",
        "tension": "unknown",
        "social_context": "unknown",
        "language_game": "unknown",
    }

    for field_name, default_val in string_defaults.items():
        value = data.get(field_name, "")
        if not value or not str(value).strip():
            analysis[field_name] = default_val
        else:
            analysis[field_name] = str(value).strip()

    # Validated enumerated fields
    analysis["objection_type"] = _validate_enum_field(
        str(data.get("objection_type", "") or ""),
        VALID_OBJECTION_TYPES,
    )
    analysis["market_stage"] = _validate_enum_field(
        str(data.get("market_stage", "") or ""),
        VALID_MARKET_STAGES,
    )
    analysis["framing_pattern"] = _validate_enum_field(
        str(data.get("framing_pattern", "") or ""),
        VALID_FRAMING_PATTERNS,
    )
    analysis["discourse_role"] = _validate_enum_field(
        str(data.get("discourse_role", "") or ""),
        VALID_DISCOURSE_ROLES,
    )

    # possible_solutions — must be a list of strings
    raw_solutions = data.get("possible_solutions", [])
    if isinstance(raw_solutions, list):
        solutions = [str(s).strip() for s in raw_solutions if s and str(s).strip()]
    elif isinstance(raw_solutions, str):
        # Handle case where LLM returned a single string instead of a list
        solutions = [raw_solutions.strip()] if raw_solutions.strip() else []
    else:
        solutions = []

    if not solutions:
        solutions = ["unknown"]

    analysis["possible_solutions"] = solutions

    # Final safety pass — ensure no field is empty
    for field_name in ANALYSIS_FIELDS:
        if field_name == "possible_solutions":
            continue
        if not analysis.get(field_name):
            analysis[field_name] = "unknown"

    return analysis


def _validate_enum_field(
    value: str,
    valid_values: List[str],
    default: str = "unknown",
) -> str:
    """
    Validate a value against a list of valid values.

    Performs case-insensitive matching after stripping whitespace.
    Returns the canonical lowercase value if found, otherwise returns default.

    Args:
        value: The raw string value to validate.
        valid_values: List of acceptable string values.
        default: Value to return if the input is invalid.

    Returns:
        The validated lowercase value, or default if not in valid_values.
    """
    if not value or not isinstance(value, str):
        return default

    normalized = value.strip().lower()
    if normalized in valid_values:
        return normalized

    # Try partial matching — check if the value is contained in any valid value
    for valid in valid_values:
        if valid in normalized or normalized in valid:
            return valid

    return default


# ─── Payload & Parsing ──────────────────────────────────────────────────────



def _parse_analysis_response(content: str) -> Dict[str, Any]:
    """
    Parse the LLM response into an analysis dictionary.

    Attempts JSON parsing first; falls back to heuristic text extraction
    when the response is not valid JSON.

    Args:
        content: Raw text content from the LLM response.

    Returns:
        Dictionary with the 14 LanguageGameAnalysis fields.
    """
    # Try JSON parse first
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, TypeError):
        pass

    # Fallback: heuristic text parsing
    return _parse_analysis_text(content)


def _parse_analysis_text(text: str) -> Dict[str, Any]:
    """
    Extract analysis fields from plain text using heuristics.

    When the LLM returns a non-JSON response, this function attempts to
    extract each of the 14 fields by scanning for labeled lines.

    Args:
        text: Plain text response from the LLM.

    Returns:
        Dictionary with all 14 analysis fields, using defaults for missing values.
    """
    result: Dict[str, Any] = {
        "surface_problem": "unknown",
        "hidden_problem": "unknown",
        "belief": "unknown",
        "fear": "unknown",
        "hidden_desire": "unknown",
        "objection_type": "unknown",
        "identity_marker": "unknown",
        "market_stage": "unknown",
        "tension": "unknown",
        "framing_pattern": "unknown",
        "social_context": "unknown",
        "discourse_role": "unknown",
        "language_game": "unknown",
        "possible_solutions": [],
    }

    # Map of field name variants to canonical field names
    field_aliases: Dict[str, str] = {}
    for field in ANALYSIS_FIELDS:
        field_aliases[field] = field
        # Also accept without underscores
        field_aliases[field.replace("_", "")] = field
        # Also accept hyphenated
        field_aliases[field.replace("_", "-")] = field

    lines = text.split("\n")
    current_field: Optional[str] = None
    in_solutions = False
    solutions_list: List[str] = []

    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue

        lower_line = line_stripped.lower()

        # Check for possible_solutions array start
        if "possible_solutions" in lower_line or "solutions" in lower_line:
            in_solutions = True
            current_field = None
            # Check if solutions are on the same line
            if ":" in line_stripped:
                after_colon = line_stripped.split(":", 1)[1].strip()
                # Try to parse as JSON array
                try:
                    solutions_list = json.loads(after_colon)
                    if isinstance(solutions_list, list):
                        in_solutions = False
                except (json.JSONDecodeError, TypeError):
                    # Extract quoted strings
                    quoted = re.findall(r'[\"\']([^\"\']+)[\"\']', after_colon)
                    if quoted:
                        solutions_list = quoted
                        in_solutions = False
                    elif after_colon and after_colon not in ("[]", "[ ]"):
                        solutions_list = [after_colon]
                        in_solutions = False
            continue

        # If we're inside the solutions array, collect items
        if in_solutions:
            if line_stripped in ("]", "}"):
                in_solutions = False
                continue
            # Strip list markers
            cleaned = re.sub(r'^[-\*\d\.\s]+', '', line_stripped).strip()
            cleaned = cleaned.strip('\"\'')
            if cleaned and cleaned not in ("[]", "[ ]"):
                solutions_list.append(cleaned)
            continue

        # Detect field labels — look for patterns like "field_name": "value" or field_name: value
        matched = False
        for alias, canonical in field_aliases.items():
            patterns = [
                f'"{alias}"',
                f"'{alias}'",
                f"{alias}:",
                f"{alias} :",
            ]
            for pattern in patterns:
                if lower_line.startswith(pattern.lower()):
                    current_field = canonical
                    matched = True
                    # Extract value after the separator
                    for sep in [": ", ":", "\":\"", "\": "]:
                        if sep in line_stripped:
                            value = line_stripped.split(sep, 1)[1].strip()
                            # Strip surrounding quotes
                            value = value.strip('"').strip("'")
                            if value and value not in ("[]", "{}", "[ ]"):
                                if current_field == "possible_solutions":
                                    try:
                                        parsed = json.loads(value)
                                        if isinstance(parsed, list):
                                            solutions_list = parsed
                                            in_solutions = False
                                        else:
                                            solutions_list = [str(parsed)]
                                    except (json.JSONDecodeError, TypeError):
                                        solutions_list = [value]
                                    in_solutions = False
                                else:
                                    result[current_field] = value
                                    current_field = None
                            break
                    break
            if matched:
                break

        # Append continuation text to current field
        if current_field and current_field in result and current_field != "possible_solutions":
            if result[current_field] == "unknown":
                result[current_field] = line_stripped
            else:
                result[current_field] += " " + line_stripped

    # Assign solutions
    if solutions_list:
        result["possible_solutions"] = [
            str(s).strip() for s in solutions_list if s and str(s).strip()
        ]

    return result


# ─── Fallback ────────────────────────────────────────────────────────────────

def _build_fallback_analysis(
    fragment: Dict[str, Any],
    error_reason: str,
) -> Dict[str, Any]:
    """
    Build a minimal analysis when the LLM call fails.

    Extracts whatever information is available from the original fragment
    and sets all analysis fields to "unknown" or sensible defaults.
    Preserves the fragment's emotion and topic as lightweight signals.

    Args:
        fragment: The original DiscourseFragment dictionary.
        error_reason: Description of the failure.

    Returns:
        A LanguageGameAnalysis-compatible dict with fallback values.
    """
    text = fragment.get("text", "")
    emotion = fragment.get("emotion", "unknown")
    topic = fragment.get("topic", "unknown")
    source = fragment.get("source", "unknown")

    # Try to extract a minimal surface_problem from the text
    surface_problem = "unknown"
    if text and text.strip():
        # Use the first sentence as surface_problem
        first_sentence = text.strip().split(".")[0].strip()
        if first_sentence:
            surface_problem = first_sentence[:200]  # Cap length

    analysis: Dict[str, Any] = {
        "surface_problem": surface_problem,
        "hidden_problem": "unknown",
        "belief": "unknown",
        "fear": "unknown",
        "hidden_desire": "unknown",
        "objection_type": "unknown",
        "identity_marker": "unknown",
        "market_stage": "unknown",
        "tension": "unknown",
        "framing_pattern": "unknown",
        "social_context": source if source != "unknown" else "unknown",
        "discourse_role": "unknown",
        "language_game": "unknown",
        "possible_solutions": ["unknown"],
        "tension_score": 0.0,
        "analysis_fallback": True,
        "analysis_error": error_reason,
        "fallback_emotion": emotion,
        "fallback_topic": topic,
    }

    return analysis


# ─── Storage ─────────────────────────────────────────────────────────────────

async def _store_analysis(fragment_id: str, analysis: Dict[str, Any]) -> None:
    """
    Store a language game analysis in PostgreSQL for long-term retention.

    Uses the fragment_id as the lead_id and stores with memory_type
    "language_game_analysis". Graceful failure — storage errors never
    propagate to the caller.

    Args:
        fragment_id: The DiscourseFragment identifier.
        analysis: The validated LanguageGameAnalysis dictionary.
    """
    try:
        postgres_mem = runtime.get_postgres_memory()
        if postgres_mem:
            await postgres_mem.store_lead_memory(
                fragment_id, "language_game_analysis", analysis
            )
    except Exception as e:
        # Log the error but do not fail the analysis because of storage issues
        logger.warning(
            f"Failed to store analysis in PostgreSQL for "
            f"fragment {fragment_id}: {e}"
        )


# ─── Tension Scoring ────────────────────────────────────────────────────────

def _calculate_tension_score(analysis: Dict[str, Any]) -> float:
    """
    Calculate a 0.0–1.0 tension score based on the analysis fields.

    The score is higher when:
      - Fear is strong and specific (not "unknown")
      - Desire conflicts with belief (both are populated and different)
      - Identity is under threat (identity_marker is populated)
      - The tension field describes a real contradiction
      - More fields are populated (stronger signal density)

    Uses a simple heuristic: count non-default fields and check for
    conflict signals. No external dependencies.

    Args:
        analysis: The validated LanguageGameAnalysis dictionary.

    Returns:
        A float between 0.0 and 1.0 representing the tension level.
    """
    score = 0.0

    # Base score: count populated string fields (out of 13 string fields)
    string_fields = [
        "surface_problem", "hidden_problem", "belief", "fear",
        "hidden_desire", "objection_type", "identity_marker",
        "market_stage", "tension", "framing_pattern",
        "social_context", "discourse_role", "language_game",
    ]
    populated = sum(
        1 for f in string_fields
        if analysis.get(f) and analysis.get(f) != "unknown"
    )
    score += (populated / len(string_fields)) * 0.3  # Up to 0.3 for signal density

    # Fear presence adds tension
    fear = analysis.get("fear", "unknown")
    if fear and fear != "unknown":
        score += 0.15

    # Hidden desire presence adds tension
    desire = analysis.get("hidden_desire", "unknown")
    if desire and desire != "unknown":
        score += 0.10

    # Belief-desire conflict: both present and different
    belief = analysis.get("belief", "unknown")
    if (belief and belief != "unknown"
            and desire and desire != "unknown"
            and belief.lower() != desire.lower()):
        score += 0.15

    # Identity marker presence — reveals a vulnerable self-concept
    identity = analysis.get("identity_marker", "unknown")
    if identity and identity != "unknown":
        score += 0.10

    # Tension field populated — explicit contradiction named
    tension = analysis.get("tension", "unknown")
    if tension and tension != "unknown":
        score += 0.10

    # Possible solutions present — suggests a problem worth solving
    solutions = analysis.get("possible_solutions", [])
    if isinstance(solutions, list) and solutions:
        real_solutions = [s for s in solutions if s and s != "unknown"]
        if real_solutions:
            score += 0.10

    return round(min(1.0, max(0.0, score)), 2)
