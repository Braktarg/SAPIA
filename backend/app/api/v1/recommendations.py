from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import require_teacher
from app.core.database import get_db
from app.core.enums import RecommendationStatus
from app.models import Recommendation, User
from app.schemas.recommendation import (
    CourseBatchGenerateResponse,
    GenerateCourseRecommendationRequest,
    GenerateRecommendationRequest,
    RecommendationRead,
    RecommendationSummary,
    ValidateRecommendationRequest,
)
from app.services.export_service import build_recommendation_pdf
from app.services.recommendation_service import (
    RecommendationServiceError,
    generate_for_course,
    generate_for_student,
    get_recommendation_detail,
    list_inbox,
    recommendation_to_summary,
    validate_recommendation,
)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.post("/generate", response_model=RecommendationRead, status_code=status.HTTP_201_CREATED)
def generate_recommendation_endpoint(
    body: GenerateRecommendationRequest,
    db: Annotated[Session, Depends(get_db)],
    teacher: Annotated[User, Depends(require_teacher)],
) -> dict:
    try:
        rec, _ = generate_for_student(
            db,
            teacher,
            student_id=body.student_id,
            course_id=body.course_id,
            planning_topic=body.planning_topic,
            ai_consent_accepted=body.ai_consent_accepted,
            consent_version=body.consent_version,
        )
        detail = get_recommendation_detail(db, teacher, rec.id)
    except RecommendationServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return detail


@router.post("/generate-course", response_model=CourseBatchGenerateResponse, status_code=status.HTTP_201_CREATED)
def generate_course_recommendation_endpoint(
    body: GenerateCourseRecommendationRequest,
    db: Annotated[Session, Depends(get_db)],
    teacher: Annotated[User, Depends(require_teacher)],
) -> dict:
    try:
        result = generate_for_course(
            db,
            teacher,
            course_id=body.course_id,
            planning_topic=body.planning_topic,
            include_per_student=body.include_per_student,
            ai_consent_accepted=body.ai_consent_accepted,
            consent_version=body.consent_version,
        )
        course_detail = get_recommendation_detail(db, teacher, result.course_recommendation.id)
        student_summaries = []
        for rec in result.student_recommendations:
            student = db.query(User).filter(User.id == rec.student_id).first()
            student_summaries.append(recommendation_to_summary(rec, student))
    except RecommendationServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return {
        "course": course_detail,
        "students": student_summaries,
        "student_count": len(student_summaries),
    }


@router.get("/inbox", response_model=list[RecommendationSummary])
def recommendations_inbox(
    db: Annotated[Session, Depends(get_db)],
    teacher: Annotated[User, Depends(require_teacher)],
    course_id: int | None = Query(default=None),
    status_filter: str | None = Query(default=RecommendationStatus.PENDING.value, alias="status"),
) -> list[dict]:
    try:
        return list_inbox(db, teacher, course_id=course_id, status=status_filter)
    except RecommendationServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/{recommendation_id}/export.pdf")
def export_recommendation_pdf(
    recommendation_id: int,
    db: Annotated[Session, Depends(get_db)],
    teacher: Annotated[User, Depends(require_teacher)],
) -> Response:
    try:
        detail = get_recommendation_detail(db, teacher, recommendation_id)
    except RecommendationServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    rec = db.query(Recommendation).filter(Recommendation.id == recommendation_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="No encontrada")
    t = db.query(User).filter(User.id == rec.teacher_id).first()
    pdf = build_recommendation_pdf(rec, detail["student_name"], t.full_name if t else "Docente")
    filename = f"sapia_recomendacion_{recommendation_id}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{recommendation_id}", response_model=RecommendationRead)
def get_recommendation(
    recommendation_id: int,
    db: Annotated[Session, Depends(get_db)],
    teacher: Annotated[User, Depends(require_teacher)],
) -> dict:
    try:
        return get_recommendation_detail(db, teacher, recommendation_id)
    except RecommendationServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/{recommendation_id}/validate", response_model=RecommendationRead)
def validate_recommendation_endpoint(
    recommendation_id: int,
    body: ValidateRecommendationRequest,
    db: Annotated[Session, Depends(get_db)],
    teacher: Annotated[User, Depends(require_teacher)],
) -> dict:
    try:
        validate_recommendation(
            db,
            teacher,
            recommendation_id,
            action=body.action,
            reason=body.reason,
            edited_body=body.edited_body,
        )
        return get_recommendation_detail(db, teacher, recommendation_id)
    except RecommendationServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
