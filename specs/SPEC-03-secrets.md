# SPEC-03 — Gestão de Secrets

**Criticidade:** 🔴 Crítico  
**Esforço:** 0,5 dia  
**Arquivos tocados:** `.env`, `docker-compose.agents.yml`, `kirin-core/docker-compose.override.yml`, `kirin-pair-backend/kirin_prospect.py`

---

## Problema

Três exposições de secrets em texto claro:

1. **`.env`** contém `JWT_SECRET=your-super-secret-jwt-key-change-this-in-production` — o placeholder literal está no arquivo que vai para o processo em produção.
2. **`docker-compose.agents.yml`** tem `POSTGRES_PASSWORD=kirinpass` hardcoded (não via variável de ambiente).
3. **`kirin-pair-backend/kirin_prospect.py`** tem `JWT_SECRET = os.getenv("JWT_SECRET", "your-super-secret-jwt-key-change-this-in-production")` — o fallback é o placeholder, então se a variável não estiver definida, o sistema funciona com secret fraco sem erro.

O `SecretVault` (`kirin-core/core/governance/secret_vault.py`) já existe e usa Fernet para criptografia — mas não está sendo usado pelos agentes legados.

---

## Solução

Dois níveis:
- **Imediato (hoje):** substituir todos os placeholders por valores reais e remover fallbacks inseguros
- **Estrutural (esta semana):** usar `SecretVault` para API keys de LLM nos agentes

---

## Implementação

### Nível 1 — Imediato: substituir placeholders

```bash
# Gerar secrets reais (executar uma vez, guardar em local seguro):
openssl rand -hex 32   # → JWT_SECRET
openssl rand -hex 32   # → KIRIN_API_KEY (SPEC-01)
openssl rand -hex 16   # → POSTGRES_PASSWORD
openssl rand -hex 32   # → SECRET_VAULT_KEY (para Fernet)
```

**`.env` — campos obrigatórios que precisam de valor real:**

```bash
# Secrets de autenticação
JWT_SECRET=<gerado_acima>
KIRIN_API_KEY=<gerado_acima>
SECRET_VAULT_KEY=<gerado_acima>

# Banco de dados
POSTGRES_PASSWORD=<gerado_acima>

# LLM (já devem ter valores reais — confirmar)
QWEN_VL_MAX_API_KEY=<sua_key_real>
DEEPSEEK_CHAT_API_KEY=<sua_key_real>
MOONSHOT_V1_128K_API_KEY=<sua_key_real>

# WhatsApp
EVOLUTION_API_KEY=<sua_key_real>
JWT_SECRET_EVOLUTION=<gerado_acima>
```

**`docker-compose.agents.yml` — remover hardcode:**

```yaml
# ANTES (hardcoded):
postgres:
  environment:
    - POSTGRES_PASSWORD=kirinpass

# DEPOIS (via variável):
postgres:
  environment:
    - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
```

**`kirin-pair-backend/kirin_prospect.py` — remover fallback inseguro:**

```python
# ANTES:
JWT_SECRET = os.getenv("JWT_SECRET", "your-super-secret-jwt-key-change-this-in-production")

# DEPOIS:
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET não definido. Configure a variável de ambiente.")
```

Aplicar o mesmo padrão para qualquer `os.getenv("X", "placeholder")` nos arquivos:
- `kirin-pair-backend/main.py`
- `kirin-pair-backend/pair_agents/prospect.py`

### Nível 2 — Estrutural: usar SecretVault nos agentes

O `SecretVault` já está implementado em `kirin-core/core/governance/secret_vault.py`. Integrar no `agents/server.py` para as API keys de LLM:

```python
# agents/server.py — substituir leitura direta de os.getenv por SecretVault

# ANTES:
QWEN_VL_MAX_API_KEY = os.getenv("QWEN_VL_MAX_API_KEY", "")
DEEPSEEK_CHAT_API_KEY = os.getenv("DEEPSEEK_CHAT_API_KEY", "")

# DEPOIS:
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'kirin-core'))
from core.governance.secret_vault import SecretVault

_vault = SecretVault()

def _get_key(name: str) -> str:
    return _vault.get("agents-server", name)

# Uso (lazy — só resolve quando o endpoint é chamado):
# _get_key("QWEN_VL_MAX_API_KEY") em vez de QWEN_VL_MAX_API_KEY
```

**Benefício do SecretVault:** toda leitura de secret gera entrada em `_vault._audit` com `agent_id`, `secret_name` e `timestamp` — sem expor o valor. Auditoria automática de quem acessou qual key.

### Nível 3 — `.gitignore` (verificar)

```bash
# Confirmar que .env está no .gitignore:
grep -n "\.env" /home/vector/Kirin/.gitignore || echo "ATENÇÃO: .env não está no .gitignore"
```

Se não estiver:
```bash
echo ".env" >> /home/vector/Kirin/.gitignore
echo "*.pem" >> /home/vector/Kirin/.gitignore
echo "secrets/" >> /home/vector/Kirin/.gitignore
```

---

## Rotação de Secrets (procedimento)

Quando um secret precisar ser rotacionado (vazamento, saída de membro da equipe):

```bash
# 1. Gerar novo valor
NEW_SECRET=$(openssl rand -hex 32)

# 2. Atualizar .env
sed -i "s/^JWT_SECRET=.*/JWT_SECRET=${NEW_SECRET}/" .env

# 3. Reiniciar apenas os serviços afetados (não o stack inteiro)
docker-compose restart agents kirin-core

# 4. Verificar que o serviço voltou saudável
curl -sf http://localhost:8000/health
```

---

## Invariante de Teste

```python
# tests/test_units.py — adicionar
def test_no_placeholder_secrets_in_env():
    """Nenhuma variável de ambiente crítica pode ter valor de placeholder."""
    import os
    placeholders = {"your-super-secret", "change-this", "placeholder", "kirinpass", "your_"}
    critical_vars = ["JWT_SECRET", "KIRIN_API_KEY", "POSTGRES_PASSWORD"]
    for var in critical_vars:
        val = os.getenv(var, "")
        if val:  # só verifica se a variável está definida
            for p in placeholders:
                assert p not in val.lower(), f"{var} contém placeholder '{p}'"
```

---

## Critérios de Aceitação

- [ ] `grep -r "your-super-secret\|kirinpass\|change-this-in-production" .env` retorna vazio
- [ ] `kirin_prospect.py` lança `RuntimeError` se `JWT_SECRET` não estiver definido
- [ ] `docker-compose up` falha com mensagem clara se `POSTGRES_PASSWORD` não estiver no `.env`
- [ ] `.env` está no `.gitignore` e não aparece em `git status`
- [ ] `SecretVault._audit` registra acesso às API keys sem expor os valores
