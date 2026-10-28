# SAPIA — despliegue staging/producción (RNF-04, RNF-15, RNF-35)

## Ambientes

| Archivo | Uso | Puertos |
|---------|-----|---------|
| `docker-compose.yml` | Desarrollo local | 3000 / 8000 / 5432 |
| `docker-compose.staging.yml` | Staging alternativo | 3001 / 8001 / 5433 |
| `deploy/docker-compose.prod.yml` | Staging/prod con TLS y backups | 443 / 80 |

## Producción / staging con HTTPS

```bash
cd sapia
cp .env.example .env   # configurar secrets
mkdir -p deploy/backups deploy/certs
# Certificados (Let's Encrypt o autofirmado para prueba):
# openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
#   -keyout deploy/certs/privkey.pem -out deploy/certs/fullchain.pem \
#   -subj "/CN=staging.sapia.local"
docker compose -f deploy/docker-compose.prod.yml up -d --build
```

- **HTTPS** termina en nginx (TLS 1.2+).
- **Backups PG** diarios en `deploy/backups/` (servicio `backup`).
- Restaurar: `deploy/scripts/restore_db.sh <archivo.sql.gz>`.

## Variables obligatorias producción

- `POSTGRES_PASSWORD`, `OPENAI_API_KEY`, `JWT_SECRET`
- `CORS_ORIGINS=https://staging.tudominio.cl`
- `NEXT_PUBLIC_API_URL=https://staging.tudominio.cl/api`

## CSV import/export

- Export: `GET /api/v1/reports/course/{id}/csv` o `/xlsx`
- Import matrícula: `POST /api/v1/reports/course/{id}/import-csv` (columnas `full_name,email,birth_year`)

## Registro público (RF-01/02)

Código demo: `DEMO-SAPIA` — `POST /api/v1/auth/register`
