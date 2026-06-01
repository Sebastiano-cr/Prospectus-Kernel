"""
Prompt templates for the Wittgensteinian Language Games Engine.

These templates drive the analysis pipeline:
  1. Ingestion  — normalize raw discourse into DiscourseFragment
  2. Analysis   — deep Wittgensteinian semantic analysis (LanguageGameAnalysis)
  3. Resonance  — cross-fragment pattern detection (ResonanceCluster)
  4. Prospect   — outreach profile generation (ProspectProfile)

Wittgenstein's insight: meaning is use. Words don't carry fixed meaning —
they are tools deployed inside specific language games governed by social
context, identity, and unspoken rules. Every prompt in this module is
designed to extract those hidden layers.

All prompts request structured JSON output. The Portuguese instruction
"Responda APENAS com o JSON válido, sem texto adicional." is appended
to every prompt to enforce strict JSON-only responses, matching the
convention established in enricher.py and scorer.py.
"""

from typing import Any, Dict, List, Optional


# ── JSON-only instruction (Portuguese, matches enricher.py / scorer.py) ──
_JSON_ONLY_SUFFIX = "Responda APENAS com o JSON válido, sem texto adicional."


def build_ingestion_prompt(
    text: str,
    source: str,
    context: str = "",
) -> str:
    """Build the ingestion prompt that normalizes raw discourse into a DiscourseFragment.

    This is the entry point of the pipeline. It takes raw text from any
    platform and asks the LLM to normalize it, detect the surface emotion,
    classify the topic, and infer surrounding context. The key instruction
    is to interpret the text by its social use — what language game is
    being played — rather than taking it at face value.

    Args:
        text: The raw discourse text exactly as it appeared in the source.
        source: The platform or channel this fragment originated from
            (e.g. "reddit", "youtube", "linkedin", "telegram",
            "sales_call", "dm", "landing_page", "community").
        context: Optional surrounding context — parent comment, video title,
            conversation thread, etc. If empty, the LLM will attempt to
            infer context from the text itself.

    Returns:
        A formatted prompt string that requests a JSON object matching the
        DiscourseFragment schema.
    """
    context_block = (
        f"Surrounding context (if any):\n{context}"
        if context
        else "No surrounding context provided — infer it from the text."
    )

    prompt = f"""
You are an expert analyst of online market discourse. Your task is to
normalize a raw piece of discourse into a structured schema.

Analyze the following discourse fragment from {source}. Normalize it,
detect the surface emotion, classify the topic, and provide surrounding
context if not given. Interpret the text by its social use — what language
game is being played?

FRAGMENT TEXT:
{repr(text)}

SOURCE PLATFORM: {source}

{context_block}

---

Instructions:
1. Return the text exactly as provided (do not paraphrase or summarize).
2. Return the source platform as given.
3. If context was not provided, infer the most likely conversational
   context from the text and source. Leave empty only if truly
   impossible to infer.
4. Detect the SURFACE-LEVEL emotion (the overt affective signal).
   Examples: frustration, excitement, confusion, anger, hope, skepticism,
   relief, anxiety, pride, disappointment.
5. Classify the TOPIC into one concise category. Examples: pricing,
   onboarding, feature_request, competitor_comparison, hiring,
   content_creation, sales_process, tool_selection, market_fit,
   scaling, burnout.

Output a JSON object with exactly these fields:
{{
  "text": "<exact raw text>",
  "source": "<platform>",
  "context": "<inferred or provided context>",
  "emotion": "<surface emotion>",
  "topic": "<topic classification>"
}}

{_JSON_ONLY_SUFFIX}
"""

    return prompt.strip()


def build_language_game_prompt(
    text: str,
    source: str,
    context: str,
    emotion: str,
    topic: str,
) -> str:
    """Build the core Wittgensteinian language game analysis prompt.

    This is the heart of the engine. It takes a normalized DiscourseFragment
    and performs deep operational semantic analysis — extracting the
    belief-fear-desire triad, identity markers, objection mechanics,
    tension patterns, and the specific language game being played.

    Wittgenstein argued that words are tools, not labels. Their meaning
    emerges from the social game in which they are deployed. This prompt
    instructs the LLM to operate from that exact framework: do NOT
    interpret text literally. Interpret it by its social use and
    operational context.

    Args:
        text: The raw discourse text.
        source: The platform or channel origin.
        context: Surrounding context for the discourse.
        emotion: Surface-level emotion detected during ingestion.
        topic: Topic classification from the ingestion layer.

    Returns:
        A formatted prompt string that requests a JSON object matching the
        LanguageGameAnalysis schema.
    """
    prompt = f"""
You are a Wittgensteinian analyst of market discourse. Your task is NOT to
interpret text literally. You must interpret it by its SOCIAL USE and
OPERATIONAL CONTEXT. Words are tools deployed in language games. Every
statement reveals:
  (1) what the person believes,
  (2) what they fear,
  (3) what they secretly want,
  (4) who they believe themselves to be,
  (5) what game they are playing.

---

DISCOURSE FRAGMENT:
{repr(text)}

SOURCE: {source}
CONTEXT: {context}
SURFACE EMOTION: {emotion}
TOPIC: {topic}

---

EXAMPLE ANALYSES (to calibrate your output):

Example 1 — Input: "Nobody buys websites anymore"
  surface_problem: "perceived market saturation for web design"
  hidden_problem: "inability to differentiate commodity service"
  belief: "the web design market is oversaturated and commoditized"
  fear: "commercial rejection — investing time in proposals that never close"
  hidden_desire: "predictable acquisition — a pipeline that works without cold outreach"
  objection_type: "need"
  identity_marker: "technical freelancer insecure about sales"
  market_stage: "saturated"
  tension: "wants recurring revenue but believes the vehicle (websites) is dead"
  framing_pattern: "denial"
  social_context: "freelancer community forum"
  discourse_role: "skeptic"
  language_game: "innovation vs commodity"
  possible_solutions: ["pivot to productized service", "vertical specialization", "build a proprietary framework"]

Example 2 — Input: "Carousels are terrible because I need 50 pages to explain everything"
  surface_problem: "carousel format cannot hold enough content"
  hidden_problem: "compression anxiety — inability to distill value into concise messaging"
  belief: "thorough explanation equals persuasion"
  fear: "losing nuance — being misunderstood or seen as shallow"
  hidden_desire: "being recognized as a deep, thorough expert"
  objection_type: "complexity"
  identity_marker: "deep technical creator who values comprehensiveness"
  market_stage: "growing"
  tension: "needs attention economy formats but resents the compression they require"
  framing_pattern: "expertise"
  social_context: "content marketing discussion"
  discourse_role: "educator"
  language_game: "depth vs attention economy"
  possible_solutions: ["content chunking strategy", "series-based carousel design", "layered narrative with hook-depth structure"]

---

Instructions:
Analyze the discourse fragment above using the same depth and structure.
For each field, reason about the HIDDEN layer — what the person would
never say out loud but what their words betray.

Output a JSON object with exactly these fields:
{{
  "surface_problem": "<what they literally say is wrong>",
  "hidden_problem": "<the underlying operational issue>",
  "belief": "<mental model that makes their statement feel true>",
  "fear": "<negative outcome they are trying to avoid>",
  "hidden_desire": "<unspoken want beneath the objection>",
  "objection_type": "<price|timing|trust|complexity|authority|need|other>",
  "identity_marker": "<social/professional identity revealed>",
  "market_stage": "<emerging|growing|saturated|commoditized>",
  "tension": "<contradiction between what they want and what they fear>",
  "framing_pattern": "<blame|aspiration|victimhood|expertise|denial|pragmatism|other>",
  "social_context": "<where this language game is being played>",
  "discourse_role": "<critic|evangelist|skeptic|educator|buyer|seller>",
  "language_game": "<name of the Wittgensteinian language game>",
  "possible_solutions": ["<solution 1>", "<solution 2>", "<solution 3>"]
}}

{_JSON_ONLY_SUFFIX}
"""

    return prompt.strip()


def build_resonance_prompt(
    analyses: List[Dict[str, Any]],
    market_cluster: str = "",
) -> str:
    """Build the resonance analysis prompt that identifies patterns across fragments.

    Takes multiple LanguageGameAnalysis results and asks the LLM to
    synthesize them into a ResonanceCluster — identifying what resonates,
    what falls flat, and what hooks work for this market segment.

    Args:
        analyses: A list of LanguageGameAnalysis dictionaries (or their
            text representations). Each dict should contain fields like
            surface_problem, hidden_problem, belief, fear, hidden_desire,
            objection_type, identity_marker, language_game, etc.
        market_cluster: Optional market vertical or segment classification
            (e.g. "developer_tools", "agencies", "legal_services").
            If provided, the LLM will use it as a classification anchor.

    Returns:
        A formatted prompt string that requests a JSON object matching the
        ResonanceCluster schema.
    """
    import json as _json

    analyses_text = _json.dumps(analyses, indent=2, ensure_ascii=False)

    cluster_block = (
        f"MARKET CLUSTER (if known): {market_cluster}"
        if market_cluster
        else "MARKET CLUSTER: not yet classified — determine the most likely segment."
    )

    prompt = f"""
You are a market resonance analyst. You are given a set of Wittgensteinian
language game analyses from the same market segment. Your task is to
identify the structural patterns that connect them — what resonates,
what falls flat, and what hooks work.

---

LANGUAGE GAME ANALYSES:
{analyses_text}

{cluster_block}

---

Instructions:
1. Identify HIGH-RESONANCE patterns — phrases, framings, tensions, or
   belief structures that appear across multiple analyses and would
   generate strong market response.
2. Identify LOW-RESONANCE patterns — approaches that miss the mark for
   this audience, framings that would fall flat or backfire.
3. Extract EFFECTIVE HOOKS — specific opening structures, angles, or
   framings that would grab attention for this cluster.
4. Identify FAILED HOOKS — hook structures that should be avoided.
5. Classify the MARKET CLUSTER if not already provided.
6. Rate BELIEF DENSITY from 0.0 to 1.0 — how concentrated and coherent
   are the belief signals across these analyses? (1.0 = dense, coherent
   belief system; 0.0 = scattered, contradictory)
7. Rate TENSION SCORE from 0.0 to 1.0 — how intense is the core
   tension driving action in this cluster? (1.0 = acute, painful,
   driving immediate action; 0.0 = mild, no urgency)

Output a JSON object with exactly these fields:
{{
  "market_cluster": "<market segment classification>",
  "high_resonance_patterns": ["<pattern 1>", "<pattern 2>", "<pattern 3>"],
  "low_resonance_patterns": ["<pattern 1>", "<pattern 2>"],
  "effective_hooks": ["<hook 1>", "<hook 2>", "<hook 3>"],
  "failed_hooks": ["<hook 1>", "<hook 2>"],
  "belief_density": 0.75,
  "tension_score": 0.60
}}

{_JSON_ONLY_SUFFIX}
"""

    return prompt.strip()


def build_prospect_prompt(
    analysis: Dict[str, Any],
    resonance: Optional[Dict[str, Any]] = None,
) -> str:
    """Build the prospect profile generation prompt.

    Takes a single LanguageGameAnalysis and an optional ResonanceCluster
    to craft an actionable outreach strategy. The output is a
    ProspectProfile with a concrete narrative, strategic angle, and
    confidence score.

    The prompt instructs the LLM to play the RIGHT game with the RIGHT
    frame — speak to the prospect's identity, address their fear, and
    fulfill their hidden desire.

    Args:
        analysis: A LanguageGameAnalysis dictionary containing the
            deep semantic analysis of the target's discourse.
        resonance: Optional ResonanceCluster dictionary with cross-
            fragment patterns. If provided, the LLM will use it to
            select the best resonance pattern and calibrate confidence.

    Returns:
        A formatted prompt string that requests a JSON object matching the
        ProspectProfile schema.
    """
    import json as _json

    analysis_text = _json.dumps(analysis, indent=2, ensure_ascii=False)

    if resonance:
        resonance_text = _json.dumps(resonance, indent=2, ensure_ascii=False)
        resonance_block = f"""
RESONANCE CLUSTER (use to select the best pattern and calibrate confidence):
{resonance_text}
"""
    else:
        resonance_block = ""

    prompt = f"""
You are a Wittgensteinian outreach strategist. Using the language game
analysis below, craft an outreach strategy that plays the RIGHT game
with the RIGHT frame. Do NOT be generic. Speak to their identity,
address their fear, fulfill their hidden desire.

---

LANGUAGE GAME ANALYSIS:
{analysis_text}

{resonance_block}
---

Instructions:
1. Identify the CORE BELIEF to address. This is the mental model you
   need to either validate or gently challenge.
2. Identify the IDENTITY MARKER to resonate with. Speak to who they
   believe themselves to be — not who you want them to be.
3. Identify the PRIMARY OBJECTION to overcome. Address this directly
   or reframe it entirely within a different language game.
4. Select the best RESONANCE PATTERN from the cluster (or derive one
   from the analysis) to use as the structural template.
5. Write the NARRATIVE — the actual outreach text. This must be
   specific to this person's language game. No templates, no
   copy-paste. Every word should reflect understanding of their
   hidden problem.
6. Define the OUTREACH ANGLE — the high-level strategic framing
   (e.g. 'lead with social proof for skeptic identity', 'validate
   fear then redirect to aspiration').
7. Assign a CONFIDENCE score from 0.0 to 1.0 based on how strong
   and coherent the signals are. Low data = low confidence.

Output a JSON object with exactly these fields:
{{
  "belief": "<core belief to address>",
  "identity": "<identity marker to resonate with>",
  "objection": "<primary objection to overcome>",
  "resonance_pattern": "<selected resonance pattern>",
  "narrative": "<the actual outreach text — specific, not generic>",
  "outreach_angle": "<strategic framing decision>",
  "market_cluster": "<market segment if identifiable, else empty string>",
  "confidence": 0.70
}}

{_JSON_ONLY_SUFFIX}
"""

    return prompt.strip()
