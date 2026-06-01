# SPEC-05 — Pipeline n8n em Produção

**Criticidade:** 🟠 Alto  
**Esforço:** 1 dia  
**Arquivos tocados:** `n8n/workflows/lead_processor.json`, `n8n/workflows/main_pipeline.json`, `n8n/workflows/webhook_handler.json`

---

## Problema

O workflow `lead_processor.json` tem `"active": false` — está desativado. Quando ativado, tem três falhas críticas:

1. **Sem retry em falhas de HTTP** — se `/enrich` retornar 500 ou 429, o item é descartado silenciosamente
2. **Sem error handling** — um lead com `phone` inválido quebra o node "Enviar WhatsApp" e para o batch inteiro
3. **Sem throttling entre leads** — processa todos os leads do batch em paralelo, ignorando o `MIN_SEND_INTERVAL` de 30s do messenger
4. **`main_pipeline.json` usa `manualTrigger`** — não tem agendamento automático

---

## Solução

Modificar os workflows JSON para adicionar retry, error handling e throttling. Ativar o pipeline com agendamento.

---

## Implementação

### 1. `lead_processor.json` — retry em cada HTTP node

Para cada node `httpRequest` que chama `agents:8000`, adicionar configuração de retry:

```json
{
  "parameters": {
    "url": "http://agents:8000/enrich",
    "method": "POST",
    "jsonParameters": true,
    "options": {
      "timeout": 70000,
      "retry": {
        "enabled": true,
        "maxTries": 3,
        "waitBetweenTries": 5000
      },
      "response": {
        "response": {
          "responseFormat": "json",
          "fullResponse": true
        }
      }
    },
    "headerParameters": {
      "parameters": [
        { "name": "X-API-Key", "value": "={{ $env.KIRIN_API_KEY }}" }
      ]
    },
    "bodyParametersJson": "={{ $json }}"
  },
  "name": "Enricher (Qwen VL Max)",
  "type": "n8n-nodes-base.httpRequest",
  "typeVersion": 2,
  "onError": "continueErrorOutput"
}
```

`"onError": "continueErrorOutput"` faz o n8n rotear falhas para um branch de erro em vez de parar o workflow.

### 2. `lead_processor.json` — branch de erro

Adicionar node de tratamento de erro após cada etapa crítica:

```json
{
  "name": "Log Erro Enricher",
  "type": "n8n-nodes-base.set",
  "parameters": {
    "values": {
      "string": [
        { "name": "status", "value": "erro_enricher" },
        { "name": "erro", "value": "={{ $json.error }}" },
        { "name": "lead_id", "value": "={{ $json.id }}" },
        { "name": "timestamp", "value": "={{ $now }}" }
      ]
    }
  }
}
```

Conectar o output de erro do Enricher → Log Erro → CRM Sync (para registrar a falha no CRM).

### 3. `lead_processor.json` — throttling entre leads

Adicionar node `Wait` entre o Messenger e o "Enviar WhatsApp":

```json
{
  "name": "Aguardar Intervalo",
  "type": "n8n-nodes-base.wait",
  "parameters": {
    "unit": "seconds",
    "amount": 45
  },
  "position": [1150, 400]
}
```

45s está dentro do intervalo `[30, 120]` definido em `agents/messenger.py`. Isso garante que o n8n respeita o rate limiting do WhatsApp mesmo que o messenger interno falhe em aplicá-lo.

### 4. `lead_processor.json` — verificação de score antes de enviar

Adicionar node `IF` antes do Messenger para não gerar mensagem para leads com score < 20:

```json
{
  "name": "Score mínimo para mensagem",
  "type": "n8n-nodes-base.if",
  "parameters": {
    "conditions": {
      "number": [
        {
          "value1": "={{ $json.score }}",
          "operation": "larger",
          "value2": 20
        }
      ]
    }
  }
}
```

Branch `false` → CRM Sync direto com `status: "descartado"`.

### 5. `main_pipeline.json` — substituir `manualTrigger` por `scheduleTrigger`

```json
{
  "name": "Agendamento Diário",
  "type": "n8n-nodes-base.scheduleTrigger",
  "parameters": {
    "rule": {
      "interval": [
        {
          "field": "cronExpression",
          "expression": "0 9 * * 1-5"
        }
      ]
    }
  },
  "position": [250, 300]
}
```

`0 9 * * 1-5` = segunda a sexta às 9h. Ajustar conforme horário comercial do nicho.

### 6. `main_pipeline.json` — ativar o workflow

```json
"active": true
```

Mudar de `false` para `true` após validar o pipeline completo em modo manual.

### 7. `webhook_handler.json` — tratamento de opt-out "SAIR"

O webhook handler precisa processar respostas de WhatsApp e bloquear leads que respondem "SAIR":

```json
{
  "name": "Detectar SAIR",
  "type": "n8n-nodes-base.if",
  "parameters": {
    "conditions": {
      "string": [
        {
          "value1": "={{ $json.message.toLowerCase() }}",
          "operation": "contains",
          "value2": "sair"
        }
      ]
    }
  }
}
```

Branch `true` → HTTP POST para `agents:8000/crm_sync` com `status: "descartado"`.

---

## Configuração de Variáveis no n8n

No painel do n8n (`Settings > Variables`), definir:

```
KIRIN_API_KEY     = <valor do .env>
EVOLUTION_INSTANCE_ID = <id da instância WhatsApp>
```

Isso evita hardcode nos workflows e permite rotação de keys sem editar JSON.

---

## Checklist de Ativação (executar em ordem)

```
[ ] 1. Implementar SPEC-01 (auth) e SPEC-04 (rate limiting) primeiro
[ ] 2. Testar lead_processor manualmente com 1 lead (Manual Trigger)
[ ] 3. Verificar que o lead aparece no CRM com status correto
[ ] 4. Testar com 5 leads — confirmar throttling de 45s entre envios
[ ] 5. Testar falha: desligar agents temporariamente, confirmar que n8n retenta
[ ] 6. Ativar agendamento (active: true) apenas após os 5 passos acima
```

---

## Critérios de Aceitação

- [ ] Falha no `/enrich` (500) resulta em 3 tentativas com 5s de intervalo, depois registra erro no CRM
- [ ] Lead com score < 20 não gera mensagem WhatsApp — vai direto para CRM com `status: "descartado"`
- [ ] Intervalo mínimo de 45s entre envios de WhatsApp consecutivos (medido no log do n8n)
- [ ] Resposta "SAIR" no WhatsApp atualiza o lead para `status: "descartado"` no CRM
- [ ] Pipeline executa automaticamente às 9h em dias úteis
- [ ] Falha em 1 lead não para o processamento dos demais leads do batch
