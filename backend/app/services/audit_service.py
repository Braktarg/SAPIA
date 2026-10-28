import csv
import io
import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.enums import RecommendationScope, RecommendationStatus, UserRole
from app.models import (
    AuditEvent,
    Course,
    CurricularDocument,
    DocumentChunk,
    Enrollment,
    PedagogicalProfile,
    Recommendation,
    RecommendationFeedback,
    RecommendationValidation,
    User,
)
from app.schemas.audit import (
    CourseDashboardSummary,
    RecommendationChain,
    TimelineResponse,
    TimelineStep,
)
from app.services.auth_service import log_audit
from app.services.diagnostic_service import student_has_profile
from app.services.document_service import teacher_can_access_course


class AuditServiceError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _course_students(db: Session, course_id: int) -> list[User]:
    return (
        db.query(User)
        .join(Enrollment, Enrollment.student_id == User.id)
        .filter(Enrollment.course_id == course_id, User.role == UserRole.STUDENT.value)
        .order_by(User.full_name)
        .all()
    )


def build_course_summary(db: Session, course: Course) -> CourseDashboardSummary:
    students = _course_students(db, course.id)
    with_profile = sum(1 for s in students if student_has_profile(db, s.id))
    recs = db.query(Recommendation).filter(Recommendation.course_id == course.id).all()
    pending = sum(1 for r in recs if r.status == RecommendationStatus.PENDING.value)
    published = sum(
        1
        for r in recs
        if r.status in (RecommendationStatus.ACCEPTED.value, RecommendationStatus.EDITED.value)
    )
    tai_pct = round((with_profile / len(students) * 100) if students else 0.0, 1)
    return CourseDashboardSummary(
        course_id=course.id,
        course_name=course.name,
        students_total=len(students),
        students_with_profile=with_profile,
        recommendations_total=len(recs),
        recommendations_pending=pending,
        recommendations_published=published,
        tai_pct=tai_pct,
    )


def _profile_step(db: Session, rec: Recommendation) -> TimelineStep:
    if rec.scope == RecommendationScope.COURSE.value:
        count = 0
        try:
            count = int(json.loads(rec.context_json or "{}").get("student_count", 0))
        except (json.JSONDecodeError, TypeError, ValueError):
            count = 0
        return TimelineStep(
            order=1,
            stage="profile",
            label="Perfiles del curso",
            detail=f"{count or 'Varios'} perfiles pedagógicos considerados",
            timestamp=rec.created_at,
        )
    profile = (
        db.query(PedagogicalProfile)
        .filter(
            PedagogicalProfile.student_id == rec.student_id,
            PedagogicalProfile.version == rec.profile_version,
        )
        .first()
    )
    ts = profile.created_at if profile else None
    return TimelineStep(
        order=1,
        stage="profile",
        label="Perfil pedagógico",
        detail=f"Perfil v{rec.profile_version} utilizado para personalización",
        timestamp=ts,
    )


def _chunk_ids_from_source_json(raw: str) -> list[int]:
    data = json.loads(raw or "[]")
    ids: list[int] = []
    for item in data:
        if isinstance(item, dict):
            ids.append(int(item["id"]))
        else:
            ids.append(int(item))
    return ids


def _rag_step(db: Session, rec: Recommendation) -> TimelineStep:
    chunk_ids = _chunk_ids_from_source_json(rec.source_chunk_ids_json or "[]")
    chunk_count = len(chunk_ids)
    units: list[str] = []
    if chunk_ids:
        rows = (
            db.query(DocumentChunk, CurricularDocument)
            .join(CurricularDocument, CurricularDocument.id == DocumentChunk.document_id)
            .filter(DocumentChunk.id.in_(chunk_ids))
            .all()
        )
        units = sorted({doc.unit_name for _c, doc in rows})
    doc_ts = (
        db.query(CurricularDocument.created_at)
        .filter(CurricularDocument.course_id == rec.course_id)
        .order_by(CurricularDocument.created_at.desc())
        .first()
    )
    return TimelineStep(
        order=2,
        stage="rag",
        label="Recuperación RAG",
        detail=f"{chunk_count} fragmentos desde unidades: {', '.join(units) if units else 'N/A'}",
        timestamp=doc_ts[0] if doc_ts else rec.created_at,
    )


def _ai_step(rec: Recommendation) -> TimelineStep:
    mode = "plantilla" if rec.degraded_mode else "LLM"
    return TimelineStep(
        order=3,
        stage="ai",
        label="Propuesta IA",
        detail=f"Recomendación generada ({mode}): «{rec.title}»",
        timestamp=rec.created_at,
    )


def _teacher_step(db: Session, rec: Recommendation) -> TimelineStep:
    validation = (
        db.query(RecommendationValidation)
        .filter(RecommendationValidation.recommendation_id == rec.id)
        .order_by(RecommendationValidation.created_at.desc())
        .first()
    )
    if validation:
        action_labels = {
            "accept": "Aceptada",
            "reject": "Rechazada",
            "edit": "Editada y aprobada",
        }
        label = action_labels.get(validation.action, validation.action)
        detail = f"Docente: {label}"
        if validation.reason:
            detail += f" — {validation.reason}"
        return TimelineStep(
            order=4,
            stage="teacher",
            label="Validación docente (MitL)",
            detail=detail,
            timestamp=validation.created_at,
        )
    return TimelineStep(
        order=4,
        stage="teacher",
        label="Validación docente (MitL)",
        detail="Pendiente de revisión",
        timestamp=None,
    )


def _student_step(db: Session, rec: Recommendation) -> TimelineStep:
    if rec.scope == RecommendationScope.COURSE.value:
        return TimelineStep(
            order=5,
            stage="student",
            label="Publicación estudiantes",
            detail="Planificación grupal para uso docente (no se publica a alumnos)",
            timestamp=None,
        )
    validation = (
        db.query(RecommendationValidation)
        .filter(
            RecommendationValidation.recommendation_id == rec.id,
            RecommendationValidation.action.in_(["accept", "edit"]),
        )
        .order_by(RecommendationValidation.created_at.desc())
        .first()
    )
    if rec.status in (RecommendationStatus.ACCEPTED.value, RecommendationStatus.EDITED.value) and validation:
        return TimelineStep(
            order=5,
            stage="student",
            label="Publicación estudiante",
            detail="Recomendación publicada en «Mis recomendaciones»",
            timestamp=validation.created_at,
        )
    return TimelineStep(
        order=5,
        stage="student",
        label="Publicación estudiante",
        detail="Aún no publicada al estudiante",
        timestamp=None,
    )


def _consumption_step(db: Session, rec: Recommendation) -> TimelineStep:
    if rec.scope == RecommendationScope.COURSE.value or rec.student_id is None:
        return TimelineStep(
            order=6,
            stage="consumption",
            label="Consumo estudiante",
            detail="No aplica (recomendación grupal)",
            timestamp=None,
        )
    view = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.entity_type == "recommendation",
            AuditEvent.entity_id == str(rec.id),
            AuditEvent.action == "student_recommendation_view",
        )
        .order_by(AuditEvent.created_at.desc())
        .first()
    )
    if view:
        return TimelineStep(
            order=6,
            stage="consumption",
            label="Consumo estudiante",
            detail="El estudiante abrió la recomendación publicada",
            timestamp=view.created_at,
        )
    if rec.status in (RecommendationStatus.ACCEPTED.value, RecommendationStatus.EDITED.value):
        return TimelineStep(
            order=6,
            stage="consumption",
            label="Consumo estudiante",
            detail="Publicada; consumo aún no registrado",
            timestamp=None,
        )
    return TimelineStep(
        order=6,
        stage="consumption",
        label="Consumo estudiante",
        detail="Pendiente de publicación",
        timestamp=None,
    )


def _result_step(db: Session, rec: Recommendation) -> TimelineStep:
    if rec.scope == RecommendationScope.COURSE.value or rec.student_id is None:
        return TimelineStep(
            order=7,
            stage="result",
            label="Resultado pedagógico",
            detail="No aplica (recomendación grupal)",
            timestamp=None,
        )
    feedback = (
        db.query(RecommendationFeedback)
        .filter(RecommendationFeedback.recommendation_id == rec.id)
        .order_by(RecommendationFeedback.created_at.desc())
        .first()
    )
    if feedback:
        return TimelineStep(
            order=7,
            stage="result",
            label="Resultado pedagógico",
            detail=f"Autoevaluación dificultad: {feedback.difficulty_rating}/5",
            timestamp=feedback.created_at,
        )
    return TimelineStep(
        order=7,
        stage="result",
        label="Resultado pedagógico",
        detail="Sin autoevaluación registrada aún",
        timestamp=None,
    )


def build_recommendation_chain(db: Session, rec: Recommendation, student_name: str) -> RecommendationChain:
    steps = [
        _profile_step(db, rec),
        _rag_step(db, rec),
        _ai_step(rec),
        _teacher_step(db, rec),
        _student_step(db, rec),
        _consumption_step(db, rec),
        _result_step(db, rec),
    ]
    return RecommendationChain(
        recommendation_id=rec.id,
        student_id=rec.student_id,
        student_name=student_name,
        planning_topic=rec.planning_topic,
        status=rec.status,
        steps=steps,
    )


def get_course_timeline(
    db: Session,
    teacher: User,
    *,
    course_id: int,
    student_id: int | None = None,
    recommendation_id: int | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
) -> TimelineResponse:
    course = teacher_can_access_course(db, teacher, course_id)
    if not course:
        raise AuditServiceError("Curso no encontrado", 404)

    query = db.query(Recommendation, User).outerjoin(User, User.id == Recommendation.student_id).filter(
        Recommendation.course_id == course_id
    )
    if student_id is not None:
        query = query.filter(Recommendation.student_id == student_id)
    if recommendation_id is not None:
        query = query.filter(Recommendation.id == recommendation_id)
    if from_date is not None:
        query = query.filter(Recommendation.created_at >= from_date)
    if to_date is not None:
        query = query.filter(Recommendation.created_at <= to_date)

    rows = query.order_by(Recommendation.created_at.desc()).all()
    from app.services.recommendation_service import _display_student_name

    chains = [
        build_recommendation_chain(db, rec, _display_student_name(rec, student)) for rec, student in rows
    ]
    return TimelineResponse(
        course_id=course.id,
        summary=build_course_summary(db, course),
        chains=chains,
    )
