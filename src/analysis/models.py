from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class DiscourseFragment:
    text: str
    source: str
    context: str
    emotion: str
    topic: str
    timestamp: str
    id: Optional[str] = None


@dataclass
class LanguageGameAnalysis:
    surface_problem: str
    hidden_problem: str
    belief: str
    fear: str
    hidden_desire: str
    objection_type: str
    identity_marker: str
    market_stage: str
    tension: str
    framing_pattern: str
    social_context: str
    discourse_role: str
    language_game: str
    possible_solutions: List[str]


@dataclass
class ResonanceCluster:
    cluster_id: Optional[str]
    market_cluster: str
    language_game_ids: List[str]
    high_resonance_patterns: List[str]
    low_resonance_patterns: List[str]
    effective_hooks: List[str]
    failed_hooks: List[str]
    belief_density: float
    tension_score: float


@dataclass
class ResonanceSignal:
    signal_id: Optional[str]
    cluster_id: str
    signal_type: str
    strength: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""


@dataclass
class ProspectProfile:
    belief: str
    identity: str
    objection: str
    resonance_pattern: str
    narrative: str
    outreach_angle: str
    market_cluster: str = ""
    confidence: float = 0.0


@dataclass
class IngestionResult:
    fragment: DiscourseFragment
    analysis: Optional[LanguageGameAnalysis] = None
    success: bool = True
    error: Optional[str] = None
