"""
Testes end-to-end do pipeline de Discourse (sem LLM — testa parsing, validação e fallbacks).
"""
import pytest
from src.analysis.analyzer import (
    _validate_source, _fragment_id, _validate_fragment, _validate_analysis,
    _parse_fragment_text, _parse_analysis_text,
    _build_fallback_fragment, _build_fallback_analysis,
    _calculate_tension_score,
    VALID_SOURCES, VALID_OBJECTION_TYPES,
)
from src.analysis.resonance import (
    _validate_cluster, _validate_prospect,
    _parse_cluster_text, _parse_prospect_text,
    _build_fallback_cluster, _build_fallback_prospect, _build_cluster_text,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_fragment(**overrides):
    return {
        "text": "Preço muito alto para meu orçamento",
        "source": "reddit",
        "context": "discussão sobre ferramentas",
        "emotion": "frustration",
        "topic": "pricing",
        "fragment_id": "abc123",
        "timestamp": "2026-06-13T00:00:00",
        **overrides,
    }


def _make_analysis(**overrides):
    return {
        "surface_problem": "preço alto",
        "hidden_problem": "orçamento limitado",
        "belief": "ferramentas caras não valem o investimento",
        "fear": "gastar dinheiro em algo que não funciona",
        "hidden_desire": "validação antes de comprar",
        "objection_type": "price",
        "identity_marker": "bootstrapper",
        "market_stage": "growing",
        "tension": "quer resolver mas tem medo de perder dinheiro",
        "framing_pattern": "pragmatism",
        "social_context": "fórum de startups",
        "discourse_role": "skeptic",
        "language_game": "risk vs reward",
        "possible_solutions": ["free trial", "prova social", "garantia"],
        **overrides,
    }


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 1 — INGESTION
# ══════════════════════════════════════════════════════════════════════════════

class TestIngestion:
    def test_validate_source_valid(self):
        for s in VALID_SOURCES:
            assert _validate_source(s) == s

    def test_validate_source_invalid_falls_to_other(self):
        assert _validate_source("twitter") == "other"

    def test_validate_source_empty(self):
        assert _validate_source("") == "other"

    def test_validate_source_none(self):
        assert _validate_source(None) == "other"  # noqa

    def test_fragment_id_deterministic(self):
        id1 = _fragment_id("texto", "reddit")
        id2 = _fragment_id("texto", "reddit")
        assert id1 == id2
        assert len(id1) == 16

    def test_fragment_id_diff_source(self):
        id1 = _fragment_id("texto", "reddit")
        id2 = _fragment_id("texto", "telegram")
        assert id1 != id2

    def test_validate_fragment_minimal(self):
        data = {"text": "teste", "source": "reddit", "context": "", "emotion": "neutro", "topic": "outro"}
        result = _validate_fragment(data, "reddit", "teste")
        assert result["text"] == "teste"
        assert result["source"] == "reddit"

    def test_validate_fragment_missing_fields(self):
        data = {}
        result = _validate_fragment(data, "telegram", "texto")
        assert result["text"] == "texto"
        assert result["source"] == "telegram"
        assert result["emotion"] == "neutral"
        assert result["topic"] == "other"

    def test_parse_fragment_text_json_fallback(self):
        text = '{"text": "hello", "source": "reddit", "context": "ctx", "emotion": "happy", "topic": "test"}'
        result = _parse_fragment_text(text)
        # The text parser doesn't parse JSON, it's for non-JSON output
        # This should produce a basic structure
        assert isinstance(result, dict)

    def test_parse_fragment_text_line_based(self):
        text = 'text: hello world\nsource: reddit\ncontext: some context\nemotion: happy\ntopic: test'
        result = _parse_fragment_text(text)
        assert result["text"] == "hello world"
        assert result["source"] == "reddit"
        assert result["emotion"] == "happy"

    def test_build_fallback_fragment(self):
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).isoformat()
        result = _build_fallback_fragment("texto erro", "reddit", "ctx", ts, "LLM error")
        assert result["fragment_id"] is not None
        assert result["source"] == "reddit"
        assert result["text"] == "texto erro"
        assert result["context"] == "ctx"
        assert result["emotion"] == "unknown"
        assert result["topic"] == "other"
        assert result["ingestion_success"] is False
        assert result["ingestion_error"] == "LLM error"


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 2 — LANGUAGE GAME ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

class TestLanguageGame:
    def test_validate_analysis_full(self):
        data = _make_analysis()
        result = _validate_analysis(data)
        for key in data:
            if key != "tension_score":
                assert result[key] == data[key], f"Mismatch for {key}"

    def test_validate_analysis_empty(self):
        result = _validate_analysis({})
        assert result["surface_problem"] == "unknown"
        assert result["hidden_problem"] == "unknown"
        assert result["belief"] == "unknown"
        assert result["possible_solutions"] == ["unknown"]
        assert result["objection_type"] == "unknown"
        assert result["market_stage"] == "unknown"
        assert result["framing_pattern"] == "unknown"
        assert result["discourse_role"] == "unknown"

    def test_calculate_tension_score(self):
        analysis = _make_analysis(
            tension="quer mas tem medo",
            belief="acredita em X",
            fear="medo de Y",
            hidden_desire="deseja Z",
        )
        score = _calculate_tension_score(analysis)
        assert 0.0 <= score <= 1.0

    def test_calculate_tension_score_minimal(self):
        analysis = {"tension": "", "belief": "", "fear": "", "hidden_desire": ""}
        score = _calculate_tension_score(analysis)
        assert 0.0 <= score <= 1.0

    def test_parse_analysis_text_simple(self):
        text = "surface_problem: problema visível\nhidden_problem: problema oculto\n"
        result = _parse_analysis_text(text)
        assert "problema visível" in result.get("surface_problem", "")
        assert "problema oculto" in result.get("hidden_problem", "")

    def test_parse_analysis_text_with_lists(self):
        text = 'possible_solutions: ["sol1", "sol2", "sol3"]'
        result = _parse_analysis_text(text)
        assert "sol1" in result.get("possible_solutions", [])

    def test_parse_analysis_text_with_numbers(self):
        text = "belief_density: 0.75\ntension_score: 0.60"
        result = _parse_analysis_text(text)
        # analysis parser uses "belief_density" only in resonance context
        # this is just checking it doesn't crash
        assert isinstance(result, dict)

    def test_build_fallback_analysis(self):
        frag = _make_fragment(text="preço alto")
        result = _build_fallback_analysis(frag, "LLM error")
        assert result["surface_problem"] == "preço alto"
        assert result["language_game"] == "unknown"
        assert result["analysis_fallback"] is True
        assert result["analysis_error"] == "LLM error"
        assert result["tension_score"] == 0.0


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 3 — RESONANCE ENGINE
# ══════════════════════════════════════════════════════════════════════════════

class TestResonance:
    def test_validate_cluster_full(self):
        data = {
            "market_cluster": "devtools",
            "high_resonance_patterns": ["p1", "p2"],
            "low_resonance_patterns": ["p3"],
            "effective_hooks": ["hook1"],
            "failed_hooks": ["fail1"],
            "belief_density": 0.75,
            "tension_score": 0.60,
        }
        result = _validate_cluster(data)
        assert result["market_cluster"] == "devtools"
        assert len(result["high_resonance_patterns"]) == 2
        assert result["belief_density"] == 0.75

    def test_validate_cluster_empty(self):
        result = _validate_cluster({})
        assert result["market_cluster"] == "unknown"
        assert result["high_resonance_patterns"] == []
        assert result["belief_density"] == 0.5
        assert result["tension_score"] == 0.5

    def test_validate_prospect_full(self):
        data = {
            "belief": "preço é problema",
            "identity": "bootstrapper",
            "objection": "falta de retorno",
            "resonance_pattern": "social proof",
            "narrative": "case de sucesso",
            "outreach_angle": "ROI primeiro",
            "market_cluster": "saas",
            "confidence": 0.85,
        }
        result = _validate_prospect(data)
        assert result["belief"] == "preço é problema"
        assert result["confidence"] == 0.85

    def test_validate_prospect_empty(self):
        result = _validate_prospect({})
        assert result["belief"] == "unknown"
        assert result["confidence"] == 0.5

    def test_parse_cluster_text_simple(self):
        text = "market_cluster: devtools\nhigh_resonance_patterns: [\"pattern1\", \"pattern2\"]"
        result = _parse_cluster_text(text)
        assert result["market_cluster"] == "devtools"
        assert "pattern1" in result["high_resonance_patterns"]

    def test_parse_cluster_text_line_items(self):
        text = "high_resonance_patterns:\n- pattern1\n- pattern2\n\nlow_resonance_patterns:\n- pattern3"
        result = _parse_cluster_text(text)
        assert "pattern1" in result.get("high_resonance_patterns", [])

    def test_parse_prospect_text_simple(self):
        text = "belief: acredito que X\nidentity: empreendedor\nobjection: preco"
        result = _parse_prospect_text(text)
        assert isinstance(result, dict)

    def test_parse_prospect_text_full(self):
        text = 'belief: acredito que X\nidentity: empreendedor\nobjection: preço\nresonance_pattern: social proof\nnarrative: história convincente\noutreach_angle: educational\nmarket_cluster: marketing\nconfidence: 0.80'
        result = _parse_prospect_text(text)
        assert result["belief"] == "acredito que X"
        assert result["identity"] == "empreendedor"
        assert result["confidence"] == 0.80

    def test_build_cluster_text(self):
        cluster = {
            "market_cluster": "devtools",
            "high_resonance_patterns": ["p1"],
            "effective_hooks": ["h1"],
            "low_resonance_patterns": ["p2"],
            "failed_hooks": ["f1"],
        }
        text = _build_cluster_text(cluster)
        assert "devtools" in text
        assert "p1" in text
        assert "h1" in text

    def test_build_fallback_cluster(self):
        analyses = [_make_analysis()]
        result = _build_fallback_cluster(analyses, "LLM error")
        assert result["cluster_fallback"] is True
        assert result["cluster_error"] == "LLM error"
        assert result["source_analysis_count"] == 1

    def test_build_fallback_cluster_empty(self):
        result = _build_fallback_cluster([], "no data")
        assert result["high_resonance_patterns"] == ["unknown"]

    def test_build_fallback_prospect(self):
        analysis = _make_analysis()
        result = _build_fallback_prospect(analysis, "LLM error")
        assert result["prospect_fallback"] is True
        assert result["prospect_error"] == "LLM error"
        assert result["belief"] == analysis["belief"]

    def test_build_fallback_prospect_empty(self):
        result = _build_fallback_prospect({}, "no data")
        assert result["belief"] == "unknown"
        assert result["confidence"] == 0.0
