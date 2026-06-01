# Spec: Fork 2 — Kirin Lite (Serverless / Single-File Runtime)

**Status:** Proposta  
**Prioridade:** Alta — primeiro fork a implementar  
**Esforço estimado:** 1 semana (equipe de 2)  
**Viabilidade:** 95%

---

## 1. Problema

O Kirin atual exige Docker Compose com 9 serviços (FastAPI, PostgreSQL, Qdrant, Redis, LiteLLM, n8n, MCP Server, Whisper, Pair Backend). A barreira de entrada impede adoção por:

- Desenvolvedores que querem avaliar o produto em 5 minutos
- Equipes sem infra DevOps
- Casos de uso de baixo volume que não justificam a stack completa
- Ambientes serverless (AWS Lambda, Cloudflare Workers, Vercel)

---

## 2. Objetivo

Criar `kirin-lite` — um runtime de arquivo único, instalável via `pip`, que executa o pipeline completo (extract → enrich → score → message) com **zero dependências de infraestrutura externa**.

```bash
pip install kirin-lite
python -c "from kirin_lite import Kirin; Kirin().run('padarias em Pinheiros', limit=5)"
```

---

## 3. Decisões Arquiteturais

### 3.1 Substituições de Infraestrutura

| Componente original | Substituto no Lite | Justificativa |
|---|---|---|
| PostgreSQL | SQLite (stdlib) | Zero instalação, suficiente para <100k leads |
| Redis | `dict` com TTL manual (`time.time()`) | Elimina dependência de rede |
| Qdrant | `numpy` + busca linear por cosseno | Vetores em memória, sem servidor |
| LiteLLM server | Chamada direta à API do provider | Remove hop de rede |
| Docker Compose | Processo único Python | `uvicorn` opcional |
| n8n | Não incluído — fora do escopo Lite | Orquestração externa é responsabilidade do usuário |

### 3.2 Modos de Operação

```
kirin-lite opera em 3 modos:

1. LIBRARY   — importado como módulo Python, sem servidor
2. CLI        — `kirin run "query" --limit 10 --output leads.csv`
3. API        — `kirin serve --port 8080` (FastAPI mínimo, sem auth)
```

### 3.3 Compatibilidade com Kirin Full

- O `kirin-lite` **não substitui** o Kirin Full — é uma porta de entrada
- Payloads são idênticos: um lead processado no Lite pode ser importado no Full
- A migração é feita trocando as variáveis de ambiente (`KIRIN_BACKEND=full`)

---

## 4. Estrutura de Arquivos

```
kirin/
└── kirin-lite/
    ├── kirin_lite/
    │   ├── __init__.py          # API pública: class Kirin
    │   ├── runtime.py           # Substitutos de PostgreSQL/Redis/Qdrant
    │   ├── pipeline.py          # Orquestra enrich→score→message (reusa agents/)
    │   ├── llm.py               # Cliente LLM direto (sem LiteLLM server)
    │   ├── cli.py               # Entrypoint CLI
    │   └── server.py            # FastAPI mínimo (opcional)
    ├── pyproject.toml
    └── README.md
```

**Arquivos do Kirin Full reutilizados sem modificação:**
- `agents/enricher.py` — função `enrich_lead()` é agnóstica à camada de memória
- `agents/scorer.py` — idem
- `agents/messenger.py` — função `generate_message()` é agnóstica
- `agents/pure_functions.py` — funções puras, zero dependências
- `agents/resonance.py` — análise de linguagem, zero dependências de infra

---

## 5. Contratos de Interface

### 5.1 API Pública (modo library)

```python
from kirin_lite import Kirin

# Configuração mínima — tudo tem default
k = Kirin(
    llm_provider="deepseek",          # ou "openai", "ollama", "anthropic"
    llm_api_key="sk-...",             # ou via env KIRIN_LLM_API_KEY
    storage="sqlite",                 # ou "memory" (sem persistência)
    sqlite_path="./kirin.db",         # default: ~/.kirin/kirin.db
)

# Uso básico
leads = k.enrich([
    {"name": "Padaria Central", "phone": "11999999999", "address": "Rua X, 100"}
])

for lead in leads:
    print(lead.score, lead.faixa, lead.message)

# Pipeline completo
results = k.run(
    query="padarias em Pinheiros",    # busca no Google Maps via MCP (opcional)
    leads=[...],                       # ou passa leads diretamente
    limit=10,
    send_whatsapp=False,               # default: False no Lite
)
```

### 5.2 CLI

```bash
# Processar leads de um CSV
kirin run --input leads.csv --output results.csv --llm deepseek

# Buscar + processar (requer MCP Server rodando)
kirin run --query "clínicas em Campinas" --limit 20

# Iniciar servidor API
kirin serve --port 8080 --storage sqlite
```

### 5.3 API REST (modo server)

Subconjunto dos endpoints do Kirin Full — mesmos schemas, sem auth:

```
POST /enrich          → agents/schemas.py::EnrichRequest (idêntico)
POST /score           → agents/schemas.py::ScoreRequest (idêntico)
POST /generate_message → agents/schemas.py::MessageRequest (idêntico)
GET  /health
```

---

## 6. Implementação do Runtime Lite

### 6.1 `kirin_lite/runtime.py` — Substitutos de Infraestrutura

```python
# kirin_lite/runtime.py
import sqlite3, time, json, math
from typing import Optional

class LiteStorage:
    """SQLite como substituto de PostgreSQL + Redis."""

    def __init__(self, path: str = ":memory:"):
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS memory "
            "(lead_id TEXT, type TEXT, data TEXT, ts REAL, ttl REAL)"
        )
        self._db.commit()

    def store(self, lead_id: str, memory_type: str, data: dict, ttl: float = 0) -> None:
        self._db.execute(
            "INSERT OR REPLACE INTO memory VALUES (?,?,?,?,?)",
            (lead_id, memory_type, json.dumps(data), time.time(), ttl)
        )
        self._db.commit()

    def get(self, lead_id: str, memory_type: str) -> Optional[dict]:
        row = self._db.execute(
            "SELECT data, ts, ttl FROM memory WHERE lead_id=? AND type=?",
            (lead_id, memory_type)
        ).fetchone()
        if not row:
            return None
        data, ts, ttl = row
        if ttl > 0 and time.time() - ts > ttl:
            return None  # expirado
        return json.loads(data)


class LiteVectorStore:
    """Busca vetorial em memória — substituto do Qdrant."""

    def __init__(self):
        self._vectors: list[tuple[list[float], dict]] = []

    def upsert(self, vector: list[float], metadata: dict) -> None:
        self._vectors.append((vector, metadata))

    def search(self, query: list[float], limit: int = 5) -> list[dict]:
        def cosine(a, b):
            dot = sum(x * y for x, y in zip(a, b))
            na = math.sqrt(sum(x**2 for x in a))
            nb = math.sqrt(sum(x**2 for x in b))
            return dot / (na * nb) if na and nb else 0.0

        scored = sorted(self._vectors, key=lambda v: cosine(query, v[0]), reverse=True)
        return [meta for _, meta in scored[:limit]]
```

### 6.2 `kirin_lite/llm.py` — Cliente LLM Direto

```python
# kirin_lite/llm.py
import httpx, os

PROVIDERS = {
    "deepseek": "https://api.deepseek.com/v1/chat/completions",
    "openai":   "https://api.openai.com/v1/chat/completions",
    "ollama":   "http://localhost:11434/v1/chat/completions",  # local, zero custo
}

async def complete(prompt: str, provider: str = "deepseek", api_key: str = "") -> str:
    url = PROVIDERS[provider]
    model = {"deepseek": "deepseek-chat", "openai": "gpt-4o-mini", "ollama": "llama3.2"}[provider]
    headers = {"Authorization": f"Bearer {api_key or os.getenv('KIRIN_LLM_API_KEY', '')}"}
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 1000}

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(url, json=payload, headers=headers)
        r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]
```

### 6.3 `kirin_lite/pipeline.py` — Orquestrador

```python
# kirin_lite/pipeline.py
# Reusa agents/ diretamente — sem modificação nos agentes originais

import asyncio
from agents.enricher import enrich_lead
from agents.scorer import score_lead
from agents.messenger import generate_message
from .runtime import LiteStorage
from .llm import complete

async def run_pipeline(leads: list[dict], config: dict) -> list[dict]:
    storage = config.get("storage") or LiteStorage()
    llm_url  = config.get("llm_url", "https://api.deepseek.com")
    api_key  = config.get("api_key", "")

    results = []
    for lead in leads:
        lead = await enrich_lead(lead, llm_url, api_key)
        lead = await score_lead(lead.get("dossie", {}), llm_url, api_key)
        lead["message"] = await generate_message(lead, llm_url, api_key)

        if lead.get("id"):
            storage.store(lead["id"], "pipeline_result", lead)

        results.append(lead)
    return results
```

---

## 7. Configuração e Variáveis de Ambiente

```bash
# Mínimo obrigatório
KIRIN_LLM_API_KEY=sk-...

# Opcionais (todos têm default)
KIRIN_LLM_PROVIDER=deepseek        # deepseek | openai | ollama
KIRIN_STORAGE=sqlite               # sqlite | memory
KIRIN_SQLITE_PATH=~/.kirin/kirin.db
KIRIN_LOG_LEVEL=WARNING            # reduzido no Lite
```

---

## 8. `pyproject.toml`

```toml
[project]
name = "kirin-lite"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "httpx>=0.27",
    "fastapi>=0.111",    # opcional, só para modo server
    "uvicorn>=0.29",     # opcional, só para modo server
    "typer>=0.12",       # CLI
]

[project.scripts]
kirin = "kirin_lite.cli:app"

[project.optional-dependencies]
server = ["fastapi>=0.111", "uvicorn>=0.29"]
```

Sem PostgreSQL, Redis, Qdrant, Docker — instalação em ~5 segundos.

---

## 9. Caminho de Migração: Lite → Full

```python
# Lite (desenvolvimento/validação)
from kirin_lite import Kirin
k = Kirin(llm_api_key="sk-...")

# Full (produção) — mesma API, troca de backend
from kirin_lite import Kirin
k = Kirin(
    backend="full",
    full_url="http://kirin-core:8001",  # aponta para kirin-core
    tenant_id="minha_empresa",
)
# Todos os métodos (run, enrich, score) delegam para o Full via HTTP
```

---

## 10. Critérios de Aceitação

- [ ] `pip install kirin-lite` funciona em ambiente limpo (Python 3.11+, sem Docker)
- [ ] `kirin run --input leads.csv` processa 10 leads em menos de 60s
- [ ] Modo `memory` (sem SQLite) funciona sem criar nenhum arquivo em disco
- [ ] Modo `ollama` funciona sem nenhuma chave de API paga
- [ ] Schemas de entrada/saída são idênticos aos do Kirin Full (compatibilidade de payload)
- [ ] `kirin serve` expõe `/enrich`, `/score`, `/generate_message` com mesmos contratos do Full

---

## 11. O que NÃO está no escopo do Lite

- Multi-tenancy (sem isolamento de dados entre usuários)
- Auth / API keys
- Métricas Prometheus
- Pesquisa profunda (`/research`) — requer Qdrant real para escala
- Envio real de WhatsApp (geração de mensagem sim, envio não — evita uso acidental)
- n8n / orquestração de workflows
