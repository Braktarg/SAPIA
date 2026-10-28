# SAPIA — Release 1 (MVP)

Sistema de Apoyo Pedagógico basado en IA para docentes con estudiantes neurodivergentes (PIE).

## Stack

- **Backend:** FastAPI + SQLAlchemy + Alembic + JWT
- **Frontend:** Next.js 14 (App Router)
- **DB:** PostgreSQL 16 + pgvector

## Inicio rápido (Docker)

```bash
cd sapia
cp .env.example .env
docker compose up --build
```

- API: http://localhost:8000/docs
- Web: http://localhost:3000/login

### Usuarios demo (seed automático)

| Rol | Email | Contraseña |
|-----|-------|------------|
| Admin | admin@demo.sapia.cl | Sapia2026! |
| Docente | docente@demo.sapia.cl | Sapia2026! |
| Estudiante | estudiante@demo.sapia.cl | Sapia2026! |

**Registro público (RF-01/02):** `/register` con código institucional `DEMO-SAPIA`.

### Cumplimiento R1 (brechas cerradas)

| Requisito | Implementación |
|-----------|----------------|
| RF-01/02 | `POST /api/v1/auth/register` + página `/register` |
| RF-47 | Trazabilidad 7 eslabones (consumo + resultado pedagógico) |
| RF-48 | Export CSV + Excel (`/reports/course/{id}/xlsx`) |
| Import CSV | `POST /reports/course/{id}/import-csv` (matrícula) |
| RNF-37 | Checkbox TyC en test diagnóstico y generación IA |
| RNF-27 | `langchain-text-splitters` en `rag/chunking.py` |
| RNF-04/15/35 | `deploy/` — nginx HTTPS, `docker-compose.prod.yml`, backups |

## Desarrollo local (sin Docker web)

```bash
# Terminal 1 — solo DB
docker compose up db

# Terminal 2 — API
cd backend
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
set DATABASE_URL=postgresql+psycopg://sapia:sapia_dev@localhost:5432/sapia
alembic upgrade head
python scripts/seed_demo.py
uvicorn app.main:app --reload

# Terminal 3 — Frontend
cd frontend
npm install
npm run dev
```

## Tests y QA (S8)

```bash
cd backend
python scripts/run_qa.py    # pytest + cobertura ≥70% módulos críticos
cd ../frontend && npm test
```

Informe piloto UAT: `docs/INFORME_PILOTO_R1.md`

## Manuales

- **Instalación:** `docs/Manual_Instalacion_SAPIA.md`
- **Usuario (docente/estudiante/admin):** `docs/Manual_Usuario_SAPIA.md`

Copia para entrega académica: `PDT/Informe 2/redaccion/manuales/`

### Staging local

```bash
docker compose -f docker-compose.yml -f docker-compose.staging.yml up --build
# Web http://localhost:3001 | API http://localhost:8001
```

## Sprints

Ver `.claude/plans/sapia-release-1-mvp.plan.md` y `PDT/redaccion/anexos/Anexo_G_Carta_Gantt.md`.

| Sprint | Estado |
|--------|--------|
| S1 Auth + scaffold | ✅ |
| S2 Test diagnóstico + Random Forest | ✅ |
| S3 RAG PDF | ✅ |
| S4 Motor recomendación | ✅ |
| S5 MitL validación | ✅ |
| S6 Vista estudiante | ✅ |
| S7 Dashboard + CSV | ✅ |
| S8 QA/UAT | ✅ |

### S8 — QA / UAT

- Smoke E2E: `tests/test_e2e_smoke.py` (flujo completo PT-ST-001).
- Cobertura: `scripts/run_qa.py` (≥70% módulos críticos).
- CI: backend QA + frontend Vitest + build.
- Plantilla informe piloto: `docs/INFORME_PILOTO_R1.md`.

### S3 — Biblioteca curricular

- Docente: `/docente/biblioteca` — subir PDF (≤20 MB, ≤20 páginas), asociar unidad y listar/eliminar documentos.
- API: `POST/GET /api/v1/courses/{id}/documents`, `DELETE /api/v1/documents/{id}`.
- Embeddings locales (384d) por defecto; opcional OpenAI con `OPENAI_API_KEY`.

### S4 — Motor de recomendación

- Docente: `/docente/recomendaciones` — generar propuesta (perfil + RAG) y ver bandeja Pendiente con explicación XAI.
- API: `POST /api/v1/recommendations/generate`, `GET /api/v1/recommendations/inbox`, `GET /api/v1/recommendations/{id}`.
- Retrieval top-5 por similitud coseno; generación LLM opcional con fallback a plantilla (RNF-15).

### S5 — Validación MitL

- Docente: botones **Aceptar / Rechazar / Editar** en `/docente/recomendaciones` (motivo obligatorio al rechazar o editar).
- API: `POST /api/v1/recommendations/{id}/validate`, `GET /api/v1/student/recommendations`.
- Auditoría persistida en `recommendation_validations` y `audit_events`.

### S6 — Vista estudiante (J-05)

- Estudiante: `/estudiante/recomendaciones` — solo ítems **accepted** y **edited**; explicación y PDFs vinculados.
- Perfil: `/estudiante/perfil` | Test: `/estudiante/diagnostico`.
- API: `GET /api/v1/student/recommendations`, `GET /api/v1/student/recommendations/{id}`, `GET /api/v1/student/documents/{id}/download`.

### S7 — Panel docente (J-06)

- Docente: `/docente/panel` — KPIs (TAI, pendientes), trazabilidad en 5 eslabones y export CSV.
- API: `GET /api/v1/audit/timeline`, `GET /api/v1/reports/course/{id}/csv` (opción `?anonymize=true`).
