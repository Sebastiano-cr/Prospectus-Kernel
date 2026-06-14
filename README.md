# Kirin Platform

Cognitive runtime platform para prospecção B2B com análise wittgensteiniana de discurso.

## Overview

Dois pipelines principais:

**Pipeline 1 — Prospecção B2B:**
1. **Enricher** — Gera dossiê do lead via Qwen VL Max (nome, pontos fracos, maturidade digital)
2. **Scorer** — Pontua 0-100 via DeepSeek, classifica em frio/morno/quente
3. **Messenger** — Gera e envia mensagem WhatsApp personalizada via Evolution API ou OpenWA
4. **Researcher** — Pesquisa fontes externas via Moonshot Kimi K2 (score ≥ 70)
5. **CRM Sync** — Sincroniza com Notion, Airtable ou NocoDB

**Pipeline 2 — Inteligência de Discurso (Language Games):**
1. **Ingestão** — Normaliza discurso bruto em DiscourseFragment (emotion, topic, context)
2. **Language Game** — Análise wittgensteiniana: 14 campos (belief, fear, desire, objection, identity, tension...)
3. **Resonance** — Clusterização de padrões entre fragmentos (high/low resonance, hooks)
4. **Prospect** — Geração de perfil de prospect com narrativa e ângulo de abordagem

Armazenamento único: **ChromaDB** (persistência vetorial + cache LRU em memória + dedup).

## Arquitetura

```
┌─────────────────────────────────────────────────────────┐
│                    Pipeline 1 — Prospecção               │
│  ┌──────────┐   ┌────────┐   ┌───────────┐   ┌────────┐│
│  │ Enricher │──▶│ Scorer │──▶│ Messenger │──▶│Research││
│  │ Qwen VL  │   │DeepSeek│   │ DeepSeek  │   │  Kimi  ││
│  └──────────┘   └────────┘   └─────┬─────┘   │  128k  ││
│                                    │         └────────┘│
│                                    ▼                    │
│                           ┌──────────────┐              │
│                           │   WhatsApp   │              │
│                           │   Evolution  │              │
│                           │   / OpenWA   │              │
│                           └──────────────┘              │
├─────────────────────────────────────────────────────────┤
│              Pipeline 2 — Discourse Intelligence         │
│  ┌──────────┐   ┌──────────────┐   ┌──────────┐        │
│  │ Ingest   │──▶│ Language     │──▶│Resonance │        │
│  │ LLM      │   │ Game (LLM)   │   │ Engine   │        │
│  └──────────┘   └──────────────┘   └────┬─────┘        │
│                                         ▼               │
│                                ┌──────────────────┐     │
│                                │  Prospect Profile│     │
│                                │ + Narrative      │     │
│                                └──────────────────┘     │
├─────────────────────────────────────────────────────────┤
│                    Storage Layer                         │
│  ┌──────────────────────────────────────────────┐       │
│  │              ChromaStore                      │       │
│  │  • Persistência vetorial (ChromaDB)          │       │
│  │  • Cache LRU em memória (TTL configurável)   │       │
│  │  • Dedup via hash                            │       │
│  └──────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────┘
```

## Componentes

### Agentes (Pipeline 1)

| Agente | Modelo | Função |
|---|---|---|
| **Enricher** | Qwen VL Max | Gera dossiê: resumo_perfil, pontos_fracos, oportunidades, maturidade_digital |
| **Scorer** | DeepSeek Chat | Score 0-100 + faixa (frio ≤39, morno 40-69, quente ≥70) |
| **Messenger** | DeepSeek Chat | Mensagem WhatsApp personalizada (≤300 chars) + templates fallback |
| **Researcher** | Moonshot Kimi K2 128k | Pesquisa fontes externas (notícias, blogs, redes sociais) |

### Discourse Intelligence (Pipeline 2)

| Camada | Função | Saída |
|---|---|---|
| **Ingestion** | Normaliza discurso bruto | `DiscourseFragment` (text, source, emotion, topic) |
| **Language Game** | Análise wittgensteiniana | `LanguageGameAnalysis` (14 campos: belief, fear, desire, objection, tension...) |
| **Resonance** | Clusterização de padrões | `ResonanceCluster` (high/low patterns, hooks, belief_density) |
| **Prospect** | Perfil de prospect | `ProspectProfile` (belief, identity, narrative, outreach_angle, confidence) |

### SkepticAgent

Mecanismo de abdução que avalia outputs dos LLMs com 7 heurísticas (H1-H7):
- H1: Score vs dossier mismatch
- H2: Generic message detection
- H3: Fake source URLs
- H4: Language deviation (PT-BR vs EN)
- H5: Suspicious length
- H6: Maturity incoherence
- H7: Emotion inconsistency

### ChromaStore

Substitui PostgreSQL + Qdrant + Redis por um banco único:

```python
from src.store import ChromaStore

store = ChromaStore(path="./data/chroma")
await store.initialize()

# Persistência
await store.store_lead_memory("lead_123", "dossie", dossie)

# Busca vetorial
results = await store.search_text("kirin_discourse", "crenças sobre preço", limit=5)

# Cache LRU com TTL
await store.cache_set("daily_count:2026-06-13", 42, ttl_seconds=86400)
count = await store.cache_get("daily_count:2026-06-13")

# Dedup
if not await store.check_duplicate(hash_key):
    await store.store_dedup(hash_key, data)
```

### LocalePort (i18n)

Integrado em todos os agentes. Controlado via env var `LOCALE` (default `pt-BR`).

```python
from src.locale import get_locale

locale = get_locale("pt-BR")  # ou "es" (precisa adapter)
prompt = locale.get_prompt("enricher", name="Clínica", address="...")
field = locale.get_field_name("profile_summary")  # → "resumo_perfil"
faixa = locale.get_score_category(72)  # → "quente"
```

Agentes com locale integrado:
- **Enricher** — prompt, fallbacks, field names
- **Scorer** — prompt, score category, fallbacks
- **Messenger** — prompt, template fallback, opt-out, status
- **Researcher** — prompt, status, field names
- **SkepticAgent** — heurísticas H2/H4/H6/H7 via locale markers
- **Server** — erros HTTP localizados (env, auth, rate limit, 500s)

## API Endpoints

| Método | Rota | Pipeline | Descrição |
|---|---|---|---|
| POST | `/enrich` | Prospecção | Enriquecer lead com dossiê |
| POST | `/score` | Prospecção | Pontuar lead (requer dossiê) |
| POST | `/generate_message` | Prospecção | Gerar mensagem WhatsApp |
| POST | `/research` | Prospecção | Pesquisar lead (score ≥ 70) |
| POST | `/crm_sync` | Prospecção | Sincronizar com CRM |
| POST | `/discourse/ingest` | Discurso | Ingerir fragmento de discurso |
| POST | `/discourse/extract` | Discurso | Ingestão + Language Game |
| POST | `/resonance/analyze` | Discurso | Clusterizar padrões |
| POST | `/resonance/lookup` | Discurso | Buscar padrões similares |
| POST | `/prospects/generate` | Discurso | Gerar perfil de prospect |
| POST | `/resonance/signal` | Discurso | Registrar sinal de mercado |
| GET | `/health` | — | Health check (ChromaDB) |
| GET | `/metrics` | — | Prometheus metrics |

## Setup

### Pré-requisitos

- Docker e Docker Compose
- Python 3.11+
- API keys: LiteLLM (DeepSeek, Qwen, Moonshot), WhatsApp Evolution API

### Variáveis de Ambiente

```env
# LiteLLM
LITELLM_URL=http://litellm:4000
QWEN_VL_MAX_API_KEY=your_qwen_key
DEEPSEEK_CHAT_API_KEY=your_deepseek_key
MOONSHOT_V1_128K_API_KEY=your_moonshot_key

# WhatsApp
EVOLUTION_API_URL=your_evolution_url
EVOLUTION_API_KEY=your_evolution_key
EVOLUTION_INSTANCE_ID=your_instance_id

# CRM
CRM_PROVIDER=notion  # notion, airtable, nocodb

# Locale
LOCALE=pt-BR

# Storage
CHROMA_PATH=./data/chroma
```

### Docker Compose

```bash
docker-compose up -d
# API em http://localhost:8000
# Docs em http://localhost:8000/docs
```

### Manual

```bash
pip install -r agents/requirements.txt
export LITELLM_URL=http://localhost:4000
# ... outras vars
uvicorn agents.server:app --host 0.0.0.0 --port 8000
```

## Testes

```bash
pytest tests/ -q
# 181 passed
```

Cobertura atual:
- `test_units.py` — Funções puras (normalize_score, classify_faixa, dedup...)
- `test_properties.py` — Testes baseados em Hypothesis (20+ invariantes)
- `test_skeptic_agent.py` — SkepticAgent (7 heurísticas)
- `test_enricher_mock.py` — Mock de LLM para enricher, scorer, messenger
- `test_eval_integration.py` — Eval harness e LLM judge
- `test_llm_judge.py` — Model-graded judges
- `test_store.py` — ChromaStore (CRUD, cache, dedup, search)
- `test_locale.py` — LocalePort (fields, score, status, fallbacks, prompts)
- `test_analysis.py` — Models + templates
- `test_analysis_pipeline.py` — Pipeline parsing/validação/fallback (32 testes)

## Estrutura do Projeto

```
├── agents/
│   ├── server.py              # FastAPI app (endpoints, auth, rate limit)
│   ├── enricher.py            # Enricher Agent
│   ├── scorer.py              # Scorer Agent
│   ├── messenger.py           # Messenger Agent
│   ├── researcher.py          # Researcher Agent
│   ├── skeptic.py             # SkepticAgent (7 heurísticas)
│   ├── factory.py             # ServiceFactory (LLM, WhatsApp)
│   ├── runtime.py             # ChromaStore singleton
│   ├── pure_functions.py      # Funções puras (score, status, truncate)
│   ├── models.py              # Dataclasses (Lead, CampaignConfig)
│   ├── schemas.py             # Pydantic schemas (request validation)
│   ├── crm_connector.py       # CRM adapters (Notion, Airtable, NocoDB)
│   ├── metrics.py             # Prometheus counters/histograms
│   ├── discourse_*.py         # Re-exports from src.analysis
│   ├── ports/
│   │   ├── llm_client.py      # ILLMClient (ABC)
│   │   └── whatsapp_gateway.py # IWhatsAppGateway (ABC)
│   └── adapters/
│       ├── litellm_adapter.py  # LiteLLM → ILLMClient
│       ├── evolution_api_adapter.py  # Evolution → IWhatsAppGateway
│       └── openwa_adapter.py  # OpenWA → IWhatsAppGateway
├── src/
│   ├── store.py               # ChromaStore
│   ├── analysis/
│   │   ├── models.py          # Dataclasses (DiscourseFragment, Analysis...)
│   │   ├── templates.py       # Prompt builders (8 templates)
│   │   ├── analyzer.py        # Ingestão + Language Game
│   │   └── resonance.py       # Resonance Engine + Prospect
│   └── locale/
│       ├── port.py            # LocalePort (ABC)
│       ├── factory.py         # get_locale() (registry pattern)
│       ├── errors.py
│       ├── adapters/
│       │   └── pt_br.py       # PTBRLocaleAdapter (implementação completa)
│       └── prompts/
│           ├── pt-BR/         # 10 templates .prompt.md
│           │   ├── enricher.prompt.md
│           │   ├── scorer.prompt.md
│           │   ├── messenger.prompt.md
│           │   ├── researcher.prompt.md
│           │   ├── discourse_ingestion.prompt.md
│           │   ├── language_game.prompt.md
│           │   ├── resonance.prompt.md
│           │   ├── prospect.prompt.md
│           │   ├── llm_judge_system.prompt.md
│           │   └── llm_judge_criteria.prompt.md
│           └── es/            # Placeholder para expansão
├── eval/
│   ├── kirin_eval_harness.py  # Eval framework (6 dimensões)
│   └── llm_judge.py           # Model-graded judges
├── tests/                     # Test suite (7 arquivos)
├── docker-compose.yml         # 2 serviços (litellm + agents)
└── pyproject.toml
```

## Extending

### Novo Agente
1. Criar módulo em `agents/novo_agente.py`
2. Usar `ServiceFactory.get_llm_client()` ou `get_whatsapp_gateway()`
3. Persistir via `runtime.get_store()`
4. Adicionar endpoint em `server.py`

### Novo Locale
1. Criar `src/locale/adapters/{locale}.py` implementando `LocalePort`
2. Traduzir prompts em `src/locale/prompts/{locale}/*.prompt.md`
3. Registrar via `register_locale("es", ESLocaleAdapter())`

### Nova Fonte de Discurso
1. Adicionar source a `VALID_SOURCES` em `src/analysis/analyzer.py`
2. Ajustar prompts se necessário

## Monitoramento

Métricas Prometheus em `/metrics`:
- `kirin_leads_extracted_total` — Leads extraídos
- `kirin_enrichment_success_total` — Enriquecimentos bem-sucedidos
- `kirin_enrichment_failed_total` — Enriquecimentos falhos
- `kirin_lead_score` — Distribuição de scores
- `kirin_messages_sent_total` — Mensagens por status
- `kirin_errors_total` — Erros por componente
- `kirin_active_leads` — Leads ativos
- `kirin_discourse_ingested_total` — Fragmentos ingeridos
- `kirin_language_game_analyzed_total` — Análises realizadas
- `kirin_resonance_lookup_total` — Consultas de ressonância
- `kirin_prospect_generated_total` — Prospects gerados
