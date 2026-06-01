# Spec: Fork 1 — Marketplace de Agents

**Status:** Proposta  
**Prioridade:** Alta — segundo fork a implementar (após Kirin Lite)  
**Esforço estimado:** 2–3 semanas (equipe de 2)  
**Viabilidade:** 85%

---

## 1. Problema

O Kirin é um pipeline fechado: Enricher → Scorer → Messenger → Researcher. Quem quer adaptar para um novo caso de uso (LinkedIn, TikTok, email B2C, imóveis, freelancers) precisa forkar o repositório inteiro e entender toda a arquitetura.

Isso cria dois problemas de adoção:
1. **Barreira técnica alta** — o usuário precisa ser desenvolvedor Python experiente
2. **Fragmentação** — cada fork vira um projeto separado, sem comunidade compartilhada

---

## 2. Objetivo

Transformar o Kirin em uma **plataforma extensível**: qualquer desenvolvedor publica um agent como pacote Python, e qualquer usuário instala e usa via CLI ou API — sem entender o runtime interno.

```bash
# Usuário instala agent de terceiro
kirin install prospector-linkedin --source github:user/repo

# Usa via API — mesmo contrato do Kirin nativo
POST /invoke  {"agent": "prospector-linkedin", "input": {...}}
```

---

## 3. Decisões Arquiteturais

### 3.1 Fundação Existente Reutilizada

O `CapabilityRegistry` (`kirin-core/core/registry/capability_registry.py`) já modela capabilities com:
- `input_schema` / `output_schema` (validação de contrato)
- `cost_profile` (custo por chamada em USD)
- `latency_profile` (p50/p95/p99)
- `tags` (descoberta por categoria)
- `provider_requirements` (dependências de LLM)

O `PolicyEngine` (`kirin-core/core/governance/policy_engine.py`) já tem `check_tool_permission(agent_id, tenant_id, plugin, tool)`.

O `PluginLoader` (`kirin-core/core/plugins/plugin_loader.py`) já tem `load(name, version)` e `invoke_tool(agent_id, tenant_id, plugin, tool, args)`.

**O Marketplace é uma extensão dessas três peças — não uma reescrita.**

### 3.2 Modelo de Extensão

Um agent de marketplace é um pacote Python que:
1. Expõe uma classe que herda de `BaseAgent`
2. Declara um `capability.json` com o schema de entrada/saída
3. É instalado via `kirin install` (wrapper de `pip install` + validação)
4. Roda em processo isolado (sandbox) com acesso limitado à memória

### 3.3 Isolamento de Segurança

Agents não-verificados rodam com restrições:
- Acesso à memória limitado ao `tenant_id` do chamador (já garantido pelo `PolicyEngine`)
- Sem acesso a variáveis de ambiente do host (injetadas explicitamente)
- Timeout máximo configurável por agent (padrão: 120s)
- Sem acesso à rede exceto para os `provider_requirements` declarados

---

## 4. Estrutura de Arquivos

```
kirin/
├── marketplace/                        # NOVO
│   ├── registry.json                   # Catálogo local de agents instalados
│   ├── installer.py                    # pip install + validação de schema
│   ├── sandbox.py                      # Execução isolada com timeout
│   └── validator.py                    # Valida capability.json do agent
│
└── kirin-core/
    └── core/
        ├── registry/
        │   └── capability_registry.py  # EXISTENTE — adicionar from_package()
        ├── plugins/
        │   └── plugin_loader.py        # EXISTENTE — adicionar dispatch para marketplace
        └── server.py                   # EXISTENTE — adicionar /marketplace/* endpoints
```

**Arquivos modificados (não reescritos):**
- `kirin-core/core/registry/capability_registry.py` — adicionar `from_package()` e `unregister()`
- `kirin-core/core/plugins/plugin_loader.py` — adicionar `_dispatch` para agents de marketplace
- `kirin-core/core/server.py` — adicionar 4 endpoints de marketplace

---

## 5. Contrato de um Agent de Marketplace

### 5.1 Estrutura do Pacote

```
prospector-linkedin/
├── pyproject.toml
├── capability.json          # Contrato declarativo
└── prospector_linkedin/
    ├── __init__.py
    └── agent.py             # Herda BaseAgent
```

### 5.2 `capability.json`

```json
{
  "name": "prospector-linkedin",
  "version": "1.0.0",
  "description": "Prospecta perfis de profissionais no LinkedIn",
  "author": "github:user",
  "tags": ["prospecting", "linkedin", "b2b"],
  "input_schema": {
    "type": "object",
    "required": ["query"],
    "properties": {
      "query":   {"type": "string", "description": "Ex: CTOs em São Paulo"},
      "limit":   {"type": "integer", "default": 10},
      "filters": {"type": "object"}
    }
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "leads": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "name":         {"type": "string"},
            "linkedin_url": {"type": "string"},
            "title":        {"type": "string"},
            "company":      {"type": "string"},
            "email":        {"type": "string"}
          }
        }
      }
    }
  },
  "provider_requirements": ["deepseek-chat"],
  "cost_profile": {
    "cost_per_call_usd": 0.005,
    "tokens_per_call_avg": 800,
    "currency": "USD"
  },
  "latency_profile": {"p50_ms": 2000, "p95_ms": 5000, "p99_ms": 10000},
  "permissions": {
    "network": ["linkedin.com", "api.deepseek.com"],
    "memory_read": true,
    "memory_write": true
  }
}
```

### 5.3 `agent.py`

```python
# prospector_linkedin/agent.py
from kirin_core.core.agents.base_agent import BaseAgent, InvokeRequest

class ProspectorLinkedIn(BaseAgent):
    _context_key = "query"
    _action = "prospect"

    async def _observe(self, request: InvokeRequest) -> dict:
        # Lê query do contexto
        return {"query": request.context.get("query"), "limit": request.context.get("limit", 10)}

    async def _decide(self, observation: dict) -> dict:
        return {"action": "prospect", "query": observation["query"], "memory_updates": []}

    async def _execute(self, decision: dict) -> list[dict]:
        # Implementação específica do agent
        # Acesso à rede limitado ao declarado em capability.json
        leads = await self._scrape_linkedin(decision["query"])
        return {"leads": leads}

    async def _scrape_linkedin(self, query: str) -> list[dict]:
        # Implementação do conector LinkedIn
        ...
```

---

## 6. Implementação do Marketplace

### 6.1 `marketplace/installer.py`

```python
# marketplace/installer.py
import subprocess, json, importlib
from pathlib import Path
from .validator import validate_capability

REGISTRY_PATH = Path("~/.kirin/marketplace/registry.json").expanduser()

def install(source: str) -> dict:
    """
    source: "github:user/repo", "pypi:package-name", ou path local
    Retorna o capability.json validado.
    """
    pkg_name = _resolve_package_name(source)
    subprocess.run(["pip", "install", "--quiet", pkg_name], check=True)

    # Localiza e valida capability.json
    pkg = importlib.import_module(pkg_name.replace("-", "_"))
    cap_path = Path(pkg.__file__).parent / "capability.json"
    capability = json.loads(cap_path.read_text())
    validate_capability(capability)  # lança ValueError se inválido

    # Registra localmente
    registry = _load_registry()
    registry[capability["name"]] = {
        "source": source,
        "pkg_name": pkg_name,
        "capability": capability,
    }
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(json.dumps(registry, indent=2))

    return capability

def _load_registry() -> dict:
    if REGISTRY_PATH.exists():
        return json.loads(REGISTRY_PATH.read_text())
    return {}

def _resolve_package_name(source: str) -> str:
    if source.startswith("github:"):
        _, repo = source.split(":", 1)
        return f"git+https://github.com/{repo}.git"
    if source.startswith("pypi:"):
        return source.split(":", 1)[1]
    return source  # path local
```

### 6.2 `marketplace/validator.py`

```python
# marketplace/validator.py
REQUIRED_FIELDS = {"name", "version", "input_schema", "output_schema",
                   "provider_requirements", "cost_profile", "latency_profile"}

def validate_capability(cap: dict) -> None:
    missing = REQUIRED_FIELDS - set(cap.keys())
    if missing:
        raise ValueError(f"capability.json faltando campos: {missing}")

    # Valida que input/output_schema são JSON Schema válidos
    for field in ("input_schema", "output_schema"):
        if cap[field].get("type") != "object":
            raise ValueError(f"{field} deve ser type=object")

    # Valida cost_profile
    cp = cap["cost_profile"]
    if not isinstance(cp.get("cost_per_call_usd"), (int, float)):
        raise ValueError("cost_profile.cost_per_call_usd deve ser numérico")
```

### 6.3 `marketplace/sandbox.py`

```python
# marketplace/sandbox.py
import asyncio, importlib
from typing import Any

async def invoke_sandboxed(
    agent_name: str,
    input_data: dict,
    tenant_id: str,
    timeout: float = 120.0,
) -> Any:
    """Invoca agent de marketplace com timeout e isolamento básico."""
    pkg_name = agent_name.replace("-", "_")
    mod = importlib.import_module(pkg_name)
    AgentClass = _find_agent_class(mod)

    agent = AgentClass(agent_id=agent_name)
    agent._tenant_id = tenant_id

    from kirin_core.core.agents.base_agent import InvokeRequest
    request = InvokeRequest(
        goal=agent_name,
        context=input_data,
        memory_id=f"{tenant_id}:{agent_name}",
        tenant_id=tenant_id,
    )

    try:
        await agent._init(request)
        obs = await agent._observe(request)
        dec = await agent._decide(obs)
        result = await asyncio.wait_for(agent._execute(dec), timeout=timeout)
        return result
    except asyncio.TimeoutError:
        raise TimeoutError(f"Agent '{agent_name}' excedeu timeout de {timeout}s")

def _find_agent_class(mod):
    from kirin_core.core.agents.base_agent import BaseAgent
    import inspect
    for _, cls in inspect.getmembers(mod, inspect.isclass):
        if issubclass(cls, BaseAgent) and cls is not BaseAgent:
            return cls
    raise ValueError(f"Nenhuma subclasse de BaseAgent encontrada em {mod.__name__}")
```

---

## 7. Extensões no Kirin Core

### 7.1 `capability_registry.py` — adições mínimas

```python
# Adicionar ao CapabilityRegistry existente:

def from_package(self, capability_json: dict) -> None:
    """Registra capability a partir de um capability.json de marketplace."""
    cap = Capability(**capability_json)
    self.register(cap)

def unregister(self, name: str) -> None:
    self._capabilities.pop(name, None)
```

### 7.2 `plugin_loader.py` — adições mínimas

```python
# Adicionar ao _dispatch existente:

async def _dispatch(self, plugin: str, tool: str, args: dict) -> dict:
    dispatchers = {
        "crm":       self._call_crm,
        "whatsapp":  self._call_whatsapp,
        "vectordb":  self._call_vectordb,
        # NOVO: qualquer agent de marketplace
        "marketplace": self._call_marketplace,
    }
    fn = dispatchers.get(plugin) or dispatchers.get("marketplace")
    if fn is None:
        raise ValueError(f"Plugin desconhecido: {plugin}")
    return await fn(tool, args)

async def _call_marketplace(self, agent_name: str, args: dict) -> dict:
    from marketplace.sandbox import invoke_sandboxed
    return await invoke_sandboxed(agent_name, args, tenant_id=self._tenant_id)
```

### 7.3 `server.py` — novos endpoints

```python
# Adicionar ao server.py existente (kirin-core/core/server.py):

@app.post("/marketplace/install")
async def marketplace_install(payload: dict):
    """Instala agent de marketplace. source: "github:user/repo" ou "pypi:pkg"."""
    from marketplace.installer import install
    capability = install(payload["source"])
    _registry.from_package(capability)
    return {"installed": capability["name"], "version": capability["version"]}

@app.get("/marketplace/agents")
async def marketplace_list():
    """Lista agents de marketplace instalados."""
    from marketplace.installer import _load_registry
    return {"agents": list(_load_registry().values())}

@app.delete("/marketplace/agents/{name}")
async def marketplace_uninstall(name: str):
    _registry.unregister(name)
    return {"uninstalled": name}

@app.post("/marketplace/invoke/{agent_name}")
async def marketplace_invoke(agent_name: str, payload: dict, tenant_id: str = "default"):
    """Invoca agent de marketplace diretamente."""
    from marketplace.sandbox import invoke_sandboxed
    result = await invoke_sandboxed(agent_name, payload, tenant_id)
    return {"result": result, "agent": agent_name}
```

---

## 8. CLI de Marketplace

```bash
# Instalar agent
kirin install prospector-linkedin --source github:user/repo
kirin install email-outreach --source pypi:kirin-email-outreach

# Listar agents instalados
kirin agents list

# Invocar agent
kirin invoke prospector-linkedin --input '{"query": "CTOs em SP", "limit": 10}'

# Desinstalar
kirin uninstall prospector-linkedin
```

---

## 9. Fluxo Completo: Usuário Publica e Usa um Agent

```
DESENVOLVEDOR:
  1. Cria pacote Python com BaseAgent + capability.json
  2. Publica no PyPI: pip publish
  3. (Opcional) Submete PR para kirin-marketplace/registry.json (catálogo oficial)

USUÁRIO:
  1. kirin install prospector-linkedin --source pypi:kirin-prospector-linkedin
  2. Kirin: pip install → valida capability.json → registra no CapabilityRegistry local
  3. POST /marketplace/invoke/prospector-linkedin
     {"query": "CTOs em São Paulo", "limit": 10}
  4. Kirin: PolicyEngine.check_tool_permission() → sandbox.invoke_sandboxed()
  5. Agent executa com tenant_id isolado
  6. Resultado retorna no mesmo formato de InvokeResponse
```

---

## 10. `registry.json` — Catálogo Oficial (Repositório Separado)

```json
{
  "agents": [
    {
      "name": "prospector-linkedin",
      "pypi": "kirin-prospector-linkedin",
      "github": "kirin-community/prospector-linkedin",
      "tags": ["prospecting", "linkedin", "b2b"],
      "verified": true,
      "downloads": 1240
    },
    {
      "name": "email-outreach",
      "pypi": "kirin-email-outreach",
      "github": "kirin-community/email-outreach",
      "tags": ["email", "outreach", "cold-email"],
      "verified": true,
      "downloads": 890
    }
  ]
}
```

Hospedado em `github.com/kirin-community/marketplace` — separado do core.

---

## 11. Critérios de Aceitação

- [ ] `kirin install <source>` instala e valida um agent em menos de 30s
- [ ] Agent instalado aparece em `GET /capabilities` com schema correto
- [ ] `POST /marketplace/invoke/<agent>` executa com timeout e retorna erro claro se exceder
- [ ] Agent com `capability.json` inválido é rejeitado na instalação com mensagem descritiva
- [ ] Agents de marketplace são isolados por `tenant_id` (não acessam dados de outros tenants)
- [ ] Desinstalar um agent remove do `CapabilityRegistry` sem reiniciar o servidor
- [ ] O pipeline nativo (Enricher/Scorer/Messenger) continua funcionando sem alteração

---

## 12. O que NÃO está no escopo deste fork

- Marketplace web UI (catálogo visual) — fase posterior
- Billing por uso de agent de terceiro — requer Fork 5 (SaaS)
- Assinatura de pacotes (code signing) — segurança avançada, fase posterior
- Sandbox com isolamento de processo real (Docker por agent) — over-engineering para validação
- Versionamento de agents em produção (rollback) — fase posterior
