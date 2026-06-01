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
echo "[${DATE}] Iniciando dump Redis..."
docker exec kirin-redis redis-cli BGSAVE
sleep 2
docker cp kirin-redis:/data/dump.rdb "${BACKUP_DIR}/redis_${DATE}.rdb"
echo "[${DATE}] Redis: OK"

# 4. Limpar backups antigos
echo "[${DATE}] Limpando backups antigos (>${RETAIN_DAYS} dias)..."
find "$BACKUP_DIR" -name "*.gz" -mtime +${RETAIN_DAYS} -delete
find "$BACKUP_DIR" -name "*.rdb" -mtime +${RETAIN_DAYS} -delete
find "$BACKUP_DIR" -name "*.json" -mtime +${RETAIN_DAYS} -delete

# 5. Atualizar métrica de timestamp do último backup
echo "kirin_last_backup_timestamp $(date +%s)" \
  > /var/lib/prometheus/node-exporter/kirin_backup.prom 2>/dev/null || true

echo "[${DATE}] Backup concluído. Arquivos em ${BACKUP_DIR}:"
ls -lh "$BACKUP_DIR" | tail -10
