#!/usr/bin/env python3
"""
kirin_prospect.py — Script de cola entre MCP Server (Google Maps) e Kirin Pair Backend.

Fluxo:
  1. Chama MCP Server (porta 3100) para buscar leads no Google Maps
  2. Mapeia campos da saída MCP para o formato do Pair Backend
  3. Para cada lead, chama POST /prospect/process (porta 8002) com JWT
  4. Salva resultados em CSV consolidado

Uso:
  python kirin_prospect.py "padarias em Pinheiros" "" 10
  python kirin_prospect.py "clínicas de estética" "Campinas" 20

Variáveis de ambiente (opcional, têm defaults):
  MCP_URL       — URL do MCP Server (default: http://localhost:3100)
  PAIR_URL      — URL do Pair Backend (default: http://localhost:8002)
  JWT_SECRET    — Segredo JWT para autenticação (default: from .env)
  WORKSPACE_ID  — Workspace ID (default: default)
  OUTPUT_CSV    — Arquivo de saída (default: resultados.csv)
"""
import asyncio
import csv
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import httpx
import jwt

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
MCP_URL = os.getenv("MCP_URL", "http://localhost:3100")
PAIR_URL = os.getenv("PAIR_URL", "http://localhost:8002")
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError(
        "JWT_SECRET não configurado. "
        "Gere com: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
    )
WORKSPACE_ID = os.getenv("WORKSPACE_ID", "default")
OUTPUT_FILE = os.getenv("OUTPUT_CSV", "resultados.csv")

# Rate limiting entre chamadas ao Pair Backend (segundos)
PAIR_DELAY = 1.0
# Timeout para chamadas ao MCP Server (Google Maps pode ser lento)
MCP_TIMEOUT = 120.0
# Timeout para chamadas ao Pair Backend
PAIR_TIMEOUT = 60.0

logger = logging.getLogger("kirin_prospect")

# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------
def generate_token() -> str:
    """Gera token JWT para autenticação no Pair Backend."""
    return jwt.encode(
        {
            "sub": "prospect-script",
            "workspace_id": WORKSPACE_ID,
            "exp": datetime.now(tz=timezone.utc) + timedelta(days=30),
        },
        JWT_SECRET,
        algorithm="HS256",
    )

# ---------------------------------------------------------------------------
# MCP Server — busca de leads
# ---------------------------------------------------------------------------
async def search_leads(
    query: str, location: str = "", limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Chama o MCP Server para buscar estabelecimentos no Google Maps.

    Args:
        query: Termo de busca (ex: "padarias")
        location: Localização (ex: "Pinheiros, São Paulo")
        limit: Número máximo de resultados

    Returns:
        Lista de dicts com name, address, phone, rating, google_maps_url
    """
    async with httpx.AsyncClient(timeout=MCP_TIMEOUT) as client:
        resp = await client.post(
            f"{MCP_URL}/tools/search_google_maps",
            json={"arguments": {"query": query, "location": location, "limit": limit}},
        )
        resp.raise_for_status()
        body = resp.json()
        # MCP Server retorna {"result": [...]} ou {"result": {"error_code": ...}}
        result = body.get("result", [])
        if isinstance(result, dict) and "error_code" in result:
            logger.error(f"MCP Server retornou erro: {result}")
            return []
        return result if isinstance(result, list) else []

# ---------------------------------------------------------------------------
# Mapeamento de campos
# ---------------------------------------------------------------------------
def map_lead_for_pair(place: Dict[str, Any]) -> Dict[str, Any]:
    """
    Mapeia campos da saída do MCP Server para o payload do Pair Backend.

    MCP Server retorna:
      {name, address, phone, rating, google_maps_url}

    Pair Backend espera (Dict[str, Any]) com pelo menos:
      {name, company, title, phone, email}
    """
    return {
        "lead": {
            "name": place.get("name", ""),
            "company": place.get("name", ""),
            "title": "Proprietário",
            "phone": place.get("phone", ""),
            "email": "",
        },
        # Campos extras úteis para enriquecimento/scoring
        "google_maps_data": {
            "address": place.get("address"),
            "rating": place.get("rating"),
            "google_maps_url": place.get("google_maps_url"),
        },
    }

# ---------------------------------------------------------------------------
# Pair Backend — processamento
# ---------------------------------------------------------------------------
async def process_lead(
    client: httpx.AsyncClient, token: str, payload: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Envia um lead para processamento no Pair Backend.

    Args:
        client: httpx AsyncClient reutilizado
        token: JWT token
        payload: Payload no formato do Pair Backend

    Returns:
        Resposta do Pair Backend (lead processado + mensagem)
    """
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post(
        f"{PAIR_URL}/prospect/process",
        json=payload,
        headers=headers,
    )
    resp.raise_for_status()
    return resp.json()

# ---------------------------------------------------------------------------
# Orquestração principal
# ---------------------------------------------------------------------------
async def run(
    query: str, location: str = "", limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Executa o pipeline completo: busca → mapeamento → processamento → CSV.

    Args:
        query: Termo de busca no Google Maps
        location: Localização para a busca
        limit: Número máximo de leads

    Returns:
        Lista de resultados processados
    """
    token = generate_token()
    logger.info(f"🔍 Buscando leads: '{query}' (local: '{location}', limite: {limit})")

    # 1. Buscar leads no Google Maps via MCP Server
    places = await search_leads(query, location, limit)
    if not places:
        logger.warning("Nenhum lead encontrado. Verifique se o MCP Server está rodando.")
        return []

    logger.info(f"📍 Encontrados {len(places)} leads")

    # 2. Processar cada lead no Pair Backend
    results: List[Dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=PAIR_TIMEOUT) as client:
        for i, place in enumerate(places):
            place_name = place.get("name", "desconhecido")
            payload = map_lead_for_pair(place)

            try:
                result = await process_lead(client, token, payload)
                lead_data = result.get("lead", {})
                msg_data = result.get("outreach_message", {})

                results.append({
                    "nome": place.get("name"),
                    "telefone": place.get("phone"),
                    "endereco": place.get("address"),
                    "avaliacao": place.get("rating"),
                    "pontuacao": lead_data.get("score", ""),
                    "faixa": lead_data.get("faixa", ""),
                    "mensagem": msg_data.get("content", ""),
                    "status": "ok",
                })
                logger.info(
                    f"  ✅ [{i+1}/{len(places)}] {place_name} — "
                    f"score={lead_data.get('score', '?')} faixa={lead_data.get('faixa', '?')}"
                )

            except httpx.HTTPStatusError as e:
                logger.error(f"  ❌ [{i+1}/{len(places)}] {place_name} — HTTP {e.response.status_code}")
                results.append(_error_row(place, f"HTTP {e.response.status_code}"))
            except httpx.ConnectError:
                logger.error(
                    f"  ❌ [{i+1}/{len(places)}] {place_name} — "
                    "Não foi possível conectar ao Pair Backend. Verifique se ele está rodando."
                )
                results.append(_error_row(place, "Pair Backend indisponível"))
                # Se o Pair Backend caiu, parar o loop
                break
            except Exception as e:
                logger.error(f"  ❌ [{i+1}/{len(places)}] {place_name} — {e}")
                results.append(_error_row(place, str(e)))

            # Rate limiting entre chamadas
            if i < len(places) - 1:
                await asyncio.sleep(PAIR_DELAY)

    # 3. Salvar CSV
    _save_csv(results)

    # Resumo
    ok_count = sum(1 for r in results if r["status"] == "ok")
    err_count = len(results) - ok_count
    logger.info(f"\n📊 Resumo: {ok_count} processados, {err_count} erros, total {len(results)}")
    logger.info(f"📄 CSV salvo em: {OUTPUT_FILE}")

    return results

def _error_row(place: Dict[str, Any], error: str) -> Dict[str, Any]:
    """Cria uma linha de resultado para lead com erro."""
    return {
        "nome": place.get("name"),
        "telefone": place.get("phone"),
        "endereco": place.get("address"),
        "avaliacao": place.get("rating"),
        "pontuacao": "",
        "faixa": "",
        "mensagem": "",
        "status": f"erro: {error}",
    }

def _save_csv(results: List[Dict[str, Any]]) -> None:
    """Salva resultados em CSV."""
    fieldnames = [
        "nome", "telefone", "endereco", "avaliacao",
        "pontuacao", "faixa", "mensagem", "status",
    ]
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    """Entry point para uso via CLI."""
    if len(sys.argv) < 2:
        print(__doc__)
        print("Exemplos:")
        print('  python kirin_prospect.py "padarias em Pinheiros" "" 10')
        print('  python kirin_prospect.py "clínicas de estética" "Campinas" 20')
        sys.exit(1)

    query = sys.argv[1]
    location = sys.argv[2] if len(sys.argv) > 2 else ""
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 10

    asyncio.run(run(query, location, limit))

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    main()
