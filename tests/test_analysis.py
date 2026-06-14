"""
Testes para src/analysis/ — models, templates, analyzer, resonance (unit).
"""
import pytest
from src.analysis.models import (
    DiscourseFragment, LanguageGameAnalysis, ResonanceCluster,
    ResonanceSignal, ProspectProfile, IngestionResult,
)
from src.analysis.templates import (
    build_ingestion_prompt, build_language_game_prompt,
    build_resonance_prompt, build_prospect_prompt,
)


class TestModels:
    def test_discourse_fragment_defaults(self):
        f = DiscourseFragment(text="hello", source="reddit", context="", emotion="neutral", topic="other", timestamp="now")
        assert f.text == "hello"
        assert f.source == "reddit"
        assert f.id is None

    def test_language_game_analysis_full(self):
        a = LanguageGameAnalysis(
            surface_problem="no clients",
            hidden_problem="can't sell",
            belief="market is dead",
            fear="wasting time",
            hidden_desire="easy pipeline",
            objection_type="need",
            identity_marker="freelancer",
            market_stage="saturated",
            tension="wants vs fears",
            framing_pattern="denial",
            social_context="forum",
            discourse_role="skeptic",
            language_game="commodity trap",
            possible_solutions=["specialize"],
        )
        assert a.belief == "market is dead"
        assert len(a.possible_solutions) == 1

    def test_resonance_cluster(self):
        c = ResonanceCluster(
            cluster_id="abc123",
            market_cluster="devtools",
            language_game_ids=["g1", "g2"],
            high_resonance_patterns=["p1", "p2"],
            low_resonance_patterns=["p3"],
            effective_hooks=["hook1"],
            failed_hooks=["fail1"],
            belief_density=0.75,
            tension_score=0.6,
        )
        assert c.market_cluster == "devtools"
        assert c.belief_density == 0.75

    def test_resonance_signal(self):
        s = ResonanceSignal(signal_id="s1", cluster_id="c1", signal_type="engagement", strength=0.8)
        assert s.signal_type == "engagement"
        assert s.strength == 0.8

    def test_prospect_profile(self):
        p = ProspectProfile(
            belief="price is too high",
            identity="bootstrapper",
            objection="value not proven",
            resonance_pattern="social proof",
            narrative="Here is how...",
            outreach_angle="lead with ROI",
            market_cluster="saas",
            confidence=0.85,
        )
        assert p.belief == "price is too high"
        assert p.confidence == 0.85

    def test_ingestion_result_defaults(self):
        frag = DiscourseFragment(text="x", source="y", context="", emotion="neutro", topic="z", timestamp="t")
        r = IngestionResult(fragment=frag)
        assert r.success is True
        assert r.analysis is None
        assert r.error is None


class TestTemplates:
    def test_build_ingestion_prompt_includes_text(self):
        prompt = build_ingestion_prompt("test text here", "reddit", "some context")
        assert "test text here" in prompt
        assert "reddit" in prompt
        assert "JSON" in prompt or "json" in prompt

    def test_build_ingestion_prompt_no_context(self):
        prompt = build_ingestion_prompt("just text", "telegram")
        assert "just text" in prompt
        assert "telegram" in prompt

    def test_build_language_game_prompt(self):
        prompt = build_language_game_prompt("Nobody buys websites", "forum", "market discussion", "frustration", "pricing")
        assert "Nobody buys websites" in prompt
        assert "Wittgensteinian" in prompt
        assert "belief" in prompt.lower()

    def test_build_resonance_prompt(self):
        analyses = [{"belief": "market dead", "language_game": "commodity"}]
        prompt = build_resonance_prompt(analyses, "devtools")
        assert "market dead" in prompt
        assert "devtools" in prompt
        assert "resonance" in prompt.lower()

    def test_build_resonance_prompt_no_cluster(self):
        analyses = [{"belief": "test"}]
        prompt = build_resonance_prompt(analyses)
        assert "not yet classified" in prompt

    def test_build_prospect_prompt(self):
        analysis = {"belief": "too expensive", "identity_marker": "bootstrapper"}
        prompt = build_prospect_prompt(analysis)
        assert "too expensive" in prompt
        assert "Wittgensteinian" in prompt

    def test_build_prospect_prompt_with_resonance(self):
        analysis = {"belief": "test"}
        resonance = {"market_cluster": "saas", "effective_hooks": ["social proof"]}
        prompt = build_prospect_prompt(analysis, resonance)
        assert "saas" in prompt
