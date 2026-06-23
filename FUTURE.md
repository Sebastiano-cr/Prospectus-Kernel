# Prospectus-Kernel — Simplificação Planejada

## Motivação
Reduzir overengineering hexagonal sem perder diferenciais:
Language Game Analyzer, ChromaDB embarcado, i18n (42 prompts), LiteLLM, CI/CD.

## O que NÃO muda (proteger)
- `src/analysis/` — Language Game (14 campos), Resonance Engine, SkepticAgent (H1-H7)
- `src/store.py` — ChromaStore (ChromaDB embarcado, 0 containers)
- `src/locale/prompts/` — 42 arquivos .prompt.md (pt-BR, es, en)
- LiteLLM proxy (multi-provider via 1 config)
- GitHub Actions (ruff → pytest → mypy)
- `tests/` — 197 testes, 0 falhas

## O que simplificar

### 1. Ports/Adapters/Factory → funções diretas (~1h)

| Apagar | Criar |
|--------|-------|
| `agents/ports/` (3 ABCs) | `agents/llm_client.py` (~30 linhas) |
| `agents/adapters/` (3 implementações) | — (fundido em funções) |
| `agents/factory.py` | — (substituído por `llm_complete()`) |

**NOVO:** `agents/llm_client.py` — função async única que chama LiteLLM via httpx.

**Mudanças de import:**
```python
# ANTES
from agents.factory import ServiceFactory
llm = ServiceFactory.get_llm_client()
response = await llm.complete(messages=messages, model="...")

# DEPOIS
from agents.llm_client import llm_complete
response = await llm_complete(messages=messages, model="...")
```

**Arquivos a modificar:**
- `agents/enricher.py` — substituir `ServiceFactory.get_llm_client()` por `llm_complete()`, remover retry
- `agents/scorer.py` — idem
- `agents/messenger.py` — idem
- `agents/discourse_ingestor.py` — idem
- `agents/language_game.py` — idem
- `agents/skeptic.py` — idem
- `agents/researcher.py` — idem
- `agents/runtime.py` — remover import de factory

### 2. Locale hexagonal → dict simples (~30 min)

| Apagar | Criar |
|--------|-------|
| `src/locale/port.py` (ABC) | `src/locale/__init__.py` (~50 linhas, dict) |
| `src/locale/factory.py` | — (fundido em `__init__`) |
| `src/locale/adapters/pt_br.py` (classe) | — (vira dict em `_pt_br.py`) |
| `src/locale/adapters/es.py` (classe) | — (vira dict em `_es.py`) |
| `src/locale/adapters/en.py` (classe) | — (vira dict em `_en.py`) |

**Mudanças de import:**
```python
# ANTES
from src.locale import get_locale
from src.locale.port import LocalePort

# DEPOIS
from src.locale import get_locale  # mesma API, implementação simplificada
locale = get_locale("pt-BR")
prompt = locale.get_prompt("enrichment")
status = locale.get_status_label("qualified")
```

### Ordem de execução
1. `agents/llm_client.py` + atualizar imports
2. Apagar `agents/ports/`, `agents/adapters/`, `agents/factory.py`
3. Simplificar `src/locale/` (port + factory → __init__.py)
4. Rodar `pytest tests/ -q` — 197 devem passar
5. Rodar `ruff check agents/ src/` — 0 erros
6. Commit + push

## Status: Fase 0 Completa ✅

Processado 1 lead real end-to-end em **27 de junho de 2026**:
- `scripts/process_one_lead.py` — pipeline completo com Ollama (qwen2.5:3b)
- Lead: Clínica Bella Estética → dossiê (maturidade: baixo) → score (20/100, frio) → mensagem personalizada
- Tempo total: ~2.5 min (enrich: 55s, score: 56s, message: 39s)
- Custo: R$ 0,00 (LLM local gratuito)
- **Checklist de saída: 5/5** ✅ (pendente: WhatsApp delivery — requer EVOLUTION_URL)

## Próximo: Fase 1 (Product-Market Fit, 1 → 10 leads)
- [ ] Streamlit UI (`streamlit_ui.py`)
- [ ] A/B testing
- [ ] CSV export
- [ ] Qwen fallback (já funcional via Ollama)

### Ordem de execução (para próxima sessão)
1. `agents/llm_client.py` + atualizar imports
2. Apagar `agents/ports/`, `agents/adapters/`, `agents/factory.py`
3. Simplificar `src/locale/` (port + factory → __init__.py)
4. Rodar `pytest tests/ -q` — 197 devem passar
5. Rodar `ruff check agents/ src/` — 0 erros
6. Commit + push
