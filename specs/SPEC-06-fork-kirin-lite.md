# SPEC-06 — Fork 2: Kirin Lite

**Criticidade:** 🟡 Médio  
**Esforço:** 1 semana  
**Pré-requisito:** SPEC-01 a SPEC-05 implementadas (sistema estável em produção)  
**Spec detalhada:** [`fork-2-kirin-lite.md`](./fork-2-kirin-lite.md)

---

## Objetivo

Criar `kirin-lite` — runtime instalável via `pip install kirin-lite`, zero Docker, zero infra externa. Porta de entrada para adoção em massa.

## Resumo de Implementação

1. `kirin-lite/kirin_lite/runtime.py` — SQLite + dict TTL + busca vetorial linear (substitutos de PG/Redis/Qdrant)
2. `kirin-lite/kirin_lite/llm.py` — cliente LLM direto (sem LiteLLM server), suporte a Ollama
3. `kirin-lite/kirin_lite/pipeline.py` — importa `agents/enricher.py`, `agents/scorer.py`, `agents/messenger.py` sem modificação
4. `kirin-lite/kirin_lite/cli.py` — `kirin run`, `kirin serve`
5. `kirin-lite/pyproject.toml` — sem PostgreSQL, Redis, Qdrant nas dependências

**Invariante de compatibilidade:** schemas de entrada/saída idênticos ao Kirin Full. Um lead processado no Lite pode ser importado no Full sem transformação.

Ver spec detalhada para contratos de interface, exemplos de código e critérios de aceitação completos.
