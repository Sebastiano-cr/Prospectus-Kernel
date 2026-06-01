# Processo de Estratificação — Kirin Platform

## Conceito

Cada **estrato** (v0, v1, v2...) representa um estado do sistema que passa
uma bateria específica de testes invariantes. A promoção entre estratos
só ocorre quando **todos os testes do estrato atual + os testes de fronteira
para o próximo estrato** passam.

---

## Estado Atual: v2

```
v0 (original)
 └── fork-a: logging + EVOLUTION_INSTANCE_ID + MemoryFactory + backups
       └── fork-c parcial: schemas Pydantic + conftest + mock tests
             └── ⚠️ server.py: bug de import preexistente (não bloqueante)
```

### O que está em v2

| Componente | Status | Teste de fronteira |
|-----------|--------|-------------------|
| pure_functions.py | ✅ logging adicionado | `pytest tests/test_units.py` (7) |
| enricher.py | ✅ logging adicionado | `from agents.enricher import enrich_lead` |
| scorer.py | ✅ logging adicionado | `from agents.scorer import score_lead` |
| messenger.py | ✅ logging + EVOLUTION_INSTANCE_ID | `from agents.messenger import generate_message, send_whatsapp_message` |
| researcher.py | ✅ logging adicionado | `from agents.researcher import research_lead` |
| runtime.py | ✅ MemoryFactory removida | `from agents.runtime import initialize_memory_managers` |
| memory/__init__.py | ✅ MemoryFactory removida | `from agents.memory import BaseMemoryManager` |
| memory/factory.py | ✅ DEPRECATED stub | Import não quebra |
| agents/__init__.py | ✅ MemoryFactory removida | `from agents import Lead, CampaignConfig` |
| agents/schemas.py | ✅ Novo (Pydantic models) | `from agents.schemas import EnrichRequest` |
| tests/conftest.py | ✅ Novo (fixtures mock) | `pytest tests/test_enricher_mock.py` (10) |
| tests/test_enricher_mock.py | ✅ Novo (10 testes) | `pytest tests/ -v -p no:asyncio` (17) |
| scripts/extract_and_process.py | ✅ Novo (script extração) | `python3 -c "from scripts.extract_and_process import LeadResult"` |
| pyproject.toml | ✅ pytest configurado | Testes ignoram volumes Docker |
| **server.py** | ⚠️ **Import bug preexistente** | Não afeta testes nem módulos importáveis |

---

## Pirâmide de Estratos

```
                    ┌──────────┐
                    │   v6     │  Produção com CI/CD
                    │   🏭     │
                    └────┬─────┘
                         │
                    ┌────┴─────┐
                    │   v5     │  fork-e: Dockerfile + docker-compose + README
                    │   🐳     │
                    └────┬─────┘
                         │
                    ┌────┴─────┐
                    │   v4     │  fork-d: sentence-transformers + embeddings reais
                    │   🧠     │
                    └────┬─────┘
                         │
                    ┌────┴─────┐
                    │   v3     │  server.py corrigido + Kirin Agents funcional
                    │   🚀     │  Script de extração valida pipeline completo
                    └────┬─────┘
                         │
              ╔══════════╧══════════╗
              ║   v2   📌 ATUAL     ║  fork-a + fork-c parcial
              ║   17 testes passam   ║  Schemas, mocks, script criados
              ╚══════════╤══════════╝
                         │
                    ┌────┴─────┐
                    │   v1     │  Código original funcionando
                    │   📦     │
                    └────┬─────┘
                         │
                    ┌────┴─────┐
                    │   v0     │  Estado inicial (antes dos forks)
                    │   🌱     │
                    └──────────┘
```

---

## v3: Correção do server.py + Stack Local Funcional

### Gate de entrada
- ✅ v2 completamente estável (17 testes passando)
- ⏳ Nenhum dos testes novos quebra

### Trabalho necessário

| Tarefa | Arquivo | Ação | Risco |
|--------|---------|------|-------|
| 3.1 | `agents/server.py` | Substituir `from enricher import enrich_lead` → `from agents.enricher import enrich_lead` (e todos os imports análogos) | **Médio** — 14 arquivos usam imports sem `agents.` prefixo. `__init__.py` resolve pelo pacote, mas `server.py` é executado diretamente. |
| 3.2 | `agents/server.py` | Substituir `from .pure_functions` → `from agents.pure_functions` (já feito parcialmente) | Baixo |
| 3.3 | `run_agents.sh` | Testar que o launcher sobe o servidor | Validação manual |
| 3.4 | Validação manual | `curl localhost:8000/health` → `{"status": "healthy"}` | Gate do estrato |

### Invariantes do v3

Todas as invariantes de v1-v2 +:

- **I10**: `GET /health` retorna `{"status": "healthy"}` com status 200
- **I11**: `POST /enrich` com lead válido retorna 200 ou 422, nunca 500
- **I12**: Nenhum import quebrado — `from agents.enricher import enrich_lead` continua funcionando

### Testes de fronteira do v3

```bash
# Teste 1: Servidor sobe
cd /home/vector/Kirin
POSTGRES_HOST=localhost PORT=8000 bash run_agents.sh &
sleep 3
curl -s http://localhost:8000/health | grep -q "healthy" && echo "v3: OK"

# Teste 2: Testes existentes continuam passando
python3 -m pytest tests/ -v -p no:asyncio
# → 17 passed

# Teste 3: Endpoint /enrich responde (pode ser 422 sem dados, mas nunca 500)
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/enrich \
  -H "Content-Type: application/json" -d '{}'
# → 200 ou 422, nunca 500

# Teste 4: Script de extração consegue conectar
python3 scripts/extract_and_process.py --query "teste" --limit 1 --dry-run
```

### Gatilhos de rollback

| Gatilho | Ação |
|---------|------|
| `curl /health` retorna != 200 | Rollback para v2 (reverter server.py) |
| `pytest tests/` falha | Rollback para v2 (não mergear) |
| `from agents.enricher import enrich_lead` quebra | Rollback imediato |

### Esforço estimado

- 30 minutos de edição
- 15 minutos de teste
- **Total: ~45 minutos**

---

## v4: Embeddings Reais (sentence-transformers + Qdrant)

### Gate de entrada
- ✅ v3 estável (Kirin Agents responde)
- ✅ Testes existentes passam

### Trabalho necessário

| Tarefa | Arquivo | Descrição |
|--------|---------|-----------|
| 4.1 | `agents/requirements.txt` | Adicionar `sentence-transformers` |
| 4.2 | `agents/memory/qdrant_memory.py` | Integrar `SentenceTransformer('all-MiniLM-L6-v2')` |
| 4.3 | `agents/memory/qdrant_memory.py` | Substituir placeholder vector aleatório por embedding real |
| 4.4 | `agents/memory/qdrant_memory.py` | Adicionar fallback: se modelo falhar, usa placeholder (zero quebra) |
| 4.5 | Teste de integração | `pytest tests/test_qdrant_embedding.py` (novo) |

### Invariantes do v4

- **I13**: `search_similar_memories` retorna resultados semanticamente relevantes
- **I14**: Se sentence-transformers falhar, comportamento degrada gracefulmente para placeholder
- **I15**: Coleções Qdrant existentes não são recriadas

### Esforço estimado

- **Total: ~2-3 horas**

---

## v5: Dockerfile + docker-compose + README atualizado

### Gate de entrada
- ✅ v4 estável

### Trabalho necessário

| Tarefa | Descrição |
|--------|-----------|
| 5.1 | Atualizar `agents/Dockerfile` para Python 3.13 |
| 5.2 | Consolidar `docker-compose.yml` com variáveis de ambiente dos novos parâmetros |
| 5.3 | Atualizar `README.md` com novos endpoints e schemas |
| 5.4 | Limpar configs duplicadas (`docker-compose.yml.backup`, `docker-compose.agents.yml`, etc.) |
| 5.5 | Adicionar `.dockerignore` |

---

## v6: CI/CD Pipeline

### Gate de entrada
- ✅ v5 estável
- ✅ Repositório publicado (GitHub/GitLab)

### Trabalho necessário

| Tarefa | Descrição |
|--------|-----------|
| 6.1 | `.github/workflows/ci.yml` — lint → test v2 → test v3 → test v4 |
| 6.2 | Cada estrato roda em job separado |
| 6.3 | Gatilhos: push na main + PR |
| 6.4 | Cache de dependências Python |

---

## Matriz de Dependências entre Estratos

```
v0 (original)
 └── v1 (fork-a: logging + MemoryFactory) → independente
       └── v2 (fork-c parcial: schemas + conftest + tests) → depende de v1
             └── v3 (server.py fix + stack funcional) → depende de v2
                   ├── v4 (embeddings reais) → depende de v3
                   │     └── v5 (Docker/docs) → depende de v4
                   │           └── v6 (CI/CD) → depende de v5
                   │
                   ├── v7 (CloakBrowser fork) → depende de v3
                   │     ├── v7.1 Fork do repositorio
                   │     ├── v7.2 Integracao MCP Server
                   │     └── v7.3 Gerenciamento de Seeds
                   │
                   └── v8 (Embedding Router) → depende de v3
                         ├── v8.1 Router + SentenceTransformers ✅
                         ├── v8.2 LiteLLM + OpenAI
                         ├── v8.3 GraphRAG
                         └── v8.4 Integracao Qdrant ✅
```

---

## Tabela Resumo

| Estrato | Nome | Testes | Esforço | Prioridade |
|---------|------|--------|---------|------------|
| **v2** | **Atual** | **17 testes (104 total)** | **✅ pronto** | **✅ completo** |
| **v3** | **Server fix** | **17 + validação manual** | **~45 min** | **🔴 agora** (bloqueia script) |
| v4 | Embeddings reais | 17 + integração Qdrant | ~2-3h | 🟡 após v3 |
| v5 | Docker/docs | 17 + build | ~1-2h | 🟢 após v4 |
| v6 | CI/CD | Automatizado | ~1h | 🟢 após v5 |
| **v7** | **CloakBrowser fork** | **57 + invariantes** | **~11h** | 🟡 planejado |
| **v8.1** | **Embedding Router** | **45 novos** | **✅ pronto** | **✅ completo** |
| v8.2 | LiteLLM + OpenAI | 57 + mocks | ~3h | 🟡 após v8.1 |
| v8.3 | GraphRAG | 57 + integração PG | ~3h | 🟡 após v8.2 |
| **v8.4** | **Integração Qdrant** | **55 (incluso)** | **✅ pronto** | **✅ completo** |

---

## Gatilhos de Rollback Globais

| Condição | Ação |
|----------|------|
| `normalize_score(150)` retorna != 100 | Rollback imediato para estrato anterior |
| `GET /health` retorna != 200 | Rollback para último estrato com health passando |
| `pytest tests/` falha | Fork não é mergado |
| `from agents.* import` quebra | Rollback imediato |
| Volume Docker corrompido | Restore de backup ou `docker compose down -v` + recreate |
| Modelo de embedding não carrega | Fallback para placeholder (não quebra, apenas degrada) |
