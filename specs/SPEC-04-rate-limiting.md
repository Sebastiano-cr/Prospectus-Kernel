# SPEC-04 — Rate Limiting e Proteção do Servidor FastAPI

**Criticidade:** 🟠 Alto  
**Esforço:** 0,5 dia  
**Arquivos tocados:** `agents/server.py`, `docker-compose.agents.yml`

---

## Problema

O servidor FastAPI em `agents/server.py` não tem proteção contra sobrecarga. O n8n pode disparar centenas de requisições simultâneas (loop mal configurado, erro de retry, workflow duplicado) e derrubar o serviço por:

1. **Sem limite de concorrência** — uvicorn aceita todas as conexões até esgotar memória/CPU
2. **Sem timeout por requisição** — `/enrich` pode travar por 60s (ENRICHMENT_TIMEOUT) multiplicado por N requisições simultâneas
3. **Sem circuit breaker para LiteLLM** — se o LiteLLM estiver lento, todas as requisições ficam penduradas

O `agents/messenger.py` já tem rate limiting para WhatsApp (30–120s entre mensagens, limite diário de 200). O problema é a camada HTTP acima disso.

---

## Solução

`slowapi` (wrapper de `limits` para FastAPI) — zero mudança de arquitetura, adiciona rate limiting por IP/API-key em ~15 linhas.

---

## Implementação

### 1. Dependência

```bash
pip install slowapi==0.1.9
```

Adicionar ao `agents/requirements.txt`:
```
slowapi==0.1.9
```

### 2. `agents/server.py` — rate limiting por endpoint

```python
# Adicionar após os imports existentes
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Limiter usa API key como identificador se disponível, senão IP
def _get_identifier(request):
    api_key = request.headers.get("X-API-Key", "")
    return api_key if api_key else get_remote_address(request)

limiter = Limiter(key_func=_get_identifier)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Limites por endpoint (ajustar conforme capacidade do servidor):
# /enrich: pesado (LLM + screenshots) — máx 10/min por caller
# /score: leve — máx 30/min por caller
# /generate_message: médio — máx 20/min por caller
# /research: muito pesado (120s timeout) — máx 3/min por caller

@app.post("/enrich", dependencies=[Depends(_require_api_key)])
@limiter.limit("10/minute")
async def enrich_endpoint(request: Request, body: EnrichRequest):
    ...

@app.post("/score", dependencies=[Depends(_require_api_key)])
@limiter.limit("30/minute")
async def score_endpoint(request: Request, body: ScoreRequest):
    ...

@app.post("/generate_message", dependencies=[Depends(_require_api_key)])
@limiter.limit("20/minute")
async def generate_message_endpoint(request: Request, body: MessageRequest):
    ...

@app.post("/research", dependencies=[Depends(_require_api_key)])
@limiter.limit("3/minute")
async def research_endpoint(request: Request, body: dict):
    ...
```

**Nota:** `slowapi` exige que o primeiro parâmetro do endpoint seja `request: Request`. Verificar assinaturas existentes e adicionar se necessário.

### 3. Limite de concorrência no uvicorn

```yaml
# docker-compose.agents.yml — modificar o comando de start do agents:
agents:
  command: >
    uvicorn agents.server:app
    --host 0.0.0.0
    --port 8000
    --workers 2
    --limit-concurrency 20
    --timeout-keep-alive 30
```

`--limit-concurrency 20` rejeita com 503 quando há mais de 20 requisições simultâneas — protege contra burst do n8n.

`--workers 2` para servidor com 2–4 vCPUs. Não usar mais workers que vCPUs disponíveis.

### 4. Timeout global por requisição

```python
# agents/server.py — adicionar middleware de timeout
import asyncio
from starlette.middleware.base import BaseHTTPMiddleware

class TimeoutMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        try:
            return await asyncio.wait_for(call_next(request), timeout=90.0)
        except asyncio.TimeoutError:
            return JSONResponse(
                {"detail": "Request timeout — tente novamente"},
                status_code=504
            )

app.add_middleware(TimeoutMiddleware)
```

90s é maior que o maior timeout individual (RESEARCH_TIMEOUT=120s — ajustar para 130s ou remover `/research` do middleware).

### 5. Resposta de rate limit

Quando o limite é excedido, `slowapi` retorna automaticamente:
```json
HTTP 429 Too Many Requests
{"error": "Rate limit exceeded: 10 per 1 minute"}
```

O n8n deve ser configurado para tratar 429 com retry exponencial (ver SPEC-05).

---

## Configuração de Limites por Ambiente

```bash
# .env — tornar os limites configuráveis:
RATE_LIMIT_ENRICH=10/minute
RATE_LIMIT_SCORE=30/minute
RATE_LIMIT_MESSAGE=20/minute
RATE_LIMIT_RESEARCH=3/minute
UVICORN_WORKERS=2
UVICORN_LIMIT_CONCURRENCY=20
```

```python
# agents/server.py — ler do ambiente:
RATE_LIMIT_ENRICH = os.getenv("RATE_LIMIT_ENRICH", "10/minute")

@limiter.limit(RATE_LIMIT_ENRICH)
async def enrich_endpoint(...):
```

---

## Invariante de Teste

```python
# tests/test_units.py — adicionar
def test_rate_limit_returns_429(client):
    """Mais de 10 requisições por minuto ao /enrich retorna 429."""
    import os
    os.environ["KIRIN_API_KEY"] = "test-key"
    headers = {"X-API-Key": "test-key"}
    responses = [client.post("/enrich", json={"name": "T"}, headers=headers)
                 for _ in range(12)]
    status_codes = [r.status_code for r in responses]
    assert 429 in status_codes
```

---

## Critérios de Aceitação

- [ ] 11 requisições simultâneas ao `/enrich` resultam em pelo menos 1 resposta `429`
- [ ] `/health` não tem rate limiting (healthchecks não podem ser bloqueados)
- [ ] Requisição ao `/research` que demora mais de 90s retorna `504` em vez de travar indefinidamente
- [ ] `docker stats kirin-agents` mostra CPU < 80% durante burst de 20 requisições simultâneas
- [ ] n8n recebe `429` e não trava o workflow (tratado na SPEC-05)
