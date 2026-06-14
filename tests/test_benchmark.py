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

from agents.llm_client import LLMResponse

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


def _percentile(data, p):
    if not data:
        return 0.0
    s = sorted(data)
    k = max(0, min(len(s) - 1, int(len(s) * p / 100)))
    return s[k]


async def _bench_phase(phase_name: str, patch_path: str, fn, *args, **kwargs):
    timings = []
    for i in range(WARMUP + N_ITERATIONS):
        t0 = time.perf_counter()
        with patch(patch_path, new_callable=AsyncMock) as mock_fn:
            mock_fn.return_value = LLMResponse(content="{}", model="mock")
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
    timings = []
    for i in range(WARMUP + N_ITERATIONS):
        t0 = time.perf_counter()
        await enrich_lead(SAMPLE_LEAD)
        elapsed = time.perf_counter() - t0
        if i >= WARMUP:
            timings.append(elapsed)
    p50 = _percentile(timings, 50)
    p95 = _percentile(timings, 95)
    p99 = _percentile(timings, 99)
    mean = statistics.mean(timings)
    print(REPORT_LINE.format(phase="enrich_lead (real)", p50=p50, p95=p95, p99=p99, mean=mean, n=len(timings)))
    print()


@pytest.mark.skipif(not use_real_llm, reason="Real LLM benchmark requires LITELLM_URL")
@pytest.mark.asyncio
async def test_benchmark_score_real_llm():
    """Benchmark score com LLM real."""
    from agents.scorer import score_lead
    dossie = {"resumo_perfil": "Restaurante tradicional", "pontos_fracos": ["Sem website"], "oportunidades": ["Website profissional"], "maturidade_digital": "baixo"}
    timings = []
    for i in range(WARMUP + N_ITERATIONS):
        t0 = time.perf_counter()
        await score_lead(dossie)
        elapsed = time.perf_counter() - t0
        if i >= WARMUP:
            timings.append(elapsed)
    p50 = _percentile(timings, 50)
    p95 = _percentile(timings, 95)
    p99 = _percentile(timings, 99)
    mean = statistics.mean(timings)
    print(REPORT_LINE.format(phase="score_lead (real)", p50=p50, p95=p95, p99=p99, mean=mean, n=len(timings)))
    print()


@pytest.mark.skipif(not use_real_llm, reason="Real LLM benchmark requires LITELLM_URL")
@pytest.mark.asyncio
async def test_benchmark_message_real_llm():
    """Benchmark message com LLM real."""
    from agents.messenger import generate_message
    scored_lead = {**SAMPLE_LEAD, "score": 65, "faixa": "morno", "status": "qualificado", "dossie": {}}
    timings = []
    for i in range(WARMUP + N_ITERATIONS):
        t0 = time.perf_counter()
        await generate_message(scored_lead)
        elapsed = time.perf_counter() - t0
        if i >= WARMUP:
            timings.append(elapsed)
    p50 = _percentile(timings, 50)
    p95 = _percentile(timings, 95)
    p99 = _percentile(timings, 99)
    mean = statistics.mean(timings)
    print(REPORT_LINE.format(phase="generate_message (real)", p50=p50, p95=p95, p99=p99, mean=mean, n=len(timings)))
    print()


@pytest.mark.asyncio
async def test_benchmark_enrich_mock():
    """Benchmark enrich com mock LLM — mede overhead do framework."""
    from agents.enricher import enrich_lead

    print(f"\n\n=== Benchmark MOCK LLM ({N_ITERATIONS} iters, {WARMUP} warmup) ===")
    print(REPORT_HEADER)
    print("-" * len(REPORT_HEADER))
    await _bench_phase("enrich_lead (mock)", "agents.enricher.llm_complete", enrich_lead, SAMPLE_LEAD)
    print()


@pytest.mark.asyncio
async def test_benchmark_score_mock():
    """Benchmark score com mock LLM."""
    from agents.scorer import score_lead
    dossie = {"resumo_perfil": "Restaurante tradicional", "pontos_fracos": ["Sem website"], "oportunidades": ["Website profissional"], "maturidade_digital": "baixo"}
    await _bench_phase("score_lead (mock)", "agents.scorer.llm_complete", score_lead, dossie)
    print()


@pytest.mark.asyncio
async def test_benchmark_message_mock():
    """Benchmark message com mock LLM."""
    from agents.messenger import generate_message
    scored_lead = {**SAMPLE_LEAD, "score": 65, "faixa": "morno", "status": "qualificado", "dossie": {}}
    await _bench_phase("generate_message (mock)", "agents.messenger.llm_complete", generate_message, scored_lead)
    print()


@pytest.mark.asyncio
async def test_benchmark_mock_pipeline():
    """Benchmark do pipeline completo (enrich → score → message) com mock LLM."""
    from agents.enricher import enrich_lead
    from agents.scorer import score_lead
    from agents.messenger import generate_message

    timings = []
    for i in range(WARMUP + N_ITERATIONS):
        t0 = time.perf_counter()

        with patch("agents.enricher.llm_complete", new_callable=AsyncMock) as mock_e:
            mock_e.return_value = LLMResponse(content=LLM_MOCK_RESPONSES["enricher"], model="mock")
            enriched = await enrich_lead(SAMPLE_LEAD)

        dossie = enriched["dossie"]

        with patch("agents.scorer.llm_complete", new_callable=AsyncMock) as mock_s:
            mock_s.return_value = LLMResponse(content=LLM_MOCK_RESPONSES["scorer"], model="mock")
            scored = await score_lead(dossie)

        scored_lead = {**SAMPLE_LEAD, "score": scored["score"], "faixa": scored.get("faixa"), "status": "qualificado", "dossie": dossie}

        with patch("agents.messenger.llm_complete", new_callable=AsyncMock) as mock_m:
            mock_m.return_value = LLMResponse(content=LLM_MOCK_RESPONSES["messenger"], model="mock")
            await generate_message(scored_lead)

        elapsed = time.perf_counter() - t0
        if i >= WARMUP:
            timings.append(elapsed)

    p50 = _percentile(timings, 50)
    p95 = _percentile(timings, 95)
    p99 = _percentile(timings, 99)
    mean = statistics.mean(timings)
    print(REPORT_LINE.format(phase="pipeline completo (mock)", p50=p50, p95=p95, p99=p99, mean=mean, n=len(timings)))
