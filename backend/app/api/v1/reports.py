from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import require_teacher
from app.core.database import get_db
from app.models import User
from app.services.audit_service import AuditServiceError
from app.services.report_service import export_course_csv, export_course_xlsx, import_course_students_csv

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/course/{course_id}/csv")
def download_course_csv(
    course_id: int,
    db: Annotated[Session, Depends(get_db)],
    teacher: Annotated[User, Depends(require_teacher)],
    anonymize: bool = Query(default=False),
) -> Response:
    try:
        content, filename = export_course_csv(db, teacher, course_id, anonymize=anonymize)
    except AuditServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    return Response(
        content=content.encode("utf-8-sig"),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/course/{course_id}/xlsx")
def download_course_xlsx(
    course_id: int,
    db: Annotated[Session, Depends(get_db)],
    teacher: Annotated[User, Depends(require_teacher)],
    anonymize: bool = Query(default=False),
) -> Response:
    try:
        content, filename = export_course_xlsx(db, teacher, course_id, anonymize=anonymize)
    except AuditServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/course/{course_id}/import-csv")
async def upload_course_students_csv(
    course_id: int,
    db: Annotated[Session, Depends(get_db)],
    teacher: Annotated[User, Depends(require_teacher)],
    file: UploadFile = File(...),
) -> dict[str, int]:
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="Archivo CSV debe estar en UTF-8") from exc
    try:
        return import_course_students_csv(db, teacher, course_id, text)
    except AuditServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
