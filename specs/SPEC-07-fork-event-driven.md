# SPEC-07 — Fork 6: Event-Driven com Webhooks

**Criticidade:** 🟡 Médio  
**Esforço:** 2 semanas  
**Pré-requisito:** SPEC-01 a SPEC-05 implementadas  
**Spec detalhada:** [`fork-6-event-driven.md`](./fork-6-event-driven.md)

---

## Objetivo

Adicionar camada de webhooks ao Kirin: eventos tipados (CloudEvents 1.0) emitidos a cada transição do pipeline, entregues via HTTP POST para URLs registradas. Integração nativa com n8n (já no docker-compose), Slack e Zapier.

## Resumo de Implementação

1. `kirin-core/core/events/cloudevent.py` — modelo CloudEvents 1.0
2. `kirin-core/core/events/subscriptions.py` — CRUD de assinaturas por tenant
3. `kirin-core/core/events/webhook_dispatcher.py` — entrega HTTP com HMAC-SHA256
4. `kirin-core/core/events/integrations/slack.py` — adaptador Slack Block Kit
5. `kirin-core/core/bus/event_bus.py` — implementar `subscribe()` (hoje é stub)
6. `kirin-core/core/engine/execution_engine.py` — adicionar `_emit()` após transições de estado
7. `agents/server.py` — emitir eventos nos endpoints legados sem modificar os agentes
8. `kirin-core/core/server.py` — 4 novos endpoints `/webhooks/*`

**Eventos de negócio:** `kirin.lead.enriched`, `kirin.lead.scored`, `kirin.lead.hot`, `kirin.lead.message_sent`, `kirin.pipeline.completed`, `kirin.pipeline.failed`.

Ver spec detalhada para schema de eventos, fluxo completo e critérios de aceitação.
