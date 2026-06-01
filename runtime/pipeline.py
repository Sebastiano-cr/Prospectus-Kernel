"""
Pipeline — Orchestration connecting all three layers of the Language Games Engine.

full_discourse_analysis chains: ingest → language game → resonance → store
"""
import logging
import os
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


async def full_discourse_analysis(
    text: str,
    source: str = "other",
    context: str = "",
    litellm_url: str = "",
    api_key: str = "",
) -> Dict[str, Any]:
    """
    Full discourse analysis pipeline: ingest → language game → store.
    
    Chains all three layers of the Wittgensteinian Language Games Engine
    into a single observable pipeline. Each step is logged and its latency
    tracked.
    
    Args:
        text: Raw discourse text to analyze.
        source: Platform source (reddit, youtube, linkedin, etc.).
        context: Surrounding context.
        litellm_url: URL of the LiteLLM service.
        api_key: API key for the deepseek-chat model.
    
    Returns:
        Dict with 'fragment', 'analysis', 'success', and 'error' keys.
    """
    import time
    
    # Resolve config from env if not provided
    if not litellm_url:
        litellm_url = os.getenv("LITELLM_URL", "http://litellm:4000")
    if not api_key:
        api_key = os.getenv("DEEPSEEK_CHAT_API_KEY", "")
    
    result: Dict[str, Any] = {
        "fragment": None,
        "analysis": None,
        "success": False,
        "error": None,
        "latency_ms": {},
    }
    
    # Layer 1: Ingestion
    try:
        start = time.time()
        from agents.discourse_ingestor import ingest_discourse
        fragment = await ingest_discourse(text, source, context, litellm_url, api_key)
        result["fragment"] = fragment
        result["latency_ms"]["ingestion"] = round((time.time() - start) * 1000, 1)
    except Exception as e:
        logger.error(f"Pipeline ingestion failed: {e}")
        result["error"] = f"Ingestion failed: {str(e)}"
        return result
    
    # Layer 2: Language Game Analysis
    try:
        start = time.time()
        from agents.language_game import analyze_language_game
        analysis = await analyze_language_game(fragment, litellm_url, api_key)
        result["analysis"] = analysis
        result["latency_ms"]["language_game"] = round((time.time() - start) * 1000, 1)
    except Exception as e:
        logger.error(f"Pipeline language game analysis failed: {e}")
        result["error"] = f"Language game analysis failed: {str(e)}"
        result["success"] = False
        return result
    
    result["success"] = True
    result["total_latency_ms"] = sum(result["latency_ms"].values())
    
    logger.info(
        f"Pipeline complete: fragment_id={fragment.get('fragment_id', '?')}, "
        f"tension_score={analysis.get('tension_score', '?')}, "
        f"total_latency={result['total_latency_ms']}ms"
    )
    
    return result


async def full_analysis_with_resonance(
    fragments_texts: List[Dict[str, str]],
    market_cluster: str = "",
    litellm_url: str = "",
    api_key: str = "",
) -> Dict[str, Any]:
    """
    Extended pipeline: ingest multiple fragments → analyze → resonance → store.
    
    Args:
        fragments_texts: List of dicts with 'text', 'source', 'context' keys.
        market_cluster: Optional market vertical classification.
        litellm_url: URL of the LiteLLM service.
        api_key: API key for the deepseek-chat model.
    
    Returns:
        Dict with 'fragments', 'analyses', 'resonance', 'success', 'error' keys.
    """
    import time
    
    if not litellm_url:
        litellm_url = os.getenv("LITELLM_URL", "http://litellm:4000")
    if not api_key:
        api_key = os.getenv("DEEPSEEK_CHAT_API_KEY", "")
    
    result: Dict[str, Any] = {
        "fragments": [],
        "analyses": [],
        "resonance": None,
        "success": False,
        "error": None,
    }
    
    # Layer 1+2: Ingest and analyze each fragment
    from agents.discourse_ingestor import ingest_discourse
    from agents.language_game import batch_analyze
    
    for frag_input in fragments_texts:
        try:
            fragment = await ingest_discourse(
                frag_input.get("text", ""),
                frag_input.get("source", "other"),
                frag_input.get("context", ""),
                litellm_url,
                api_key,
            )
            result["fragments"].append(fragment)
        except Exception as e:
            logger.warning(f"Failed to ingest fragment: {e}")
    
    if not result["fragments"]:
        result["error"] = "All fragment ingestions failed"
        return result
    
    # Batch analyze
    try:
        analyses = await batch_analyze(result["fragments"], litellm_url, api_key)
        result["analyses"] = analyses
    except Exception as e:
        result["error"] = f"Batch analysis failed: {str(e)}"
        return result
    
    # Layer 3: Resonance
    if len(result["analyses"]) >= 2:
        try:
            from agents.resonance import analyze_resonance
            resonance = await analyze_resonance(
                result["analyses"], market_cluster, litellm_url, api_key
            )
            result["resonance"] = resonance
        except Exception as e:
            logger.warning(f"Resonance analysis failed: {e}")
    
    result["success"] = True
    return result
