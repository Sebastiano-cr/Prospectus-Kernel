# SPEC-08 — Fork 1: Marketplace de Agents

**Criticidade:** 🟢 Leviano  
**Esforço:** 2–3 semanas  
**Pré-requisito:** SPEC-06 (Kirin Lite) e SPEC-07 (Event-Driven) implementadas  
**Spec detalhada:** [`fork-1-marketplace.md`](./fork-1-marketplace.md)

---

## Objetivo

Transformar o Kirin em plataforma extensível: qualquer desenvolvedor publica um agent como pacote Python com `capability.json`, e qualquer usuário instala via `kirin install`. Flywheel de adoção via comunidade.

## Resumo de Implementação

1. `marketplace/installer.py` — `pip install` + validação de `capability.json`
2. `marketplace/validator.py` — verifica campos obrigatórios e schemas JSON
3. `marketplace/sandbox.py` — execução com timeout e isolamento por `tenant_id`
4. `kirin-core/core/registry/capability_registry.py` — adicionar `from_package()` e `unregister()`
5. `kirin-core/core/plugins/plugin_loader.py` — adicionar dispatch para agents de marketplace
6. `kirin-core/core/server.py` — 4 endpoints `/marketplace/*`
7. `github.com/kirin-community/marketplace` — repositório separado com `registry.json` público

**Contrato de agent de terceiro:** herdar `BaseAgent`, declarar `capability.json` com `input_schema`, `output_schema`, `cost_profile`, `permissions.network`.

Ver spec detalhada para contrato completo, fluxo de publicação e critérios de aceitação.
