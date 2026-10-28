# SAPIA — despliegue cloud (Railway + Vercel)

## URLs en producción (julio 2026)

| Servicio | URL |
|----------|-----|
| **Frontend** | https://sapia-prototipo.vercel.app |
| **API** | https://api-production-7d048.up.railway.app |
| **Health** | https://api-production-7d048.up.railway.app/health |
| **API docs** | https://api-production-7d048.up.railway.app/docs |

## Arquitectura

| Servicio | Plataforma | URL típica |
|----------|------------|------------|
| API FastAPI | **Railway** | `https://sapia-api-production.up.railway.app` |
| PostgreSQL + pgvector | **Railway** (plugin Postgres) | interno `DATABASE_URL` |
| Frontend Next.js | **Vercel** | `https://sapia.vercel.app` |

## 1. Railway — API + base de datos

> **Monorepo:** hay dos formas válidas de desplegar la API:
> 1. **Raíz del repo** (GitHub auto-deploy): `sapia/railway.toml` + `sapia/Dockerfile.railway` (contexto monorepo).
> 2. **Solo backend** (CLI): `cd backend` → `railway up` usa `backend/railway.toml`.
>
> Si Railpack dice *«Script start.sh not found»* o *«could not determine how to build»*, el servicio **api** está construyendo desde la raíz **sin** Dockerfile: redeploy tras subir `railway.toml` en la raíz, o en Railway → servicio **api** → Settings → **Root Directory** = `backend`.
>
> El servicio **Postgres** no debe tener repositorio conectado; un «deploy failed» en Postgres es normal (ignorar; la BD sigue online con su volumen).

### Crear proyecto

1. [railway.app](https://railway.app) → **New Project**
2. **Add PostgreSQL** (plan hobby; activar extensión vector en Query si falla migración):
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
3. **New Service** → **GitHub Repo** o **Empty** + CLI:
   ```powershell
   cd c:\Users\Niko\Desktop\Empresa\sapia\backend
   npx @railway/cli login
   npx @railway/cli init
   npx @railway/cli add --database postgres
   npx @railway/cli add --service api
   npx @railway/cli service api
   npx @railway/cli up
   ```

### Variables de entorno (servicio API)

| Variable | Valor |
|----------|--------|
| `DATABASE_URL` | Referencia `${{Postgres.DATABASE_URL}}` |
| `JWT_SECRET` | Cadena aleatoria larga (≥32 chars) |
| `CORS_ORIGINS` | `https://sapia-prototipo.vercel.app,http://localhost:3000` |
| `FRONTEND_URL` | `https://sapia-prototipo.vercel.app` |
| `UPLOAD_DIR` | `/tmp/uploads` |
| `OPENAI_API_KEY` | Clave OpenAI (obligatoria para GPT real; sin ella = modo plantilla) |
| `OPENAI_CHAT_MODEL` | `gpt-4o-mini` |
| `EMBEDDING_DIMENSIONS` | `384` |
| `RAG_TOP_K` | `5` |
| `OPENAI_TIMEOUT_SECONDS` | `120` |
| `MAX_UPLOAD_MB` | `20` |
| `MAX_PDF_PAGES` | `20` |

Railway inyecta `PORT` automáticamente. El `Dockerfile.railway` ejecuta migraciones, seed demo y arranca uvicorn.

### Dominio público API

Railway → servicio API → **Settings** → **Networking** → **Generate Domain**

Copia la URL (ej. `https://sapia-api-production.up.railway.app`).

### Verificar

```bash
curl https://TU-API.railway.app/health
# {"status":"ok"}
```

## 2. Vercel — frontend

### Desde CLI

```powershell
cd c:\Users\Niko\Desktop\Empresa\sapia\frontend
npx vercel login
npx vercel --prod
```

### Variables de entorno (Vercel dashboard)

| Variable | Valor |
|----------|--------|
| `NEXT_PUBLIC_API_URL` | `https://TU-API.railway.app` (sin `/api` al final) |

**Root Directory** del proyecto en Vercel: `frontend` (si el repo es la carpeta `sapia/`).

### Actualizar CORS en Railway

Tras obtener la URL de Vercel, actualiza en Railway:

```
CORS_ORIGINS=https://sapia-xxx.vercel.app
FRONTEND_URL=https://sapia-xxx.vercel.app
```

Redeploy API si cambias CORS.

## 3. Credenciales demo (post-deploy)

| Rol | Email | Contraseña |
|-----|-------|------------|
| Docente | docente@demo.sapia.cl | Sapia2026! |
| Estudiante | estudiante@demo.sapia.cl | Sapia2026! |
| Coordinador | pie@demo.sapia.cl | Sapia2026! |

Registro público: `/register` con código `DEMO-SAPIA`.

## 4. Limitaciones conocidas

- **PDFs subidos** en Railway viven en disco efímero (`/tmp/uploads`); se pierden al redeploy. Para producción real usar S3/R2.
- **pgvector** debe estar habilitado en Postgres Railway.
- Sin `OPENAI_API_KEY` el sistema usa **modo plantilla** (degradado) pero el flujo MitL funciona.

## 5. Comandos útiles

```powershell
# Logs API
npx @railway/cli logs

# Redeploy
npx @railway/cli up

# Redeploy frontend
cd frontend && npx vercel --prod
```
