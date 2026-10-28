from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import require_student
from app.core.database import get_db
from app.models import User
from app.schemas.recommendation import (
    StudentFeedbackRead,
    StudentFeedbackRequest,
    StudentRecommendationRead,
)
from app.services.recommendation_service import (
    RecommendationServiceError,
    get_student_recommendation,
    list_student_visible_recommendations,
    student_can_download_document,
    submit_student_feedback,
)

router = APIRouter(prefix="/student", tags=["student"])


@router.get("/recommendations", response_model=list[StudentRecommendationRead])
def student_recommendations_list(
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
) -> list[dict]:
    return list_student_visible_recommendations(db, student)


@router.get("/recommendations/{recommendation_id}", response_model=StudentRecommendationRead)
def student_recommendation_detail(
    recommendation_id: int,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
) -> dict:
    try:
        return get_student_recommendation(db, student, recommendation_id)
    except RecommendationServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post(
    "/recommendations/{recommendation_id}/feedback",
    response_model=StudentFeedbackRead,
    status_code=201,
)
def student_recommendation_feedback(
    recommendation_id: int,
    body: StudentFeedbackRequest,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
) -> dict:
    try:
        return submit_student_feedback(
            db,
            student,
            recommendation_id,
            difficulty_rating=body.difficulty_rating,
        )
    except RecommendationServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/documents/{document_id}/download")
def download_student_document(
    document_id: int,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
) -> FileResponse:
    try:
        doc = student_can_download_document(db, student, document_id)
    except RecommendationServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    path = Path(doc.storage_path)
    return FileResponse(
        path=path,
        media_type="application/pdf",
        filename=doc.original_filename,
    )
