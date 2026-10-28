#!/usr/bin/env bash
set -euo pipefail
FILE="${1:?Uso: restore_db.sh archivo.sql.gz}"
PGPASSWORD="${POSTGRES_PASSWORD}" gunzip -c "$FILE" | psql -h "${PGHOST:-db}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}"
echo "Restaurado: $FILE"
