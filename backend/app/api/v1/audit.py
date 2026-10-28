from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import require_teacher
from app.core.database import get_db
from app.models import User
from app.schemas.audit import TimelineResponse
from app.services.audit_service import AuditServiceError, get_course_timeline
from app.services.report_service import export_course_csv

router = APIRouter(tags=["audit"])


@router.get("/audit/timeline", response_model=TimelineResponse)
def audit_timeline(
    db: Annotated[Session, Depends(get_db)],
    teacher: Annotated[User, Depends(require_teacher)],
    course_id: int = Query(...),
    student_id: int | None = Query(default=None),
    recommendation_id: int | None = Query(default=None),
    from_date: datetime | None = Query(default=None),
    to_date: datetime | None = Query(default=None),
) -> TimelineResponse:
    try:
        return get_course_timeline(
            db,
            teacher,
            course_id=course_id,
            student_id=student_id,
            recommendation_id=recommendation_id,
            from_date=from_date,
            to_date=to_date,
        )
    except AuditServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
