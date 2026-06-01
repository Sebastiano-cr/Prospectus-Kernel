# Spec: Fork 6 — Event-Driven com Webhooks

**Status:** Proposta  
**Prioridade:** Alta — implementar junto com ou logo após o Marketplace  
**Esforço estimado:** 2 semanas (equipe de 2)  
**Viabilidade:** 90%

---

## 1. Problema

O Kirin atual é **síncrono e fechado**: o chamador faz um POST, espera a resposta, e não sabe o que acontece depois. Isso impede integração com o ecossistema de ferramentas que os usuários já usam:

- **Zapier / Make.com** — precisam de triggers (eventos) para disparar automações
- **n8n** — já está no docker-compose do Kirin, mas não recebe eventos do pipeline
- **Slack / Teams** — notificações de leads quentes precisam de push, não polling
- **Pipedrive / HubSpot** — criação de deals precisa ser disparada por evento, não por chamada manual
- **Webhooks genéricos** — qualquer sistema externo que queira reagir a um lead processado

Sem eventos, o Kirin é uma ferramenta isolada. Com eventos, ele vira o **centro de um ecossistema**.

---

## 2. Objetivo

Adicionar uma camada de **webhooks e eventos** ao Kirin que:
1. Emite eventos tipados (CloudEvents) a cada transição relevante do pipeline
2. Permite que usuários registrem URLs para receber esses eventos via HTTP POST
3. Reutiliza o `EventBus` existente (`kirin-core/core/bus/event_bus.py`) como backbone interno
4. Expõe integrações nativas para n8n, Zapier e Slack

---

## 3. Decisões Arquiteturais

### 3.1 Fundação Existente Reutilizada

O `EventBus` (`kirin-core/core/bus/event_bus.py`) já implementa:
- `Event` com `event_id`, `event_type`, `tenant_id`, `session_id`, `actor_id`, `payload`, `timestamp`
- `publish(event)` com deduplicação por `event_id`
- `publish_to_topic(event)` com streams por `event_type`
- `subscribe(topic, handler)` — stub pronto para implementação

O `ExecutionEngine` (`kirin-core/core/engine/execution_engine.py`) já faz transições de estado (INIT → OBSERVE → DECIDE → EXECUTE → COMPLETED). **Cada transição é um ponto natural de emissão de evento.**

### 3.2 Arquitetura de Dois Níveis

```
NÍVEL 1 — Interno (já existe, expandir):
  ExecutionEngine → EventBus.publish_to_topic()
  (eventos internos de estado do agent)

NÍVEL 2 — Externo (novo):
  EventBus → WebhookDispatcher → HTTP POST para URLs registradas
  (eventos de negócio entregues para sistemas externos)
```

### 3.3 Schema de Eventos: CloudEvents 1.0

Adotar [CloudEvents](https://cloudevents.io/) garante compatibilidade com Zapier, Make, n8n e qualquer sistema que suporte o padrão.

```json
{
  "specversion": "1.0",
  "id": "uuid-v4",
  "type": "kirin.lead.scored",
  "source": "kirin/agents/scorer",
  "time": "2026-06-01T10:30:00Z",
  "datacontenttype": "application/json",
  "extensions": {
    "tenantid": "acme_corp",
    "sessionid": "sess_abc123"
  },
  "data": {
    "lead_id": "lead_xyz",
    "score": 85,
    "faixa": "quente",
    "name": "Padaria Central"
  }
}
```

### 3.4 Catálogo de Eventos de Negócio

| Evento | Disparado quando | Payload principal |
|---|---|---|
| `kirin.lead.enriched` | Enricher conclui | `lead_id`, `dossie`, `enrichment_success` |
| `kirin.lead.scored` | Scorer conclui | `lead_id`, `score`, `faixa` |
| `kirin.lead.hot` | Score >= 70 (quente) | `lead_id`, `score`, `dossie` completo |
| `kirin.lead.message_generated` | Messenger gera mensagem | `lead_id`, `message`, `channel` |
| `kirin.lead.message_sent` | Mensagem enviada com sucesso | `lead_id`, `channel`, `message_id` |
| `kirin.lead.message_failed` | Falha no envio | `lead_id`, `channel`, `error` |
| `kirin.lead.researched` | Researcher conclui | `lead_id`, `research_summary` |
| `kirin.pipeline.completed` | Pipeline completo para um lead | `lead_id`, `final_status`, `duration_ms` |
| `kirin.pipeline.failed` | Pipeline falhou | `lead_id`, `failed_stage`, `error` |

---

## 4. Estrutura de Arquivos

```
kirin/
└── kirin-core/
    └── core/
        ├── events/                         # NOVO
        │   ├── __init__.py
        │   ├── cloudevent.py               # Modelo CloudEvents 1.0
        │   ├── webhook_dispatcher.py       # Entrega HTTP para URLs externas
        │   ├── subscriptions.py            # CRUD de assinaturas por tenant
        │   └── integrations/
        │       ├── n8n.py                  # Formato específico para n8n
        │       ├── slack.py                # Slack Block Kit
        │       └── zapier.py               # Formato Zapier
        ├── bus/
        │   └── event_bus.py                # EXISTENTE — implementar subscribe()
        ├── engine/
        │   └── execution_engine.py         # EXISTENTE — adicionar emit_event()
        └── server.py                       # EXISTENTE — adicionar /webhooks/* endpoints
```

---

## 5. Implementação

### 5.1 `events/cloudevent.py` — Modelo

```python
# kirin-core/core/events/cloudevent.py
import uuid
from datetime import datetime, timezone
from pydantic import BaseModel, Field

class CloudEvent(BaseModel):
    specversion: str = "1.0"
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str                          # ex: "kirin.lead.scored"
    source: str                        # ex: "kirin/agents/scorer"
    time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    datacontenttype: str = "application/json"
    tenantid: str = "default"
    sessionid: str = ""
    data: dict = {}

    @classmethod
    def from_event(cls, event_type: str, source: str, tenant_id: str,
                   session_id: str, data: dict) -> "CloudEvent":
        return cls(type=event_type, source=source, tenantid=tenant_id,
                   sessionid=session_id, data=data)
```

### 5.2 `events/subscriptions.py` — Gerenciamento de Assinaturas

```python
# kirin-core/core/events/subscriptions.py
from pydantic import BaseModel
from typing import Optional
import uuid

class Subscription(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str
    event_types: list[str]             # ["kirin.lead.scored", "kirin.lead.hot"]
                                       # ou ["*"] para todos
    target_url: str                    # URL que receberá o POST
    secret: Optional[str] = None       # HMAC-SHA256 para verificação
    active: bool = True
    integration: Optional[str] = None  # "slack", "n8n", "zapier", ou None

class SubscriptionStore:
    """In-memory store — em produção, persistir no PostgreSQL."""

    def __init__(self):
        self._subs: dict[str, Subscription] = {}

    def add(self, sub: Subscription) -> Subscription:
        self._subs[sub.id] = sub
        return sub

    def remove(self, sub_id: str, tenant_id: str) -> None:
        sub = self._subs.get(sub_id)
        if sub and sub.tenant_id == tenant_id:
            del self._subs[sub_id]

    def get_for_event(self, event_type: str, tenant_id: str) -> list[Subscription]:
        return [
            s for s in self._subs.values()
            if s.tenant_id == tenant_id
            and s.active
            and ("*" in s.event_types or event_type in s.event_types)
        ]

    def list_for_tenant(self, tenant_id: str) -> list[Subscription]:
        return [s for s in self._subs.values() if s.tenant_id == tenant_id]
```

### 5.3 `events/webhook_dispatcher.py` — Entrega HTTP

```python
# kirin-core/core/events/webhook_dispatcher.py
import hashlib, hmac, json, logging
import httpx
from .cloudevent import CloudEvent
from .subscriptions import SubscriptionStore

logger = logging.getLogger(__name__)

class WebhookDispatcher:
    def __init__(self, store: SubscriptionStore):
        self._store = store

    async def dispatch(self, event: CloudEvent) -> None:
        subs = self._store.get_for_event(event.type, event.tenantid)
        if not subs:
            return

        payload = event.model_dump(mode="json")

        async with httpx.AsyncClient(timeout=10.0) as client:
            for sub in subs:
                headers = {
                    "Content-Type": "application/json",
                    "Ce-Specversion": "1.0",
                    "Ce-Type": event.type,
                    "Ce-Id": event.id,
                    "Ce-Source": event.source,
                }
                if sub.secret:
                    sig = hmac.new(sub.secret.encode(), json.dumps(payload).encode(),
                                   hashlib.sha256).hexdigest()
                    headers["X-Kirin-Signature"] = f"sha256={sig}"

                # Adapta payload para integrações específicas
                body = _adapt_payload(payload, sub.integration)

                try:
                    r = await client.post(sub.target_url, json=body, headers=headers)
                    if r.status_code >= 400:
                        logger.warning(f"Webhook {sub.id} retornou {r.status_code}: {sub.target_url}")
                except Exception as e:
                    logger.error(f"Falha ao entregar webhook {sub.id}: {e}")

def _adapt_payload(payload: dict, integration: str | None) -> dict:
    if integration == "slack":
        from .integrations.slack import to_slack_blocks
        return to_slack_blocks(payload)
    if integration == "zapier":
        # Zapier espera objeto plano
        return {**payload.get("data", {}), "_event_type": payload["type"]}
    return payload  # CloudEvents padrão para n8n e genérico
```

### 5.4 `events/integrations/slack.py`

```python
# kirin-core/core/events/integrations/slack.py

def to_slack_blocks(event: dict) -> dict:
    data = event.get("data", {})
    event_type = event.get("type", "")
    emoji = {"kirin.lead.hot": "🔥", "kirin.lead.scored": "📊",
             "kirin.lead.message_sent": "✅"}.get(event_type, "📌")

    return {
        "blocks": [
            {"type": "header", "text": {"type": "plain_text",
             "text": f"{emoji} Kirin: {event_type}"}},
            {"type": "section", "fields": [
                {"type": "mrkdwn", "text": f"*Lead:* {data.get('name', data.get('lead_id', '-'))}"},
                {"type": "mrkdwn", "text": f"*Score:* {data.get('score', '-')} ({data.get('faixa', '-')})"},
            ]},
        ]
    }
```

### 5.5 Emissão de Eventos no `ExecutionEngine`

Modificação mínima no `execution_engine.py` existente — adicionar chamadas ao dispatcher após cada transição relevante:

```python
# kirin-core/core/engine/execution_engine.py
# Adicionar ao método run() após agent.transition_to(AgentState.COMPLETED):

from core.events.cloudevent import CloudEvent

async def _emit(self, event_type: str, agent: BaseAgent, request: InvokeRequest,
                data: dict) -> None:
    if self._dispatcher is None:
        return
    event = CloudEvent.from_event(
        event_type=event_type,
        source=f"kirin/agents/{agent.agent_id}",
        tenant_id=request.tenant_id,
        session_id=request.memory_id,
        data=data,
    )
    await self._dispatcher.dispatch(event)
```

O `ExecutionEngine.__init__` recebe `dispatcher: WebhookDispatcher | None = None` — retrocompatível (sem dispatcher = comportamento atual).

### 5.6 Emissão nos Agentes Existentes (`agents/`)

Para o pipeline legado (`agents/enricher.py`, `agents/scorer.py`, `agents/messenger.py`), a emissão é feita no `server.py` após cada chamada, sem modificar os agentes:

```python
# agents/server.py — modificação no endpoint /score existente:

@app.post("/score")
async def score_endpoint(request: ScoreRequest):
    result = await score_lead(request.model_dump(), LITELLM_URL, DEEPSEEK_CHAT_API_KEY)

    # NOVO: emitir evento após score
    await _emit_lead_event("kirin.lead.scored", result)
    if result.get("score", 0) >= 70:
        await _emit_lead_event("kirin.lead.hot", result)

    return result

async def _emit_lead_event(event_type: str, lead: dict) -> None:
    if _dispatcher is None:
        return
    event = CloudEvent.from_event(
        event_type=event_type,
        source=f"kirin/agents/scorer",
        tenant_id="default",
        session_id=lead.get("id", ""),
        data={k: lead[k] for k in ("id", "name", "score", "faixa", "dossie") if k in lead},
    )
    await _dispatcher.dispatch(event)
```

---

## 6. Novos Endpoints no `server.py`

```python
# kirin-core/core/server.py — adicionar ao app existente:

@app.post("/webhooks/subscriptions")
async def create_subscription(payload: dict, tenant_id: str = "default"):
    """
    Registra URL para receber eventos.
    payload: {
      "event_types": ["kirin.lead.hot", "kirin.lead.scored"],
      "target_url": "https://hooks.zapier.com/...",
      "secret": "opcional",
      "integration": "slack|zapier|n8n|null"
    }
    """
    sub = Subscription(tenant_id=tenant_id, **payload)
    _sub_store.add(sub)
    return {"id": sub.id, "active": True}

@app.get("/webhooks/subscriptions")
async def list_subscriptions(tenant_id: str = "default"):
    return {"subscriptions": [s.model_dump() for s in _sub_store.list_for_tenant(tenant_id)]}

@app.delete("/webhooks/subscriptions/{sub_id}")
async def delete_subscription(sub_id: str, tenant_id: str = "default"):
    _sub_store.remove(sub_id, tenant_id)
    return {"deleted": sub_id}

@app.get("/webhooks/events")
async def list_event_types():
    """Catálogo de eventos disponíveis para assinatura."""
    return {"event_types": [
        "kirin.lead.enriched", "kirin.lead.scored", "kirin.lead.hot",
        "kirin.lead.message_generated", "kirin.lead.message_sent",
        "kirin.lead.message_failed", "kirin.lead.researched",
        "kirin.pipeline.completed", "kirin.pipeline.failed",
    ]}
```

---

## 7. Integração com n8n (já no docker-compose)

O n8n já está no `docker-compose.yml` do Kirin. A integração é imediata:

```
No n8n:
1. Adicionar node "Webhook" com URL: http://n8n:5678/webhook/kirin-leads
2. No Kirin:
   POST /webhooks/subscriptions
   {
     "event_types": ["kirin.lead.hot"],
     "target_url": "http://n8n:5678/webhook/kirin-leads",
     "integration": "n8n"
   }
3. Quando um lead quente é processado, n8n recebe o evento e pode:
   - Criar deal no Pipedrive
   - Enviar email via Gmail
   - Notificar no Slack
   - Criar tarefa no Asana
```

Nenhuma modificação no n8n — usa o node Webhook nativo.

---

## 8. Fluxo Completo: Lead Quente → Notificação Slack + Deal no Pipedrive

```
[1] POST /invoke  {"goal": "score_lead", "context": {"dossie": {...}}, "tenant_id": "acme"}
         │
         ▼
[2] ExecutionEngine.run()
    → scorer executa → score = 85 → faixa = "quente"
    → _emit("kirin.lead.scored", data={score:85, faixa:"quente", lead_id:"xyz"})
    → _emit("kirin.lead.hot",    data={score:85, dossie:{...}, lead_id:"xyz"})
         │
         ▼
[3] WebhookDispatcher.dispatch(event="kirin.lead.hot", tenant="acme")
    → busca assinaturas do tenant "acme" para "kirin.lead.hot"
    → encontra 2 assinaturas:
         sub_1: target_url="https://hooks.slack.com/...", integration="slack"
         sub_2: target_url="http://n8n:5678/webhook/kirin", integration="n8n"
         │
         ├──▶ [4a] POST https://hooks.slack.com/...
         │         body: Slack Block Kit com 🔥 "Lead Quente: Padaria Central, score 85"
         │
         └──▶ [4b] POST http://n8n:5678/webhook/kirin
                   body: CloudEvent padrão
                   n8n recebe → cria deal no Pipedrive via node nativo
         │
         ▼
[5] InvokeResponse retorna para o chamador original (síncrono, não bloqueia)
    Os webhooks são disparados em background (asyncio.gather sem await no caller)
```

---

## 9. Implementação do `subscribe()` no `EventBus`

O `subscribe()` atual é um stub. Implementação mínima para conectar ao `WebhookDispatcher`:

```python
# kirin-core/core/bus/event_bus.py — implementar subscribe():

async def subscribe(self, topic: str, handler: Callable[[Event], Awaitable[None]]) -> None:
    """Registra handler para um topic. Processa eventos já no stream."""
    stream_key = f"kirin:topic:{topic}"
    # Em produção: consumer group Redis Streams
    # Para validação: processa eventos em memória
    for entry in self._streams.get(stream_key, []):
        await handler(entry["event"])
```

Para produção com Redis real, substituir por `XREADGROUP` — a interface do `subscribe()` não muda.

---

## 10. Segurança

### Verificação de Assinatura (HMAC-SHA256)

Quando `secret` é fornecido na assinatura, o receptor pode verificar:

```python
# Exemplo de verificação no receptor (qualquer linguagem)
import hmac, hashlib

def verify_signature(payload_bytes: bytes, secret: str, header_sig: str) -> bool:
    expected = "sha256=" + hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header_sig)
```

### Retry com Backoff

Falhas de entrega são retentadas com backoff exponencial (3 tentativas: 5s, 25s, 125s). Após 3 falhas, a assinatura é marcada como `active=False` e o tenant é notificado via log.

---

## 11. Critérios de Aceitação

- [ ] `POST /webhooks/subscriptions` registra URL e retorna `id` da assinatura
- [ ] Após `POST /score` com score >= 70, a URL registrada recebe POST com `kirin.lead.hot` em menos de 2s
- [ ] Payload segue CloudEvents 1.0 (campos `specversion`, `id`, `type`, `source`, `time`, `data`)
- [ ] Assinatura com `integration: "slack"` entrega Slack Block Kit válido
- [ ] Assinatura com `secret` inclui header `X-Kirin-Signature: sha256=...`
- [ ] Falha na entrega do webhook não afeta a resposta síncrona do endpoint original
- [ ] n8n (já no docker-compose) recebe evento `kirin.lead.hot` via node Webhook sem configuração adicional
- [ ] `GET /webhooks/events` lista todos os tipos de evento disponíveis
- [ ] Pipeline legado (`agents/server.py`) emite eventos sem modificação nos agentes individuais

---

## 12. O que NÃO está no escopo deste fork

- Persistência de histórico de eventos entregues (log de auditoria) — fase posterior
- UI de gerenciamento de webhooks — fase posterior
- Retry com dead-letter queue (DLQ) — Redis Streams em produção resolve, fora do escopo de validação
- Rate limiting por assinatura — fase posterior
- Suporte a WebSockets (streaming de eventos em tempo real) — fase posterior
- Nodes nativos para Zapier/Make (requer aprovação das plataformas) — fase posterior
