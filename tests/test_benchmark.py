"""
Benchmark de Performance do pipeline de prospecção.
Mede P50/P95/P99 de cada fase (enrich, score, message).
Usa mock LLM se LITELLM_URL não estiver definido, LLM real se estiver.
"""
import os
import time
import statistics
from unittest.mock import AsyncMock, patch

import pytest

from agents.factory import ServiceFactory
from agents.ports.llm_client import LLMResponse

use_real_llm = bool(os.environ.get("LITELLM_URL"))

LLM_MOCK_RESPONSES = {
    "enricher": (
        '{"resumo_perfil": "Restaurante tradicional",'
        '"pontos_fracos": ["Nao possui website"],'
        '"oportunidades": ["Criar site profissional"],'
        '"maturidade_digital": "baixo"}'
    ),
    "scorer": (
        '{"score": 65, "justification": "Lead possui pontos fracos claros.",'
        '"faixa": "morno"}'
    ),
    "messenger": (
        '{"message": "Ola! Podemos ajudar com seu site."}'
    ),
}

SAMPLE_LEAD = {
    "name": "Restaurante Teste",
    "address": "Rua Exemplo, 123",
    "phone": "+55 11 99999-9999",
    "rating": 4.2,
    "google_maps_url": "https://maps.google.com/?cid=teste123",
}

N_ITERATIONS = 10
WARMUP = 2
REPORT_HEADER = f"{'Fase':<30} {'P50 (s)':>10} {'P95 (s)':>10} {'P99 (s)':>10} {'Média (s)':>10} {'Iters':>6}"
REPORT_LINE = "{phase:<30} {p50:>10.4f} {p95:>10.4f} {p99:>10.4f} {mean:>10.4f} {n:>6}"


@pytest.fixture(scope="module")
def mock_llm():
    mock = AsyncMock()
    return mock


def _percentile(data, p):
    if not data:
        return 0.0
    s = sorted(data)
    k = max(0, min(len(s) - 1, int(len(s) * p / 100)))
    return s[k]


async def _bench_phase(phase_name: str, fn, *args, **kwargs):
    timings = []
    for i in range(WARMUP + N_ITERATIONS):
        t0 = time.perf_counter()
        await fn(*args, **kwargs)
        elapsed = time.perf_counter() - t0
        if i >= WARMUP:
            timings.append(elapsed)
    p50 = _percentile(timings, 50)
    p95 = _percentile(timings, 95)
    p99 = _percentile(timings, 99)
    mean = statistics.mean(timings)
    print(REPORT_LINE.format(phase=phase_name, p50=p50, p95=p95, p99=p99, mean=mean, n=len(timings)))
    return timings


@pytest.mark.skipif(not use_real_llm, reason="Real LLM benchmark requires LITELLM_URL")
@pytest.mark.asyncio
async def test_benchmark_enrich_real_llm():
    """Benchmark enrich com LLM real."""
    from agents.enricher import enrich_lead
    print(f"\n\n=== Benchmark REAL LLM ({N_ITERATIONS} iters, {WARMUP} warmup) ===")
    print(REPORT_HEADER)
    print("-" * len(REPORT_HEADER))
    await _bench_phase("enrich_lead", enrich_lead, SAMPLE_LEAD)
    print()


@pytest.mark.skipif(not use_real_llm, reason="Real LLM benchmark requires LITELLM_URL")
@pytest.mark.asyncio
async def test_benchmark_score_real_llm():
    """Benchmark score com LLM real."""
    from agents.scorer import score_lead
    dossie = {
        "resumo_perfil": "Restaurante tradicional",
        "pontos_fracos": ["Sem website"],
        "oportunidades": ["Website profissional"],
        "maturidade_digital": "baixo",
    }
    await _bench_phase("score_lead", score_lead, dossie)
    print()


@pytest.mark.skipif(not use_real_llm, reason="Real LLM benchmark requires LITELLM_URL")
@pytest.mark.asyncio
async def test_benchmark_message_real_llm():
    """Benchmark message com LLM real."""
    from agents.messenger import generate_message
    scored_lead = {**SAMPLE_LEAD, "score": 65, "faixa": "morno", "status": "qualificado", "dossie": {}}
    await _bench_phase("generate_message", generate_message, scored_lead)
    print()


@pytest.mark.asyncio
async def test_benchmark_enrich_mock(mock_llm):
    """Benchmark enrich com mock LLM — mede overhead do framework."""
    from agents.enricher import enrich_lead
    mock_llm.complete.return_value = LLMResponse(content=LLM_MOCK_RESPONSES["enricher"], model="mock")
    with patch.object(ServiceFactory, "get_llm_client", return_value=mock_llm):
        print(f"\n\n=== Benchmark MOCK LLM ({N_ITERATIONS} iters, {WARMUP} warmup) ===")
        print(REPORT_HEADER)
        print("-" * len(REPORT_HEADER))
        await _bench_phase("enrich_lead (mock)", enrich_lead, SAMPLE_LEAD)
        print()


@pytest.mark.asyncio
async def test_benchmark_score_mock(mock_llm):
    """Benchmark score com mock LLM."""
    from agents.scorer import score_lead
    mock_llm.complete.return_value = LLMResponse(content=LLM_MOCK_RESPONSES["scorer"], model="mock")
    dossie = {
        "resumo_perfil": "Restaurante tradicional",
        "pontos_fracos": ["Sem website"],
        "oportunidades": ["Website profissional"],
        "maturidade_digital": "baixo",
    }
    with patch.object(ServiceFactory, "get_llm_client", return_value=mock_llm):
        await _bench_phase("score_lead (mock)", score_lead, dossie)
        print()


@pytest.mark.asyncio
async def test_benchmark_message_mock(mock_llm):
    """Benchmark message com mock LLM."""
    from agents.messenger import generate_message
    mock_llm.complete.return_value = LLMResponse(content=LLM_MOCK_RESPONSES["messenger"], model="mock")
    scored_lead = {**SAMPLE_LEAD, "score": 65, "faixa": "morno", "status": "qualificado", "dossie": {}}
    with patch.object(ServiceFactory, "get_llm_client", return_value=mock_llm):
        await _bench_phase("generate_message (mock)", generate_message, scored_lead)
        print()


@pytest.mark.asyncio
async def test_benchmark_mock_pipeline(mock_llm):
    """Benchmark do pipeline completo (enrich → score → message) com mock LLM."""
    from agents.enricher import enrich_lead
    from agents.scorer import score_lead
    from agents.messenger import generate_message

    timings = []

    for i in range(WARMUP + N_ITERATIONS):
        mock_llm.complete.side_effect = [
            LLMResponse(content=LLM_MOCK_RESPONSES["enricher"], model="mock"),
            LLMResponse(content=LLM_MOCK_RESPONSES["scorer"], model="mock"),
            LLMResponse(content=LLM_MOCK_RESPONSES["messenger"], model="mock"),
        ]
        t0 = time.perf_counter()
        with patch.object(ServiceFactory, "get_llm_client", return_value=mock_llm):
            enriched = await enrich_lead(SAMPLE_LEAD)
            dossie = enriched["dossie"]
            scored = await score_lead(dossie)
            scored_lead = {**SAMPLE_LEAD, "score": scored["score"], "faixa": scored.get("faixa"), "status": "qualificado", "dossie": dossie}
            await generate_message(scored_lead)
        elapsed = time.perf_counter() - t0
        if i >= WARMUP:
            timings.append(elapsed)

    p50 = _percentile(timings, 50)
    p95 = _percentile(timings, 95)
    p99 = _percentile(timings, 99)
    mean = statistics.mean(timings)
    print(REPORT_LINE.format(phase="pipeline completo (mock)", p50=p50, p95=p95, p99=p99, mean=mean, n=len(timings)))
