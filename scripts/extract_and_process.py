"""
Script de extração e processamento de leads.

Fluxo:
  1. Chama MCP Server (/tools/search_google_maps) para extrair leads do Google Maps
  2. Para cada lead, encadeia: /enrich -> /score -> /generate_message no Kirin
  3. Salva resultados em CSV com nome, telefone, score, faixa e mensagem

Uso:
  # Extrair 10 padarias em Pinheiros
  python scripts/extract_and_process.py --query "padarias" --location "Pinheiros, SP" --limit 10

  # Usar MCP e Kirin em hosts diferentes
  python scripts/extract_and_process.py --query "clinicas estetica" --location "Campinas" \
      --mcp-url http://localhost:3100 --kirin-url http://localhost:8000 --limit 5
"""

import argparse
import asyncio
import csv
import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

# ── Config ────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("extract_and_process")

DEFAULT_MCP_URL = "http://localhost:3100"
DEFAULT_KIRIN_URL = "http://localhost:8000"
DEFAULT_LIMIT = 10
REQUEST_TIMEOUT = 120.0  # 2 minutos para cada chamada


# ── Data Classes ──────────────────────────────────────────────────────────────

class LeadResult:
    """Resultado consolidado de um lead processado."""

    def __init__(self, place: Dict[str, Any]):
        self.place = place
        self.name: str = place.get("name", "")
        self.phone: str = place.get("phone", "") or ""
        self.address: str = place.get("address", "") or ""
        self.rating: Optional[float] = place.get("rating")
        self.google_maps_url: str = place.get("google_maps_url", "") or ""

        # Preenchido pelo pipeline
        self.enriched: Optional[Dict[str, Any]] = None
        self.scored: Optional[Dict[str, Any]] = None
        self.message: Optional[str] = None

        # Estado
        self.status = "ok"
        self.error_step: Optional[str] = None
        self.error_detail: Optional[str] = None

    def mark_error(self, step: str, detail: str) -> None:
        self.status = f"erro: {step}"
        self.error_step = step
        self.error_detail = detail

    @property
    def score(self) -> int:
        if self.scored:
            return self.scored.get("score", 0)
        return 0

    @property
    def faixa(self) -> str:
        if self.scored:
            return self.scored.get("faixa", "")
        return ""


# ── MCP Client ────────────────────────────────────────────────────────────────

async def search_google_maps(
    client: httpx.AsyncClient,
    mcp_url: str,
    query: str,
    location: str = "",
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """
    Busca estabelecimentos no Google Maps via MCP Server.

    Args:
        client: Sessão HTTP compartilhada.
        mcp_url: URL base do MCP Server.
        query: Termo de busca (ex.: "padarias", "clinicas de estetica").
        location: Localização (ex.: "Pinheiros, SP", "Campinas").
        limit: Máximo de resultados.

    Returns:
        Lista de estabelecimentos encontrados.

    Raises:
        httpx.HTTPError: Se a chamada ao MCP falhar.
        ValueError: Se a resposta veio com erro estruturado.
    """
    logger.info(f"Buscando '{query}' em '{location}' (limite={limit})...")

    payload = {
        "arguments": {
            "query": query,
            "location": location,
            "limit": limit,
        }
    }

    response = await client.post(
        f"{mcp_url}/tools/search_google_maps",
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()

    data = response.json()
    result = data.get("result", [])

    # Verifica se veio erro estruturado do MCP
    if isinstance(result, dict) and "error_code" in result:
        raise ValueError(
            f"MCP error: {result.get('error_code')} - {result.get('error_message')}"
        )

    if not isinstance(result, list):
        logger.warning(f"Resposta inesperada do MCP (não é lista): {type(result)}")
        return []

    logger.info(f"Encontrados {len(result)} estabelecimentos")
    return result


# ── Kirin Pipeline ─────────────────────────────────────────────────────────────

async def enrich_lead(
    client: httpx.AsyncClient,
    kirin_url: str,
    lead_data: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Enriquece um lead via /enrich."""
    try:
        response = await client.post(
            f"{kirin_url}/enrich",
            json=lead_data,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        logger.warning(f"Falha no enrich para {lead_data.get('name', '?'):.30s}: {e}")
        return None


async def score_lead(
    client: httpx.AsyncClient,
    kirin_url: str,
    lead_data: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Pontua um lead via /score.

    O /score espera receber o dossiê aninhado em 'dossie'.
    Monta o payload com os dados do lead + dossiê do enrich.
    """
    try:
        response = await client.post(
            f"{kirin_url}/score",
            json=lead_data,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        logger.warning(f"Falha no score para {lead_data.get('name', '?'):.30s}: {e}")
        return None


async def generate_message(
    client: httpx.AsyncClient,
    kirin_url: str,
    lead_data: Dict[str, Any],
) -> Optional[str]:
    """Gera mensagem WhatsApp via /generate_message.

    Retorna None se o score for < 20 (lead descartado).
    """
    try:
        response = await client.post(
            f"{kirin_url}/generate_message",
            json=lead_data,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("message")
    except httpx.HTTPError as e:
        logger.warning(f"Falha no generate_message para {lead_data.get('name', '?'):.30s}: {e}")
        return None


# ── Processamento ─────────────────────────────────────────────────────────────

async def process_lead(
    client: httpx.AsyncClient,
    kirin_url: str,
    place: Dict[str, Any],
) -> LeadResult:
    """
    Processa um lead completo: enrich -> score -> generate_message.

    Args:
        client: Sessão HTTP compartilhada.
        kirin_url: URL base do Kirin Agents API.
        place: Estabelecimento retornado pelo MCP.

    Returns:
        LeadResult com o resultado de cada etapa.
    """
    result = LeadResult(place)
    name = place.get("name", "desconhecido")

    # ── 1. Enrich ──────────────────────────────────────────────────────────
    logger.info(f"  [{name:.40s}] Enriquecendo...")
    enriched = await enrich_lead(client, kirin_url, place)
    if enriched is None:
        result.mark_error("enrich", "falha na chamada HTTP")
        return result

    if not enriched.get("enrichment_success"):
        error_msg = enriched.get("enrichment_error", "motivo desconhecido")
        logger.warning(f"  [{name:.40s}] Enrich falhou: {error_msg}")
        result.mark_error("enrich", error_msg)
        # Continua com dossiê vazio mesmo assim (o scorer tem fallback)

    result.enriched = enriched
    logger.info(f"  [{name:.40s}] Enrich OK")

    # ── 2. Score ────────────────────────────────────────────────────────────
    # Monta payload: passa o dossiê + dados básicos para o scorer
    score_payload = {
        "id": place.get("id", ""),
        "name": place.get("name", ""),
        "address": place.get("address", ""),
        "phone": place.get("phone", ""),
        "website": place.get("website", ""),
        "instagram_username": place.get("instagram_username", ""),
        "rating": place.get("rating"),
        "google_maps_url": place.get("google_maps_url", ""),
    }

    # Pega dossiê do enriched se existir
    if enriched and enriched.get("dossie"):
        score_payload["dossie"] = enriched["dossie"]
    else:
        # Dossiê vazio para fallback
        score_payload["dossie"] = {
            "resumo_perfil": "",
            "pontos_fracos": [],
            "oportunidades": [],
            "maturidade_digital": "médio",
        }

    logger.info(f"  [{name:.40s}] Pontuando...")
    scored = await score_lead(client, kirin_url, score_payload)
    if scored is None:
        result.mark_error("score", "falha na chamada HTTP")
        return result

    result.scored = scored
    logger.info(f"  [{name:.40s}] Score: {scored.get('score', '?')}/100 ({scored.get('faixa', '?')})")

    # ── 3. Generate Message ─────────────────────────────────────────────────
    # Se score >= 20, gera mensagem
    current_score = scored.get("score", 0)
    if current_score >= 20:
        # Monta payload completo para o messenger
        msg_payload = score_payload.copy()
        msg_payload.update({
            "score": current_score,
            "faixa": scored.get("faixa", ""),
            "score_justification": scored.get("score_justification", ""),
        })

        logger.info(f"  [{name:.40s}] Gerando mensagem...")
        message = await generate_message(client, kirin_url, msg_payload)
        result.message = message

        if message:
            logger.info(f"  [{name:.40s}] Mensagem gerada ({len(message)} chars)")
        else:
            logger.info(f"  [{name:.40s}] Mensagem NAO gerada (score {current_score} >= 20, mas retornou None)")
    else:
        logger.info(f"  [{name:.40s}] Score {current_score} < 20: descartado, sem mensagem")

    return result


# ── CSV ───────────────────────────────────────────────────────────────────────

CSV_HEADERS = [
    "nome",
    "telefone",
    "endereco",
    "avaliacao",
    "google_maps_url",
    "pontuacao",
    "faixa",
    "mensagem",
    "status",
    "erro_detalhe",
]


def lead_to_row(result: LeadResult) -> Dict[str, Any]:
    """Converte LeadResult em linha para CSV."""
    return {
        "nome": result.name,
        "telefone": result.phone if result.phone else "",
        "endereco": result.address if result.address else "",
        "avaliacao": result.rating if result.rating is not None else "",
        "google_maps_url": result.google_maps_url,
        "pontuacao": result.score if result.status == "ok" else "",
        "faixa": result.faixa if result.status == "ok" else "",
        "mensagem": (result.message or "") if result.status == "ok" else "",
        "status": result.status,
        "erro_detalhe": result.error_detail or "",
    }


def save_csv(results: List[LeadResult], output_path: str) -> None:
    """
    Salva resultados em CSV.

    Args:
        results: Lista de resultados processados.
        output_path: Caminho do arquivo CSV.
    """
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        for r in results:
            writer.writerow(lead_to_row(r))

    logger.info(f"Resultados salvos em: {output_path}")

    # Summary
    ok = sum(1 for r in results if r.status == "ok")
    errors = len(results) - ok
    com_msg = sum(1 for r in results if r.message)
    logger.info(f"Resumo: {len(results)} leads, {ok} OK, {errors} erro(s), {com_msg} mensagens geradas")


# ── Main ───────────────────────────────────────────────────────────────────────

async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extrai leads do Google Maps e processa pelo Kirin pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  %(prog)s --query "padarias" --location "Pinheiros, SP" --limit 5
  %(prog)s --query "clinicas estetica" --location "Campinas" --mcp-url http://mcp:3100 --kirin-url http://agents:8000
  %(prog)s --query "restaurantes" --location "Centro, RJ" --limit 20 --output leads_rio.csv
        """,
    )
    parser.add_argument("--query", "-q", required=True, help="Termo de busca (ex.: padarias)")
    parser.add_argument("--location", "-l", default="", help="Localização (ex.: Pinheiros, SP)")
    parser.add_argument("--limit", "-n", type=int, default=DEFAULT_LIMIT, help=f"Máximo de leads (default: {DEFAULT_LIMIT})")
    parser.add_argument("--mcp-url", default=os.getenv("MCP_URL", DEFAULT_MCP_URL), help=f"URL do MCP Server (default: {DEFAULT_MCP_URL})")
    parser.add_argument("--kirin-url", default=os.getenv("KIRIN_URL", DEFAULT_KIRIN_URL), help=f"URL do Kirin Agents API (default: {DEFAULT_KIRIN_URL})")
    parser.add_argument("--output", "-o", default="", help="Caminho do CSV de saída (default: resultados_<query>_<location>.csv)")

    args = parser.parse_args()

    # Determina nome do arquivo de saída
    if not args.output:
        safe_query = args.query.replace(" ", "_")[:20]
        safe_loc = args.location.replace(" ", "_")[:15] if args.location else "sem_local"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = f"resultados_{safe_query}_{safe_loc}_{timestamp}.csv"

    logger.info("=" * 60)
    logger.info(f"Kirin - Extrator e Processador de Leads")
    logger.info(f"Query: '{args.query}' | Local: '{args.location}' | Limite: {args.limit}")
    logger.info(f"MCP: {args.mcp_url} | Kirin: {args.kirin_url}")
    logger.info(f"Output: {args.output}")
    logger.info("=" * 60)

    async with httpx.AsyncClient() as client:
        # ── 1. Extrair leads do Google Maps ────────────────────────────────
        try:
            places = await search_google_maps(
                client, args.mcp_url, args.query, args.location, args.limit
            )
        except (httpx.HTTPError, ValueError) as e:
            logger.error(f"Falha na extração do Google Maps: {e}")
            logger.error("Verifique se o MCP Server está rodando em " + args.mcp_url)
            sys.exit(1)

        if not places:
            logger.warning("Nenhum estabelecimento encontrado.")
            sys.exit(0)

        # ── 2. Processar cada lead ─────────────────────────────────────────
        results: List[LeadResult] = []
        total = len(places)
        start_time = time.time()

        for i, place in enumerate(places, 1):
            name = place.get("name", "desconhecido")[:50]
            logger.info(f"\n[{i}/{total}] Processando: {name}")

            result = await process_lead(client, args.kirin_url, place)
            results.append(result)

            # Pequena pausa entre leads para não sobrecarregar
            if i < total:
                await asyncio.sleep(1)

        elapsed = time.time() - start_time

        # ── 3. Salvar resultados ───────────────────────────────────────────
        save_csv(results, args.output)

        logger.info(f"\nTempo total: {elapsed:.1f}s ({elapsed/len(results):.1f}s por lead)")
        logger.info("Processamento concluído!")


if __name__ == "__main__":
    asyncio.run(main())
