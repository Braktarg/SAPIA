#!/usr/bin/env bash
set -euo pipefail
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="/backups/sapia_${POSTGRES_DB}_${STAMP}.sql.gz"
echo "Backup -> ${OUT}"
PGPASSWORD="${POSTGRES_PASSWORD}" pg_dump -h "${PGHOST:-db}" -U "${POSTGRES_USER}" "${POSTGRES_DB}" | gzip > "${OUT}"
find /backups -name 'sapia_*.sql.gz' -mtime +14 -delete
echo "OK"
