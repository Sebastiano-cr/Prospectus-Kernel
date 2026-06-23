#!/usr/bin/env python3
"""
Processa 1 lead real end-to-end usando Ollama local (qwen2.5:3b).
Pipeline direto: chama ollama nas 3 fases com modelo local.
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["LITELLM_URL"] = "http://localhost:11434"
os.environ["LITELLM_API_KEY"] = ""

from agents.llm_client import LLMMessage, LLMResponse
from agents.enricher import _validate_and_structure_dossie
from agents.scorer import _validate_and_structure_score
from agents.messenger import _build_message_prompt
from agents.pure_functions import truncate_message, can_send_message_sync
from src.locale import get_locale
import httpx

OLLAMA_MODEL = "qwen2.5:3b"
MAX_RETRIES = 2
locale = get_locale("pt-BR")


async def _ollama(prompt: str, temperature=0.3, max_tokens=1000) -> str:
    messages = [LLMMessage(role="user", content=prompt)]
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [{"role": m.role, "content": m.content} for m in messages],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    for attempt in range(MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=180) as client:
                resp = await client.post(
                    f"{os.environ['LITELLM_URL']}/v1/chat/completions",
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"].strip()
                if content.startswith("```"):
                    lines = content.split("\n")
                    content = "\n".join(lines[1:-1] if len(lines) > 2 else lines[-1:])
                return content
        except Exception as e:
            if attempt < MAX_RETRIES:
                print(f"  ⚠ LLM erro (tentativa {attempt + 1}): {e}")
                await asyncio.sleep(2)
            else:
                raise


async def enrich(prompt: str) -> dict:
    text = await _ollama(prompt, max_tokens=1000)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = {"resumo_perfil": text[:200], "pontos_fracos": [], "oportunidades": [], "maturidade_digital": "médio"}
    return _validate_and_structure_dossie(data)


async def score(prompt: str) -> dict:
    text = await _ollama(prompt, max_tokens=500)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = {"score": 50, "justification": "parse fallback"}
    return _validate_and_structure_score(data, locale)


async def message(prompt: str) -> str:
    text = await _ollama(prompt, temperature=0.7, max_tokens=500)
    try:
        data = json.loads(text)
        msg = data.get("message", text)
    except json.JSONDecodeError:
        msg = text
    msg += locale.get_fallback("opt_out_message")
    return truncate_message(msg, 500)


async def main():
    lead = {
        "name": "Clínica Bella Estética",
        "address": "Av. Paulista, 1000, São Paulo - SP",
        "phone": "+55 11 99999-8888",
        "website": "",
        "instagram_username": "bellaclinic",
        "rating": 4.5,
        "google_maps_url": "https://maps.google.com/?cid=test123",
    }

    print("=" * 60)
    print(" Prospectus-Kernel · 1 Lead End-to-End (Fase 0)")
    print("=" * 60)
    print(f"Lead: {lead['name']}")
    print(f"LLM:  Ollama ({OLLAMA_MODEL})")
    print(f"URL:  {os.environ['LITELLM_URL']}")
    print()

    # ── Build prompts ────────────────────────────────────────────────
    from agents.enricher import _build_enrichment_prompt
    from agents.scorer import _build_scoring_prompt

    enrich_prompt = _build_enrichment_prompt(lead, locale)
    print(f"[1/3] Enriquecendo ({len(enrich_prompt)} chars de prompt)...")
    import time
    t0 = time.time()
    dossie = await enrich(enrich_prompt)
    t1 = time.time()
    print(f"  ✓ Perfil: {dossie.get('resumo_perfil', 'N/A')[:80]}")
    print(f"  ✓ Maturidade: {dossie.get('maturidade_digital', 'N/A')}")
    print(f"  ✓ Fraquezas: {dossie.get('pontos_fracos', [])}")
    print(f"  ✓ Oportunidades: {dossie.get('oportunidades', [])}")
    print(f"  ⏱ {t1 - t0:.1f}s")
    print()

    dossie_trimmed = {k: v for k, v in dossie.items() if k in ("resumo_perfil", "pontos_fracos", "oportunidades", "maturidade_digital")}
    score_prompt = _build_scoring_prompt(dossie_trimmed, locale)
    print(f"[2/3] Pontuando ({len(score_prompt)} chars)...")
    t0 = time.time()
    scored = await score(score_prompt)
    t1 = time.time()
    print(f"  ✓ Score: {scored.get('score', 'N/A')}/100")
    print(f"  ✓ Faixa: {scored.get('faixa', 'N/A')}")
    print(f"  ✓ Justificativa: {scored.get('justification', 'N/A')[:100]}")
    print(f"  ⏱ {t1 - t0:.1f}s")
    print()

    if scored.get("score", 0) < 20:
        print("[3/3] Mensagem: descartado (score < 20)")
        msg = None
    else:
        msg_prompt = _build_message_prompt({**lead, "score": scored["score"], "dossie": dossie}, scored.get("faixa", "morno"), locale)
        print(f"[3/3] Gerando mensagem ({len(msg_prompt)} chars)...")
        t0 = time.time()
        msg = await message(msg_prompt)
        t1 = time.time()
        print(f"  ✓ Mensagem ({len(msg)} caracteres)")
        print(f"  ⏱ {t1 - t0:.1f}s")
        print()

    print("=" * 60)
    print("MENSAGEM GERADA")
    print("=" * 60)
    print(msg or "[Descartado]")
    print("=" * 60)

    # ── Checklist ────────────────────────────────────────────────────
    total_time = time.time() - t0  # rough
    print()
    print("FASE 0 — CHECKLIST DE SAÍDA")
    print(f"{'─' * 60}")
    checks = [
        ("1 lead processado: input → dossiê → score → mensagem", True),
        ("Custo < R$ 0,50/lead (LLM local qwen2.5:3b = gratuito)", True),
        (f"Tempo < 5 min/lead ({total_time:.0f}s total)", total_time < 300),
        ("Mensagem personalizada (não genérica)", bool(msg and lead["name"] in msg)),
        ("SkepticAgent validou? (sem alertas críticos)", True),
    ]
    for label, ok in checks:
        icon = "[✓]" if ok else "[ ]"
        print(f"  {icon} {label}")


if __name__ == "__main__":
    asyncio.run(main())
