# SPEC-01 — Autenticação e Segurança de Endpoints

**Criticidade:** 🔴 Crítico  
**Esforço:** 0,5 dia  
**Arquivos tocados:** `agents/server.py`, `kirin-core/core/server.py`, `docker-compose.agents.yml`, `.env`

---

## Problema

`agents/server.py` expõe `/enrich`, `/score`, `/generate_message`, `/research`, `/crm_sync` sem nenhuma autenticação. Qualquer processo na mesma rede (ou na internet, se a porta 8000 estiver exposta) pode chamar o pipeline, consumir cotas de LLM e enviar mensagens WhatsApp.

O `kirin-core/core/server.py` tem `PolicyEngine.check()` que valida `tenant_id` mas não valida credencial — qualquer `tenant_id` arbitrário passa.

---

## Solução

API Key estática por header `X-API-Key`. Simples, sem dependência nova, reversível.

Não usar JWT aqui — JWT é para o `kirin-pair-backend` (autenticação de usuário). Para comunicação serviço-a-serviço (n8n → agents), API Key é o padrão correto.

---

## Implementação

### 1. `agents/server.py` — middleware de API key

```python
# Adicionar após os imports existentes
from fastapi import Depends, Security
from fastapi.security.api_key import APIKeyHeader

_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
_KIRIN_API_KEY = os.getenv("KIRIN_API_KEY", "")

async def _require_api_key(key: str = Security(_API_KEY_HEADER)) -> None:
    if not _KIRIN_API_KEY:
        return  # sem key configurada = modo dev, passa tudo
    if key != _KIRIN_API_KEY:
        raise HTTPException(status_code=403, detail="API key inválida")
```

Adicionar `dependencies=[Depends(_require_api_key)]` nos endpoints do caminho crítico:

```python
@app.post("/enrich",            dependencies=[Depends(_require_api_key)])
@app.post("/score",             dependencies=[Depends(_require_api_key)])
@app.post("/generate_message",  dependencies=[Depends(_require_api_key)])
@app.post("/research",          dependencies=[Depends(_require_api_key)])
@app.post("/crm_sync",          dependencies=[Depends(_require_api_key)])
```

`/health` e `/metrics` ficam públicos — são necessários para healthchecks e Prometheus.

### 2. `kirin-core/core/server.py` — mesmo padrão

```python
# Adicionar ao PolicyEngine.check():
async def check(self, request: InvokeRequest) -> None:
    if not request.tenant_id:
        raise PermissionError("tenant_id obrigatório")
    # Validar API key do header (injetada via middleware FastAPI)
    # O middleware já rejeita antes de chegar aqui — dupla camada
```

Adicionar o mesmo middleware de API key ao `app` do kirin-core.

### 3. `docker-compose.agents.yml` — injetar a variável

```yaml
agents:
  environment:
    - KIRIN_API_KEY=${KIRIN_API_KEY}   # adicionar esta linha
```

### 4. `.env` — gerar e definir a key

```bash
# Gerar (executar uma vez):
openssl rand -hex 32

# Adicionar ao .env:
KIRIN_API_KEY=<valor_gerado>
```

### 5. `n8n/workflows/lead_processor.json` — adicionar header

Em cada node `httpRequest` que chama `http://agents:8000/*`, adicionar:

```json
"headerParameters": {
  "parameters": [
    { "name": "X-API-Key", "value": "={{ $env.KIRIN_API_KEY }}" }
  ]
}
```

---

## Invariante de Teste

```python
# tests/test_units.py — adicionar
def test_endpoint_rejects_missing_api_key(client):
    """Endpoints críticos retornam 403 sem X-API-Key quando KIRIN_API_KEY está definida."""
    import os
    os.environ["KIRIN_API_KEY"] = "test-key"
    r = client.post("/enrich", json={"name": "Test"})
    assert r.status_code == 403

def test_endpoint_accepts_valid_api_key(client):
    r = client.post("/enrich", json={"name": "Test"},
                    headers={"X-API-Key": "test-key"})
    assert r.status_code != 403  # pode falhar por outro motivo, mas não por auth
```

---

## Critérios de Aceitação

- [ ] `POST /enrich` sem `X-API-Key` retorna `403` quando `KIRIN_API_KEY` está definida
- [ ] `GET /health` retorna `200` sem autenticação (healthcheck não pode exigir auth)
- [ ] n8n consegue chamar o pipeline com a key configurada via variável de ambiente
- [ ] Quando `KIRIN_API_KEY` não está definida, o sistema funciona sem auth (modo dev)
- [ ] Nenhum teste existente quebra (os testes de unidade não passam header — modo dev ativo)
