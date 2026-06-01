"""
Tools — Cline-compatible tool functions for the Language Games Engine.

Each function wraps the corresponding agents module function, resolving
configuration from environment variables and handling errors gracefully.
These are the callable entry points exposed to the Cline SDK tool layer.
"""
import logging
import os
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool 1: discourse_extract
# ---------------------------------------------------------------------------

async def discourse_extract(
    text: str,
    source: str = "other",
    context: str = "",
) -> Dict[str, Any]:
    """
    Full discourse extraction pipeline: ingest → language game analysis.

    Takes raw discourse text, normalizes it into a structured DiscourseFragment
    via the ingestion layer, then performs deep operational semantic analysis
    through the Wittgensteinian language game framework.

    Wraps ``agents.discourse_ingestor.ingest_discourse`` and
    ``agents.language_game.analyze_language_game``.

    Args:
        text: Raw discourse text to extract and analyse.
        source: Platform source identifier (reddit, youtube, linkedin, etc.).
        context: Surrounding context that may influence interpretation.

    Returns:
        Dict with 'fragment' and 'analysis' keys on success,
        or 'error' key on failure.
    """
    litellm_url = os.getenv("LITELLM_URL", "http://litellm:4000")
    api_key = os.getenv("DEEPSEEK_CHAT_API_KEY", "")

    try:
        from agents.discourse_ingestor import ingest_discourse
        from agents.language_game import analyze_language_game

        # Layer 1: Ingestion
        fragment = await ingest_discourse(text, source, context, litellm_url, api_key)

        # Layer 2: Language Game Analysis
        analysis = await analyze_language_game(fragment, litellm_url, api_key)

        return {
            "fragment": fragment,
            "analysis": analysis,
            "success": True,
        }
    except Exception as e:
        logger.error(f"discourse_extract failed: {e}")
        return {
            "fragment": None,
            "analysis": None,
            "success": False,
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# Tool 2: resonance_lookup
# ---------------------------------------------------------------------------

async def resonance_lookup(
    query: str,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """
    Search for semantic resonance clusters in Qdrant / PostgreSQL.

    Finds previously stored ResonanceCluster records that match a free-text
    query describing a market pattern.  Tries Qdrant first (payload filtering),
    falling back to PostgreSQL text search.

    Wraps ``agents.resonance.lookup_resonance``.

    Args:
        query: Free-text description of the resonance pattern to search for.
        limit: Maximum number of results to return (default 5).

    Returns:
        List of matching ResonanceCluster dicts, most relevant first.
        Returns an empty list on failure.
    """
    litellm_url = os.getenv("LITELLM_URL", "http://litellm:4000")
    api_key = os.getenv("DEEPSEEK_CHAT_API_KEY", "")

    try:
        from agents.resonance import lookup_resonance

        results = await lookup_resonance(query, litellm_url, api_key, limit)
        return results
    except Exception as e:
        logger.error(f"resonance_lookup failed: {e}")
        return []


# ---------------------------------------------------------------------------
# Tool 3: prospect_generator
# ---------------------------------------------------------------------------

async def prospect_generator(
    analysis: Dict[str, Any],
    resonance: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Generate an outreach prospect profile from a language game analysis.

    Combines the belief-fear-desire triad, identity markers, objection
    mechanics, and optional resonance patterns to craft an actionable
    outreach angle.

    Wraps ``agents.resonance.generate_prospect``.

    Args:
        analysis: A LanguageGameAnalysis dict from the language game layer.
        resonance: Optional ResonanceCluster dict from the resonance layer.

    Returns:
        ProspectProfile dict on success, or error dict on failure.
    """
    litellm_url = os.getenv("LITELLM_URL", "http://litellm:4000")
    api_key = os.getenv("DEEPSEEK_CHAT_API_KEY", "")

    try:
        from agents.resonance import generate_prospect

        prospect = await generate_prospect(analysis, resonance, litellm_url, api_key)
        return prospect
    except Exception as e:
        logger.error(f"prospect_generator failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# Tool 4: memory_store
# ---------------------------------------------------------------------------

async def memory_store(
    key: str,
    data: Dict[str, Any],
    memory_type: str = "general",
) -> bool:
    """
    Persist operational semantic memory to PostgreSQL.

    Stores arbitrary structured data in the lead_memory table using the
    provided *key* as the ``lead_id`` and *memory_type* to categorise the
    record.

    Wraps ``agents.runtime.get_postgres_memory().store_lead_memory()``.

    Args:
        key: The lead / entity identifier used as primary key.\n        data: JSON-serialisable dictionary of data to persist.
        memory_type: Category tag (general, discourse_fragment,
            language_game_analysis, resonance_cluster, etc.).

    Returns:
        True on successful storage, False on failure.
    """
    try:
        from agents.runtime import get_postgres_memory

        postgres_mem = get_postgres_memory()
        if not postgres_mem:
            logger.error("memory_store: PostgreSQL memory manager not initialised")
            return False

        success = await postgres_mem.store_lead_memory(key, memory_type, data)
        return success
    except Exception as e:
        logger.error(f"memory_store failed: {e}")
        return False
