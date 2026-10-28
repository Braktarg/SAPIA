from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_teacher
from app.core.database import get_db
from app.models import User
from app.services.teacher_dashboard_service import (
    get_course_analytics,
    get_student_teacher_summary,
    get_teacher_setup_status,
)

router = APIRouter(prefix="/teacher", tags=["teacher"])


@router.get("/setup-status")
def teacher_setup_status(
    db: Annotated[Session, Depends(get_db)],
    teacher: Annotated[User, Depends(require_teacher)],
    course_id: int | None = Query(default=None),
) -> dict:
    return get_teacher_setup_status(db, teacher, course_id=course_id)


@router.get("/courses/{course_id}/analytics")
def course_analytics(
    course_id: int,
    db: Annotated[Session, Depends(get_db)],
    teacher: Annotated[User, Depends(require_teacher)],
) -> dict:
    try:
        return get_course_analytics(db, teacher, course_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/students/{student_id}/summary")
def student_summary_for_teacher(
    student_id: int,
    db: Annotated[Session, Depends(get_db)],
    teacher: Annotated[User, Depends(require_teacher)],
) -> dict:
    try:
        return get_student_teacher_summary(db, teacher, student_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
