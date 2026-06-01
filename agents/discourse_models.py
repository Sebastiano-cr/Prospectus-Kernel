"""
Data models for the Wittgensteinian Language Games Engine.

These models represent the core schema for discourse ingestion, semantic analysis,
resonance clustering, and prospect profiling. The analysis pipeline normalizes
raw discourse from any source into a DiscourseFragment, applies a deep
Wittgensteinian analysis (LanguageGameAnalysis), clusters similar patterns into
ResonanceClusters, and ultimately generates ProspectProfiles for outreach.

Wittgenstein's insight: meaning is use. Words don't carry fixed meaning —
they are tools deployed inside specific language games governed by social context,
identity, and unspoken rules. This module models those games.
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class DiscourseFragment:
    """Normalized discourse from any source.

    Represents a single piece of ingested text that has been stripped of
    platform-specific formatting and normalized into a uniform schema.
    Every piece of discourse — a Reddit comment, a YouTube transcript line,
    a sales call transcript segment — becomes a DiscourseFragment before
    it enters the analysis pipeline.

    Attributes:
        text: The raw, unmodified text exactly as it appeared in the source.
        source: The platform or channel this fragment originated from.
            One of: reddit, youtube, linkedin, telegram, sales_call, dm,
            landing_page, community, other.
        context: Surrounding context where this was said — parent comment,
            video title, conversation thread, etc. Provides the social
            frame that changes how the text is interpreted.
        emotion: The surface-level emotion detected in the text.
            This is the overt affective signal, not the deeper fear/desire.
        topic: Topic classification assigned by the ingestion layer.
            Used for initial filtering and routing.
        timestamp: ISO 8601 format timestamp of when the discourse occurred.
        id: Unique identifier assigned after storage. None until persisted.
    """

    # ── Content ────────────────────────────────────────────────────────
    text: str
    """The raw text exactly as it appeared in the source."""

    source: str
    """Platform or channel origin: reddit, youtube, linkedin, telegram,
    sales_call, dm, landing_page, community, or other."""

    context: str
    """Surrounding context where this was said — parent comment, thread,
    video title, conversation frame. Changes interpretation of text."""

    # ── Classification ─────────────────────────────────────────────────
    emotion: str
    """Surface emotion detected in the text (e.g. frustration, excitement,
    confusion, anger, hope). This is the overt affective signal."""

    topic: str
    """Topic classification assigned during ingestion (e.g. pricing,
    onboarding, feature_request, competitor_comparison)."""

    # ── Metadata ───────────────────────────────────────────────────────
    timestamp: str
    """ISO 8601 format timestamp of when the discourse occurred."""

    id: Optional[str] = None
    """Unique identifier assigned after storage. None until the fragment
    has been persisted to the data layer."""


@dataclass
class LanguageGameAnalysis:
    """Core Wittgensteinian semantic analysis of a discourse fragment.

    This is the heart of the engine. It models the gap between what a person
    *says* and what they *mean* within the language game they are playing.
    Wittgenstein argued that words are tools, not labels — their meaning
    emerges from the social game in which they are deployed.

    A single statement like "I can't afford this" is simultaneously:
      - A price objection (surface)
      - A trust signal — they haven't seen enough proof (hidden)
      - A belief that the solution hasn't earned investment yet
      - A fear of wasting money on something that won't work
      - An identity marker — they see themselves as careful, not reckless

    This dataclass captures all those layers.

    Attributes:
        surface_problem: What the person literally says is wrong.
            The text-level complaint or objection.
        hidden_problem: The underlying operational issue that the surface
            problem is a symptom of.
        belief: Inferred belief about the market or world that makes
            their statement feel true to them.
        fear: Inferred fear driving the statement — the negative outcome
            they are trying to avoid.
        hidden_desire: The unspoken want beneath the objection. What they
            actually wish were true.
        objection_type: Classification of the objection mechanism:
            price, timing, trust, complexity, authority, need, etc.
        identity_marker: Social or professional identity revealed by
            the language choices in the statement.
        market_stage: Market maturity signal inferred from the statement:
            emerging, growing, saturated, or commoditized.
        tension: The core tension in the statement — the contradiction
            between what they want and what they fear.
        framing_pattern: How they frame their problem:
            blame, aspiration, victimhood, expertise, denial, etc.
        social_context: Where this language game is being played —
            the platform, community, or conversational setting.
        discourse_role: The role they occupy in this language game:
            critic, evangelist, skeptic, educator, buyer, seller.
        language_game: Name of the Wittgensteinian language game being
            played (e.g. "depth vs attention economy", "expertise vs
            accessibility", "innovation vs reliability").
        possible_solutions: Operational solution directions that could
            resolve the hidden problem.
    """

    # ── Problem Layers ─────────────────────────────────────────────────
    surface_problem: str
    """What the person literally says is wrong. The text-level complaint
    or objection as stated."""

    hidden_problem: str
    """The underlying operational issue that the surface problem is a
    symptom of. What is actually broken in their workflow or thinking."""

    # ── Belief-Fear-Desire Triad ───────────────────────────────────────
    belief: str
    """Inferred belief about the market or world that makes their
    statement feel true to them. The mental model they are operating from."""

    fear: str
    """Inferred fear driving the statement. The negative outcome they
    are trying to avoid by holding this position."""

    hidden_desire: str
    """The unspoken want beneath the objection. What they actually wish
    were true if they felt safe enough to admit it."""

    # ── Objection Mechanics ────────────────────────────────────────────
    objection_type: str
    """Classification of the objection mechanism: price, timing, trust,
    complexity, authority, need, etc."""

    identity_marker: str
    """Social or professional identity revealed by the language choices
    in the statement (e.g. 'pragmatic founder', 'technical skeptic',
    'risk-averse operations manager')."""

    # ── Market Signals ─────────────────────────────────────────────────
    market_stage: str
    """Market maturity signal inferred from the statement: emerging,
    growing, saturated, or commoditized."""

    # ── Tension & Framing ──────────────────────────────────────────────
    tension: str
    """The core tension in the statement — the contradiction between
    what they want and what they fear. The engine that drives the
    language game."""

    framing_pattern: str
    """How they frame their problem: blame, aspiration, victimhood,
    expertise, denial, pragmatism, etc."""

    # ── Contextual Placement ───────────────────────────────────────────
    social_context: str
    """Where this language game is being played — the platform,
    community, or conversational setting that gives the words their
    specific force."""

    discourse_role: str
    """The role they occupy in this language game: critic, evangelist,
    skeptic, educator, buyer, seller."""

    language_game: str
    """Name of the Wittgensteinian language game being played.
    Examples: 'depth vs attention economy', 'expertise vs accessibility',
    'innovation vs reliability', 'speed vs thoroughness'."""

    # ── Solutions ──────────────────────────────────────────────────────
    possible_solutions: List[str]
    """Operational solution directions that could resolve the hidden
    problem. Concrete approaches, not abstract ideas."""


@dataclass
class ResonanceCluster:
    """A cluster of similar discourse patterns across the market.

    When multiple DiscourseFragments share structural similarities in their
    LanguageGameAnalysis — same objection types, overlapping tensions,
    compatible identity markers — they form a ResonanceCluster.

    Clusters represent pockets of the market that share a common language
    game. They are the unit of analysis for understanding what messaging
    resonates (and what falls flat) for a specific audience segment.

    Attributes:
        cluster_id: Unique identifier for this cluster. None until persisted.
        market_cluster: The market vertical or segment this cluster
            represents (e.g. "legal_services", "developer_tools",
            "healthcare", "agencies").
        language_game_ids: IDs of DiscourseFragments whose analyses form
            this cluster.
        high_resonance_patterns: Patterns (phrases, framings, tensions)
            that generate strong market response within this cluster.
        low_resonance_patterns: Patterns that consistently fall flat
            with this cluster — attempts that miss the mark.
        effective_hooks: Hook structures (openers, angles, framings) that
            work for this cluster.
        failed_hooks: Hook structures that don't work — tried and failed.
        belief_density: Concentration of belief signals within this
            cluster, from 0.0 (scattered/weak) to 1.0 (dense/coherent).
        tension_score: Intensity of the core tension in this cluster,
            from 0.0 (mild) to 1.0 (acute/painful).
    """

    cluster_id: Optional[str]
    """Unique identifier for this cluster. Assigned upon persistence."""

    market_cluster: str
    """The market vertical or segment this cluster represents.
    Examples: legal_services, developer_tools, healthcare, agencies."""

    language_game_ids: List[str]
    """IDs of DiscourseFragments whose LanguageGameAnalyses formed
    this cluster through structural similarity."""

    # ── Resonance Patterns ─────────────────────────────────────────────
    high_resonance_patterns: List[str]
    """Patterns — phrases, framings, tensions — that generate strong
    market response within this cluster."""

    low_resonance_patterns: List[str]
    """Patterns that consistently fall flat with this cluster.
    Attempts that miss the mark for this audience."""

    # ── Hooks ──────────────────────────────────────────────────────────
    effective_hooks: List[str]
    """Hook structures — openers, angles, framings — that work
    for this cluster and drive engagement."""

    failed_hooks: List[str]
    """Hook structures that don't work for this cluster.
    Tried and failed — useful for negative filtering."""

    # ── Quantitative Signals ───────────────────────────────────────────
    belief_density: float
    """Concentration of belief signals within this cluster.
    Ranges from 0.0 (scattered, weak beliefs) to 1.0 (dense,
    coherent belief system)."""

    tension_score: float
    """Intensity of the core tension in this cluster.
    Ranges from 0.0 (mild, no urgency) to 1.0 (acute,
    painful, driving action)."""


@dataclass
class ResonanceSignal:
    """Individual signal of market response to a message or pattern.

    Captures a single data point of how the market reacted to a specific
    piece of content, hook, or outreach attempt within a ResonanceCluster.
    Over time, signals accumulate to refine the cluster's resonance model.

    Attributes:
        signal_id: Unique identifier for this signal. None until persisted.
        cluster_id: The ResonanceCluster this signal belongs to.
        signal_type: Type of market response observed: engagement,
            conversion, reply, ctr, ignore, or negative.
        strength: Strength of the signal, from 0.0 (negligible) to
            1.0 (maximum impact).
        metadata: Arbitrary key-value pairs for signal-specific data.
            Could contain platform metrics, A/B test variants, content
            IDs, etc.
        timestamp: ISO 8601 format timestamp of when the signal was
            recorded. Empty string until set.
    """

    signal_id: Optional[str]
    """Unique identifier for this signal. Assigned upon persistence."""

    cluster_id: str
    """The ResonanceCluster this signal belongs to."""

    signal_type: str
    """Type of market response observed: engagement, conversion, reply,
    ctr, ignore, or negative."""

    strength: float
    """Strength of the signal from 0.0 (negligible) to 1.0 (maximum
    impact). Normalized across different signal types."""

    metadata: Dict[str, Any] = field(default_factory=dict)
    """Arbitrary key-value pairs for signal-specific data. May contain
    platform metrics, A/B test variants, content IDs, user agent
    strings, or any other contextual data."""

    timestamp: str = ""
    """ISO 8601 format timestamp of when the signal was recorded.
    Empty string until set by the recording layer."""


@dataclass
class ProspectProfile:
    """Generated outreach profile based on language game analysis.

    The final output of the analysis pipeline. A ProspectProfile synthesizes
    everything the engine knows about a target's language game — their
    beliefs, fears, objections, identity — into an actionable outreach
    strategy with a concrete narrative.

    This is what the outreach layer consumes: not a generic persona, but
    a precise model of which language game to play and how to play it.

    Attributes:
        belief: The core belief to address in outreach. This is the
            mental model you need to either validate or gently challenge.
        identity: The identity marker to resonate with. Speak to who
            they believe themselves to be.
        objection: The primary objection to overcome. Address this
            directly or reframe it entirely.
        resonance_pattern: Which resonance pattern from the cluster
            to apply. The structural template for the message.
        narrative: The generated outreach text. The actual words to
            use, crafted to play the right language game.
        outreach_angle: The strategic angle of approach. The high-level
            framing decision (e.g. 'lead with social proof for
            skeptic identity', 'validate fear then redirect').
        market_cluster: The market segment this profile targets.
            Empty string if not yet classified.
        confidence: How confident the system is in this profile,
            from 0.0 (low confidence, needs more data) to 1.0
            (high confidence, strong signal density).
    """

    # ── Target Model ───────────────────────────────────────────────────
    belief: str
    """The core belief to address in outreach. The mental model you
    need to either validate or gently challenge."""

    identity: str
    """The identity marker to resonate with. Speak to who they believe
    themselves to be — not who you want them to be."""

    objection: str
    """The primary objection to overcome. Address this directly or
    reframe it entirely within a different language game."""

    # ── Strategy ───────────────────────────────────────────────────────
    resonance_pattern: str
    """Which resonance pattern from the cluster to apply. The structural
    template for the message — the pattern that works for this audience."""

    narrative: str
    """The generated outreach text. The actual words to use, crafted
    to play the right language game with the right frame."""

    outreach_angle: str
    """The strategic angle of approach. The high-level framing decision
    (e.g. 'lead with social proof for skeptic identity',
    'validate fear then redirect to aspiration')."""

    # ── Metadata ───────────────────────────────────────────────────────
    market_cluster: str = ""
    """The market segment this profile targets. Empty string if not
    yet classified."""

    confidence: float = 0.0
    """How confident the system is in this profile, from 0.0 (low
    confidence, needs more data) to 1.0 (high confidence, strong
    signal density across the cluster)."""


@dataclass
class IngestionResult:
    """Result from the ingestion layer for a single piece of discourse.

    Wraps a DiscourseFragment with its optional LanguageGameAnalysis and
    processing status. This is the return type for the ingestion pipeline — every piece of raw discourse flows through ingestion and emerges as
    an IngestionResult.

    Attributes:
        fragment: The normalized DiscourseFragment created from the
            raw input.
        analysis: The LanguageGameAnalysis if the fragment was deep
            enough to warrant analysis. None for fragments that were
            too short, ambiguous, or low-signal.
        success: Whether ingestion completed without errors.
        error: Error message if ingestion failed. None on success.
    """

    fragment: DiscourseFragment
    """The normalized DiscourseFragment created from the raw input."""

    analysis: Optional[LanguageGameAnalysis] = None
    """The LanguageGameAnalysis if the fragment was deep enough to
    warrant full Wittgensteinian analysis. None for fragments that
    were too short, ambiguous, or low-signal to analyze."""

    success: bool = True
    """Whether ingestion completed without errors."""

    error: Optional[str] = None
    """Error message if ingestion failed. None on success."""
