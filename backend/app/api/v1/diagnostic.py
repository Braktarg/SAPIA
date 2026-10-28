from datetime import datetime

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_student, require_teacher
from app.core.database import get_db
from app.core.enums import UserRole
from app.models import DiagnosticItem, Enrollment, User
from app.schemas.diagnostic import (
    DiagnosticItemRead,
    DiagnosticStatusResponse,
    DiagnosticSubmitRequest,
    PedagogicalProfileRead,
)
from app.services.diagnostic_service import (
    complete_diagnostic,
    get_latest_profile,
    profile_to_read,
    student_has_profile,
)
from app.services.teacher_dashboard_service import student_attention_level
from app.services.auth_service import require_roles

router = APIRouter(tags=["diagnostic"])


@router.get("/diagnostic/items", response_model=list[DiagnosticItemRead])
def list_diagnostic_items(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[DiagnosticItemRead]:
    require_roles(current_user, {UserRole.STUDENT, UserRole.TEACHER, UserRole.ADMIN, UserRole.COORDINATOR})
    items = db.query(DiagnosticItem).order_by(DiagnosticItem.sort_order).all()
    result = []
    for item in items:
        result.append(
            DiagnosticItemRead(
                id=item.id,
                sort_order=item.sort_order,
                question_text=item.question_text,
                options=json.loads(item.options_json),
            )
        )
    return result


@router.get("/diagnostic/status", response_model=DiagnosticStatusResponse)
def diagnostic_status(
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
) -> DiagnosticStatusResponse:
    profile = get_latest_profile(db, student.id)
    return DiagnosticStatusResponse(has_profile=profile is not None, session_id=profile.session_id if profile else None)


@router.post("/diagnostic/submit", response_model=PedagogicalProfileRead, status_code=status.HTTP_201_CREATED)
def submit_diagnostic(
    body: DiagnosticSubmitRequest,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
) -> dict:
    profile = complete_diagnostic(
        db,
        student,
        body.answers,
        consent_accepted=body.consent_accepted,
        consent_version=body.consent_version,
    )
    return profile_to_read(profile)


@router.get("/students/me/profile", response_model=PedagogicalProfileRead)
def my_profile(
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
) -> dict:
    profile = get_latest_profile(db, student.id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Perfil no generado")
    return profile_to_read(profile)


@router.get("/students/{student_id}/profile", response_model=PedagogicalProfileRead)
def student_profile_for_teacher(
    student_id: int,
    db: Annotated[Session, Depends(get_db)],
    teacher: Annotated[User, Depends(require_teacher)],
) -> dict:
    student = db.query(User).filter(User.id == student_id, User.org_id == teacher.org_id).first()
    if not student or student.role != UserRole.STUDENT.value:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Estudiante no encontrado")
    profile = get_latest_profile(db, student_id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Perfil no generado")
    return profile_to_read(profile)


@router.get("/students", response_model=list[dict])
def list_students_with_profile_flag(
    db: Annotated[Session, Depends(get_db)],
    teacher: Annotated[User, Depends(require_teacher)],
    course_id: int | None = Query(default=None),
) -> list[dict]:
    query = db.query(User).filter(
        User.org_id == teacher.org_id,
        User.role == UserRole.STUDENT.value,
        User.is_active.is_(True),
    )
    if course_id is not None:
        query = query.join(Enrollment, Enrollment.student_id == User.id).filter(
            Enrollment.course_id == course_id
        )
    students = query.order_by(User.full_name).all()
    return [
        {
            "id": s.id,
            "full_name": s.full_name,
            "email": s.email,
            "birth_year": s.birth_year,
            "age": datetime.now().year - s.birth_year if s.birth_year else None,
            "has_profile": (hp := student_has_profile(db, s.id)),
            "attention_level": student_attention_level(db, s.id, hp),
        }
        for s in students
    ]
