from fastapi import APIRouter

from app.api.v1 import admin, audit, auth, courses, diagnostic, documents, recommendations, reports, student, teacher

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(admin.router)
api_router.include_router(courses.router)
api_router.include_router(diagnostic.router)
api_router.include_router(documents.router)
api_router.include_router(recommendations.router)
api_router.include_router(student.router)
api_router.include_router(audit.router)
api_router.include_router(reports.router)
api_router.include_router(teacher.router)
