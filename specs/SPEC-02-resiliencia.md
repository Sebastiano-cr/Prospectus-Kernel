# SPEC-02 — Resiliência de Infraestrutura

**Criticidade:** 🔴 Crítico  
**Esforço:** 0,5 dia  
**Arquivos tocados:** `docker-compose.agents.yml`, `docker-compose.yml`, novo `scripts/backup.sh`

---

## Problema

Três falhas silenciosas que custam receita:

1. **Sem `restart: unless-stopped`** — se qualquer container cair (OOM, crash, reboot do host), não sobe sozinho. O pipeline para sem alerta.
2. **Sem `healthcheck`** — `depends_on` não garante que o serviço está *pronto*, só que o container *iniciou*. O `agents` pode tentar conectar ao PostgreSQL antes dele aceitar conexões.
3. **Sem backup** — `postgres_data/`, `qdrant_data/` são volumes locais. Falha de disco = perda total do histórico de leads e embeddings.

---

## Solução

### 1. `docker-compose.agents.yml` — restart + healthchecks

```yaml
services:
  postgres:
    image: postgres:15
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U kirin -d kirin"]
      interval: 10s
      timeout: 5s
      retries: 5
    volumes:
      - postgres_data:/var/lib/postgresql/data

  qdrant:
    image: qdrant/qdrant:latest
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "curl -sf http://localhost:6333/healthz || exit 1"]
      interval: 15s
      timeout: 5s
      retries: 3
    volumes:
      - qdrant_data:/qdrant/storage

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3
    command: ["redis-server", "--save", "60", "1", "--loglevel", "warning"]
    volumes:
      - redis_data:/data

  agents:
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "curl -sf http://localhost:8000/health || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 20s   # aguarda inicialização do FastAPI
    depends_on:
      postgres:
        condition: service_healthy   # espera pg_isready, não só container up
      qdrant:
        condition: service_healthy
      redis:
        condition: service_healthy
```

Aplicar o mesmo padrão em `docker-compose.yml` para os serviços: `litellm`, `n8n`, `evolution-api`, `prometheus`, `grafana`.

### 2. `scripts/backup.sh` — backup diário automatizado

```bash
#!/usr/bin/env bash
# scripts/backup.sh
# Executar via cron: 0 3 * * * /home/vector/Kirin/scripts/backup.sh >> /var/log/kirin-backup.log 2>&1

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backups/kirin}"
DATE=$(date +%Y%m%d_%H%M%S)
RETAIN_DAYS="${RETAIN_DAYS:-7}"

mkdir -p "$BACKUP_DIR"

# 1. PostgreSQL — dump completo
echo "[${DATE}] Iniciando backup PostgreSQL..."
docker exec kirin-postgres pg_dump -U kirin kirin \
  | gzip > "${BACKUP_DIR}/postgres_${DATE}.sql.gz"
echo "[${DATE}] PostgreSQL: OK ($(du -sh "${BACKUP_DIR}/postgres_${DATE}.sql.gz" | cut -f1))"

# 2. Qdrant — snapshot via API REST
echo "[${DATE}] Iniciando snapshot Qdrant..."
curl -sf -X POST "http://localhost:6333/collections/kirin_enrichment/snapshots" \
  -o "${BACKUP_DIR}/qdrant_snapshot_${DATE}.json"
echo "[${DATE}] Qdrant: OK"

# 3. Redis — dump RDB (já configurado com --save 60 1)
docker exec kirin-redis redis-cli BGSAVE
sleep 2
docker cp kirin-redis:/data/dump.rdb "${BACKUP_DIR}/redis_${DATE}.rdb"
echo "[${DATE}] Redis: OK"

# 4. Limpar backups antigos
find "$BACKUP_DIR" -name "*.gz" -mtime +${RETAIN_DAYS} -delete
find "$BACKUP_DIR" -name "*.rdb" -mtime +${RETAIN_DAYS} -delete
find "$BACKUP_DIR" -name "*.json" -mtime +${RETAIN_DAYS} -delete

echo "[${DATE}] Backup concluído. Arquivos em ${BACKUP_DIR}:"
ls -lh "$BACKUP_DIR" | tail -10
```

### 3. Instalar o cron

```bash
chmod +x /home/vector/Kirin/scripts/backup.sh

# Adicionar ao crontab do usuário vector:
crontab -e
# Adicionar linha:
0 3 * * * /home/vector/Kirin/scripts/backup.sh >> /var/log/kirin-backup.log 2>&1
```

### 4. Alerta de backup no Prometheus

```yaml
# prometheus/alerts.yml — adicionar regra:
- alert: BackupStale
  expr: (time() - kirin_last_backup_timestamp) > 86400
  for: 1h
  labels:
    severity: warning
  annotations:
    summary: "Backup do Kirin não executado há mais de 24h"
```

Para expor `kirin_last_backup_timestamp`, adicionar ao final do `backup.sh`:

```bash
# Atualiza métrica de timestamp do último backup
echo "kirin_last_backup_timestamp $(date +%s)" \
  > /var/lib/prometheus/node-exporter/kirin_backup.prom
```

---

## Critérios de Aceitação

- [ ] `docker-compose up -d` sobe todos os serviços com `restart: unless-stopped`
- [ ] `docker stop kirin-agents && sleep 5 && docker ps` mostra o container reiniciando
- [ ] `agents` só inicia após PostgreSQL passar no healthcheck (`pg_isready`)
- [ ] `scripts/backup.sh` executa sem erro e cria os 3 arquivos de backup
- [ ] Backup de 7 dias: executar o script 8 vezes com datas diferentes confirma que arquivos antigos são removidos
- [ ] Restauração testada: `psql -U kirin kirin < backup.sql.gz` recupera os dados
