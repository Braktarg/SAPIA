from dataclasses import dataclass

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import DocumentStatus, RecommendationScope, RecommendationStatus, UserRole, ValidationAction
from app.models import (
    Course,
    CurricularDocument,
    DocumentChunk,
    Enrollment,
    Recommendation,
    RecommendationFeedback,
    RecommendationValidation,
    User,
)
from app.schemas.auth import CONSENT_VERSION
from app.services.auth_service import log_audit
from app.services.diagnostic_service import get_latest_profile, profile_to_read
from app.services.document_service import teacher_can_access_course
from app.utils.student_content import simplify_explanation_for_student
from app.utils.teacher_content import sanitize_teacher_explanation
from rag.generate import (
    GeneratedRecommendation,
    StudentProfileSnapshot,
    generate_course_recommendation,
    generate_recommendation,
)
from rag.retrieve import retrieve_chunks, score_chunks_for_query

logger = logging.getLogger(__name__)


class RecommendationServiceError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass
class CourseGenerateResult:
    course_recommendation: Recommendation
    student_recommendations: list[Recommendation]
    retrieval_ms: int


def _student_in_course(db: Session, student_id: int, course_id: int) -> bool:
    return (
        db.query(Enrollment)
        .filter(Enrollment.student_id == student_id, Enrollment.course_id == course_id)
        .first()
        is not None
    )


def _course_has_indexed_docs(db: Session, course_id: int) -> bool:
    return (
        db.query(CurricularDocument)
        .filter(
            CurricularDocument.course_id == course_id,
            CurricularDocument.status == DocumentStatus.INDEXED.value,
        )
        .count()
        > 0
    )


def _students_with_profiles_in_course(db: Session, course_id: int, org_id: int) -> list[tuple[User, dict]]:
    rows = (
        db.query(User)
        .join(Enrollment, Enrollment.student_id == User.id)
        .filter(
            Enrollment.course_id == course_id,
            User.org_id == org_id,
            User.role == UserRole.STUDENT.value,
            User.is_active.is_(True),
        )
        .order_by(User.full_name)
        .all()
    )
    result: list[tuple[User, dict]] = []
    for student in rows:
        profile = get_latest_profile(db, student.id)
        if profile:
            result.append((student, profile_to_read(profile)))
    return result


def _enrich_context_json(context_json: str | None, generated: GeneratedRecommendation) -> str | None:
    if not context_json and not generated.evidence_chain:
        return context_json
    try:
        ctx = json.loads(context_json) if context_json else {}
    except json.JSONDecodeError:
        ctx = {}
    if generated.evidence_chain:
        ctx["evidence_chain"] = generated.evidence_chain
    return json.dumps(ctx, ensure_ascii=False)


def _persist_recommendation(
    db: Session,
    teacher: User,
    *,
    course_id: int,
    planning_topic: str,
    generated: GeneratedRecommendation,
    chunks,
    profile_version: int,
    scope: str,
    student_id: int | None,
    context_json: str | None,
) -> Recommendation:
    rec = Recommendation(
        student_id=student_id,
        course_id=course_id,
        teacher_id=teacher.id,
        scope=scope,
        status=RecommendationStatus.PENDING.value,
        planning_topic=planning_topic,
        title=generated.title,
        body=generated.body,
        explanation=generated.explanation,
        source_chunk_ids_json=_encode_source_chunks(chunks),
        profile_version=profile_version,
        context_json=_enrich_context_json(context_json, generated),
        degraded_mode=generated.degraded_mode,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def _generate_and_persist_student(
    db: Session,
    teacher: User,
    *,
    student: User,
    profile_data: dict,
    profile_version: int,
    course_id: int,
    planning_topic: str,
    chunks,
    batch_course_rec_id: int | None = None,
    grade_level: str | None = None,
) -> Recommendation:
    generated = generate_recommendation(
        planning_topic=planning_topic,
        descriptors=profile_data["descriptors"],
        chunks=chunks,
        student_name=student.full_name,
        grade_level=grade_level,
        student_id=student.id,
    )
    context_json = None
    if batch_course_rec_id is not None:
        context_json = json.dumps(
            {"batch_course_recommendation_id": batch_course_rec_id},
            ensure_ascii=False,
        )
    return _persist_recommendation(
        db,
        teacher,
        course_id=course_id,
        planning_topic=planning_topic,
        generated=generated,
        chunks=chunks,
        profile_version=profile_version,
        scope=RecommendationScope.STUDENT.value,
        student_id=student.id,
        context_json=context_json,
    )


def _llm_generate_for_student_row(
    *,
    planning_topic: str,
    profile_data: dict,
    chunks,
    student_name: str,
    grade_level: str | None,
) -> GeneratedRecommendation:
    """Solo inferencia LLM/plantilla (sin DB) — seguro para ejecutar en paralelo."""
    return generate_recommendation(
        planning_topic=planning_topic,
        descriptors=profile_data["descriptors"],
        chunks=chunks,
        student_name=student_name,
        grade_level=grade_level,
    )


def _require_ai_consent(*, accepted: bool, version: str) -> None:
    if not accepted:
        raise RecommendationServiceError(
            "Debe aceptar el consentimiento para procesamiento con IA (RNF-37)",
            400,
        )
    if version != CONSENT_VERSION:
        raise RecommendationServiceError("Versión de consentimiento desactualizada; recargue la página", 400)


def generate_for_student(
    db: Session,
    teacher: User,
    *,
    student_id: int,
    course_id: int,
    planning_topic: str,
    ai_consent_accepted: bool = False,
    consent_version: str = CONSENT_VERSION,
) -> tuple[Recommendation, int]:
    _require_ai_consent(accepted=ai_consent_accepted, version=consent_version)
    if not teacher_can_access_course(db, teacher, course_id):
        raise RecommendationServiceError("Curso no encontrado o sin permiso", 404)

    student = db.query(User).filter(
        User.id == student_id,
        User.org_id == teacher.org_id,
        User.role == UserRole.STUDENT.value,
    ).first()
    if not student:
        raise RecommendationServiceError("Estudiante no encontrado", 404)

    if not _student_in_course(db, student_id, course_id):
        raise RecommendationServiceError("El estudiante no está inscrito en el curso", 400)

    profile = get_latest_profile(db, student_id)
    if not profile:
        raise RecommendationServiceError("El estudiante no tiene perfil pedagógico", 400)

    if not _course_has_indexed_docs(db, course_id):
        raise RecommendationServiceError("No hay documentos curriculares indexados en el curso", 400)

    course = db.query(Course).filter(Course.id == course_id).first()
    grade_level = course.grade_level if course else None

    topic = planning_topic.strip()
    if len(topic) < 3:
        raise RecommendationServiceError("El tema de planificación es obligatorio", 400)

    started = time.perf_counter()
    chunks = retrieve_chunks(db, course_id, topic)
    if not chunks:
        raise RecommendationServiceError("No se encontraron fragmentos curriculares relevantes", 422)

    profile_data = profile_to_read(profile)
    rec = _generate_and_persist_student(
        db,
        teacher,
        student=student,
        profile_data=profile_data,
        profile_version=profile.version,
        course_id=course_id,
        planning_topic=topic,
        chunks=chunks,
        grade_level=grade_level,
    )
    retrieval_ms = int((time.perf_counter() - started) * 1000)

    log_audit(
        db,
        org_id=teacher.org_id,
        actor_id=teacher.id,
        entity_type="recommendation",
        entity_id=str(rec.id),
        action="recommendation_generated",
        payload={
            "student_id": student_id,
            "course_id": course_id,
            "chunk_ids": [c.id for c in chunks],
            "degraded_mode": rec.degraded_mode,
            "retrieval_ms": retrieval_ms,
        },
    )
    return rec, retrieval_ms


def generate_for_course(
    db: Session,
    teacher: User,
    *,
    course_id: int,
    planning_topic: str,
    include_per_student: bool = True,
    ai_consent_accepted: bool = False,
    consent_version: str = CONSENT_VERSION,
) -> CourseGenerateResult:
    _require_ai_consent(accepted=ai_consent_accepted, version=consent_version)
    if not teacher_can_access_course(db, teacher, course_id):
        raise RecommendationServiceError("Curso no encontrado o sin permiso", 404)

    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise RecommendationServiceError("Curso no encontrado", 404)

    if not _course_has_indexed_docs(db, course_id):
        raise RecommendationServiceError("No hay documentos curriculares indexados en el curso", 400)

    topic = planning_topic.strip()
    if len(topic) < 3:
        raise RecommendationServiceError("El tema de planificación es obligatorio", 400)

    profile_rows = _students_with_profiles_in_course(db, course_id, teacher.org_id)
    if not profile_rows:
        raise RecommendationServiceError(
            "No hay estudiantes matriculados con perfil pedagógico en este curso", 400
        )

    started = time.perf_counter()
    chunks = retrieve_chunks(db, course_id, topic)
    if not chunks:
        raise RecommendationServiceError("No se encontraron fragmentos curriculares relevantes", 422)

    snapshots = [
        StudentProfileSnapshot(
            student_id=student.id,
            student_name=student.full_name,
            descriptors=profile_data["descriptors"],
            profile_version=profile_data["version"],
        )
        for student, profile_data in profile_rows
    ]
    generated = generate_course_recommendation(
        planning_topic=topic,
        course_name=course.name,
        student_profiles=snapshots,
        chunks=chunks,
        grade_level=course.grade_level,
    )
    retrieval_ms = int((time.perf_counter() - started) * 1000)

    context_payload = {
        "scope": RecommendationScope.COURSE.value,
        "course_name": course.name,
        "student_count": len(snapshots),
        "students": [
            {
                "student_id": s.student_id,
                "student_name": s.student_name,
                "profile_version": s.profile_version,
            }
            for s in snapshots
        ],
    }
    max_version = max(s.profile_version for s in snapshots)

    rec = _persist_recommendation(
        db,
        teacher,
        course_id=course_id,
        planning_topic=topic,
        generated=generated,
        chunks=chunks,
        profile_version=max_version,
        scope=RecommendationScope.COURSE.value,
        student_id=None,
        context_json=json.dumps(context_payload, ensure_ascii=False),
    )

    log_audit(
        db,
        org_id=teacher.org_id,
        actor_id=teacher.id,
        entity_type="recommendation",
        entity_id=str(rec.id),
        action="recommendation_generated_course",
        payload={
            "course_id": course_id,
            "student_count": len(snapshots),
            "chunk_ids": [c.id for c in chunks],
            "degraded_mode": generated.degraded_mode,
            "retrieval_ms": retrieval_ms,
            "include_per_student": include_per_student,
        },
    )

    student_recs: list[Recommendation] = []
    if include_per_student:
        workers = min(settings.batch_llm_workers, len(profile_rows))
        logger.info(
            "batch_generate students=%s workers=%s topic=%s",
            len(profile_rows),
            workers,
            topic,
        )
        generated_rows: list[tuple[User, dict, GeneratedRecommendation]] = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(
                    _llm_generate_for_student_row,
                    planning_topic=topic,
                    profile_data=profile_data,
                    chunks=chunks,
                    student_name=student.full_name,
                    grade_level=course.grade_level,
                ): (student, profile_data)
                for student, profile_data in profile_rows
            }
            for future in as_completed(futures):
                student, profile_data = futures[future]
                generated_rows.append((student, profile_data, future.result()))

        for student, profile_data, generated in generated_rows:
            context_json = json.dumps(
                {"batch_course_recommendation_id": rec.id},
                ensure_ascii=False,
            )
            student_rec = _persist_recommendation(
                db,
                teacher,
                course_id=course_id,
                planning_topic=topic,
                generated=generated,
                chunks=chunks,
                profile_version=profile_data["version"],
                scope=RecommendationScope.STUDENT.value,
                student_id=student.id,
                context_json=context_json,
            )
            student_recs.append(student_rec)
            log_audit(
                db,
                org_id=teacher.org_id,
                actor_id=teacher.id,
                entity_type="recommendation",
                entity_id=str(student_rec.id),
                action="recommendation_generated_batch",
                payload={
                    "student_id": student.id,
                    "course_id": course_id,
                    "batch_course_recommendation_id": rec.id,
                    "degraded_mode": student_rec.degraded_mode,
                },
            )

    if include_per_student and student_recs:
        log_audit(
            db,
            org_id=teacher.org_id,
            actor_id=teacher.id,
            entity_type="recommendation",
            entity_id=str(rec.id),
            action="recommendation_batch_completed",
            payload={
                "course_id": course_id,
                "course_recommendation_id": rec.id,
                "student_recommendation_ids": [r.id for r in student_recs],
                "student_count": len(student_recs),
            },
        )

    return CourseGenerateResult(
        course_recommendation=rec,
        student_recommendations=student_recs,
        retrieval_ms=retrieval_ms,
    )


def list_inbox(
    db: Session,
    teacher: User,
    *,
    course_id: int | None = None,
    status: str | None = RecommendationStatus.PENDING.value,
) -> list[dict]:
    query = (
        db.query(Recommendation, User)
        .outerjoin(User, User.id == Recommendation.student_id)
        .filter(Recommendation.teacher_id == teacher.id)
    )
    if course_id is not None:
        if not teacher_can_access_course(db, teacher, course_id):
            raise RecommendationServiceError("Curso no encontrado", 404)
        query = query.filter(Recommendation.course_id == course_id)
    if status and status != "all":
        if status == "published":
            query = query.filter(
                Recommendation.status.in_(
                    [RecommendationStatus.ACCEPTED.value, RecommendationStatus.EDITED.value]
                )
            )
        else:
            query = query.filter(Recommendation.status == status)
    rows = query.order_by(Recommendation.created_at.desc()).all()
    return [recommendation_to_summary(rec, student) for rec, student in rows]


def recommendation_to_summary(rec: Recommendation, student: User | None) -> dict:
    return {
        "id": rec.id,
        "student_id": rec.student_id,
        "student_name": _display_student_name(rec, student),
        "course_id": rec.course_id,
        "scope": rec.scope,
        "status": rec.status,
        "planning_topic": rec.planning_topic,
        "title": rec.title,
        "created_at": rec.created_at,
    }


def _display_student_name(rec: Recommendation, student: User | None) -> str:
    if rec.scope == RecommendationScope.COURSE.value or student is None:
        try:
            ctx = json.loads(rec.context_json or "{}")
            count = ctx.get("student_count")
            if count:
                return f"Curso completo ({count} perfiles)"
        except json.JSONDecodeError:
            pass
        return "Curso completo"
    return student.full_name


def get_recommendation_detail(db: Session, teacher: User, recommendation_id: int) -> dict:
    rec = db.query(Recommendation).filter(Recommendation.id == recommendation_id).first()
    if not rec:
        raise RecommendationServiceError("Recomendación no encontrada", 404)
    if not teacher_can_access_course(db, teacher, rec.course_id):
        raise RecommendationServiceError("Sin permiso", 403)
    if rec.teacher_id != teacher.id and teacher.role not in (
        UserRole.ADMIN.value,
        UserRole.COORDINATOR.value,
    ):
        raise RecommendationServiceError("Sin permiso", 403)

    student = db.query(User).filter(User.id == rec.student_id).first() if rec.student_id else None
    display_name = _display_student_name(rec, student)
    source_chunks = _resolve_source_chunks(
        db, rec.course_id, rec.source_chunk_ids_json, rec.planning_topic
    )
    return recommendation_to_read(rec, display_name, source_chunks, db)


def _encode_source_chunks(chunks) -> str:
    return json.dumps([{"id": c.id, "score": round(float(c.score), 4)} for c in chunks])


def _parse_source_chunk_refs(raw: str) -> list[tuple[int, float | None]]:
    data = json.loads(raw or "[]")
    refs: list[tuple[int, float | None]] = []
    for item in data:
        if isinstance(item, dict):
            score = item.get("score")
            refs.append((int(item["id"]), float(score) if score is not None else None))
        else:
            refs.append((int(item), None))
    return refs


def _chunk_ids_from_raw(raw: str) -> list[int]:
    return [cid for cid, _ in _parse_source_chunk_refs(raw)]


def _snippet_from_content(content: str, max_len: int = 220) -> str:
    text = content.strip()
    if len(text) <= max_len:
        return text
    cut = text[:max_len]
    if " " in cut[40:]:
        cut = cut[: cut.rfind(" ", 40, max_len)]
    return cut.rstrip() + "…"


def _display_citation_score(raw: float, raw_scores: list[float]) -> float:
    """Convierte similitud coseno a % útil en UI (embeddings locales pueden ser < 0)."""
    if not raw_scores:
        return 0.0
    lo, hi = min(raw_scores), max(raw_scores)
    if lo >= 0:
        return round(max(0.0, min(1.0, float(raw))), 4)
    if hi - lo < 1e-9:
        return 0.85
    normalized = (float(raw) - lo) / (hi - lo)
    return round(0.5 + 0.5 * normalized, 4)


def _resolve_source_chunks(
    db: Session,
    course_id: int,
    raw_json: str,
    planning_topic: str | None = None,
) -> list[dict]:
    refs = _parse_source_chunk_refs(raw_json)
    if not refs:
        return []

    chunk_ids = [cid for cid, _ in refs]
    missing_scores = [cid for cid, sc in refs if sc is None]
    computed: dict[int, float] = {}
    if missing_scores and planning_topic:
        computed = score_chunks_for_query(db, course_id, planning_topic, missing_scores)

    rows = (
        db.query(DocumentChunk, CurricularDocument)
        .join(CurricularDocument, CurricularDocument.id == DocumentChunk.document_id)
        .filter(DocumentChunk.id.in_(chunk_ids))
        .all()
    )
    by_id = {
        dc.id: {
            "id": dc.id,
            "unit_name": doc.unit_name,
            "snippet": _snippet_from_content(dc.content),
            "score": 0.0,
        }
        for dc, doc in rows
    }
    raw_scores: list[float] = []
    pending: list[tuple[dict, float]] = []
    for cid, stored_score in refs:
        if cid not in by_id:
            continue
        raw = stored_score if stored_score is not None else computed.get(cid, 0.0)
        raw_scores.append(float(raw))
        pending.append((dict(by_id[cid]), float(raw)))

    result: list[dict] = []
    for entry, raw in pending:
        entry["score"] = _display_citation_score(raw, raw_scores)
        result.append(entry)
    return result


def _mitl_info(db: Session, rec: Recommendation) -> dict | None:
    validation = (
        db.query(RecommendationValidation)
        .filter(RecommendationValidation.recommendation_id == rec.id)
        .order_by(RecommendationValidation.created_at.desc())
        .first()
    )
    if not validation:
        return None
    return {
        "action": validation.action,
        "reason": validation.reason,
        "original_body": validation.original_body,
        "validated_at": validation.created_at.isoformat() if validation.created_at else None,
    }


def recommendation_to_read(rec: Recommendation, student_name: str, source_chunks: list[dict], db: Session | None = None) -> dict:
    mitl = _mitl_info(db, rec) if db else None
    course_context = None
    evidence_chain = None
    if rec.context_json:
        try:
            ctx = json.loads(rec.context_json)
            evidence_chain = ctx.get("evidence_chain")
            if rec.scope == RecommendationScope.COURSE.value:
                course_context = {k: v for k, v in ctx.items() if k != "evidence_chain"}
        except json.JSONDecodeError:
            course_context = None

    if evidence_chain and mitl:
        evidence_chain = json.loads(json.dumps(evidence_chain))
        for step in evidence_chain.get("steps", []):
            if step.get("stage") == "mitl":
                action = mitl.get("action", "pendiente")
                reason = mitl.get("reason")
                step["detail"] = (
                    f"Docente: {action}"
                    + (f" — {reason}" if reason else "")
                )
                break

    return {
        "id": rec.id,
        "student_id": rec.student_id,
        "student_name": student_name,
        "course_id": rec.course_id,
        "scope": rec.scope,
        "course_context": course_context if rec.scope == RecommendationScope.COURSE.value else None,
        "evidence_chain": evidence_chain,
        "teacher_id": rec.teacher_id,
        "status": rec.status,
        "planning_topic": rec.planning_topic,
        "title": rec.title,
        "body": rec.body,
        "explanation": sanitize_teacher_explanation(
            rec.explanation, has_evidence_chain=bool(evidence_chain)
        ),
        "source_chunks": source_chunks,
        "profile_version": rec.profile_version,
        "degraded_mode": rec.degraded_mode,
        "created_at": rec.created_at,
        "mitl": mitl,
    }


def _ensure_teacher_owns_recommendation(teacher: User, rec: Recommendation) -> None:
    if rec.teacher_id != teacher.id and teacher.role not in (
        UserRole.ADMIN.value,
        UserRole.COORDINATOR.value,
    ):
        raise RecommendationServiceError("Sin permiso para validar esta recomendación", 403)


def validate_recommendation(
    db: Session,
    teacher: User,
    recommendation_id: int,
    *,
    action: str,
    reason: str | None = None,
    edited_body: str | None = None,
) -> Recommendation:
    rec = db.query(Recommendation).filter(Recommendation.id == recommendation_id).first()
    if not rec:
        raise RecommendationServiceError("Recomendación no encontrada", 404)
    if not teacher_can_access_course(db, teacher, rec.course_id):
        raise RecommendationServiceError("Sin permiso", 403)
    _ensure_teacher_owns_recommendation(teacher, rec)

    if rec.status != RecommendationStatus.PENDING.value:
        raise RecommendationServiceError("Solo se pueden validar recomendaciones pendientes", 409)

    try:
        validation_action = ValidationAction(action)
    except ValueError as exc:
        raise RecommendationServiceError("Acción inválida", 400) from exc

    reason_text = (reason or "").strip()
    edited_text = (edited_body or "").strip()
    original_ia_body: str | None = None

    if validation_action == ValidationAction.ACCEPT:
        rec.status = RecommendationStatus.ACCEPTED.value
    elif validation_action == ValidationAction.REJECT:
        if len(reason_text) < 3:
            raise RecommendationServiceError("El motivo es obligatorio al rechazar", 422)
        rec.status = RecommendationStatus.REJECTED.value
    elif validation_action == ValidationAction.EDIT:
        if len(reason_text) < 3:
            raise RecommendationServiceError("El motivo es obligatorio al editar", 422)
        if len(edited_text) < 10:
            raise RecommendationServiceError("El contenido editado es obligatorio", 422)
        original_ia_body = rec.body
        rec.status = RecommendationStatus.EDITED.value
        rec.body = edited_text

    validation = RecommendationValidation(
        recommendation_id=rec.id,
        teacher_id=teacher.id,
        action=validation_action.value,
        reason=reason_text or None,
        original_body=original_ia_body,
        edited_body=edited_text or None,
    )
    db.add(validation)
    db.commit()
    db.refresh(rec)

    log_audit(
        db,
        org_id=teacher.org_id,
        actor_id=teacher.id,
        entity_type="recommendation",
        entity_id=str(rec.id),
        action=f"recommendation_{validation_action.value}",
        payload={
            "reason": reason_text or None,
            "new_status": rec.status,
            "validation_id": validation.id,
        },
    )
    return rec


def list_student_visible_recommendations(db: Session, student: User) -> list[dict]:
    if student.role_enum != UserRole.STUDENT:
        raise RecommendationServiceError("Solo estudiantes", 403)

    rows = _student_visible_query(db, student.id).all()
    return [_student_recommendation_to_dict(db, rec, student.id) for rec in rows]


def get_student_recommendation(db: Session, student: User, recommendation_id: int) -> dict:
    rec = (
        _student_visible_query(db, student.id)
        .filter(Recommendation.id == recommendation_id)
        .first()
    )
    if not rec:
        raise RecommendationServiceError("Recomendación no encontrada", 404)
    log_audit(
        db,
        org_id=student.org_id,
        actor_id=student.id,
        entity_type="recommendation",
        entity_id=str(rec.id),
        action="student_recommendation_view",
        payload={"recommendation_id": rec.id},
    )
    return _student_recommendation_to_dict(db, rec, student.id)


def student_can_download_document(db: Session, student: User, document_id: int) -> CurricularDocument:
    if student.role_enum != UserRole.STUDENT:
        raise RecommendationServiceError("Solo estudiantes", 403)

    doc = (
        db.query(CurricularDocument)
        .filter(
            CurricularDocument.id == document_id,
            CurricularDocument.status == DocumentStatus.INDEXED.value,
        )
        .first()
    )
    if not doc:
        raise RecommendationServiceError("Documento no encontrado", 404)

    approved = _student_visible_query(db, student.id).all()
    allowed_doc_ids: set[int] = set()
    for rec in approved:
        for resource in _resources_for_recommendation(db, rec):
            allowed_doc_ids.add(resource["document_id"])

    if document_id not in allowed_doc_ids:
        raise RecommendationServiceError("Sin acceso a este recurso", 403)

    path = Path(doc.storage_path)
    if not path.is_file():
        raise RecommendationServiceError("Archivo no disponible", 404)
    return doc


def _student_visible_query(db: Session, student_id: int):
    return (
        db.query(Recommendation)
        .filter(
            Recommendation.student_id == student_id,
            Recommendation.scope == RecommendationScope.STUDENT.value,
            Recommendation.status.in_(
                [RecommendationStatus.ACCEPTED.value, RecommendationStatus.EDITED.value]
            ),
        )
        .order_by(Recommendation.created_at.desc())
    )


def _published_at(db: Session, recommendation_id: int) -> datetime | None:
    validation = (
        db.query(RecommendationValidation)
        .filter(
            RecommendationValidation.recommendation_id == recommendation_id,
            RecommendationValidation.action.in_(
                [ValidationAction.ACCEPT.value, ValidationAction.EDIT.value]
            ),
        )
        .order_by(RecommendationValidation.created_at.desc())
        .first()
    )
    return validation.created_at if validation else None


def _resources_for_recommendation(db: Session, rec: Recommendation) -> list[dict]:
    chunk_ids = _chunk_ids_from_raw(rec.source_chunk_ids_json or "[]")
    if not chunk_ids:
        return []
    rows = (
        db.query(DocumentChunk, CurricularDocument)
        .join(CurricularDocument, CurricularDocument.id == DocumentChunk.document_id)
        .filter(DocumentChunk.id.in_(chunk_ids))
        .all()
    )
    seen: set[int] = set()
    resources: list[dict] = []
    for _chunk, doc in rows:
        if doc.id in seen:
            continue
        seen.add(doc.id)
        resources.append(
            {
                "document_id": doc.id,
                "unit_name": doc.unit_name,
                "filename": doc.original_filename,
            }
        )
    return resources


def _feedback_for_student(db: Session, recommendation_id: int, student_id: int) -> RecommendationFeedback | None:
    return (
        db.query(RecommendationFeedback)
        .filter(
            RecommendationFeedback.recommendation_id == recommendation_id,
            RecommendationFeedback.student_id == student_id,
        )
        .first()
    )


def submit_student_feedback(
    db: Session,
    student: User,
    recommendation_id: int,
    *,
    difficulty_rating: int,
) -> dict:
    if student.role_enum != UserRole.STUDENT:
        raise RecommendationServiceError("Solo estudiantes", 403)
    if difficulty_rating < 1 or difficulty_rating > 5:
        raise RecommendationServiceError("La dificultad debe estar entre 1 y 5", 422)

    rec = (
        _student_visible_query(db, student.id)
        .filter(Recommendation.id == recommendation_id)
        .first()
    )
    if not rec:
        raise RecommendationServiceError("Recomendación no encontrada", 404)

    existing = _feedback_for_student(db, recommendation_id, student.id)
    if existing:
        existing.difficulty_rating = difficulty_rating
        db.commit()
        db.refresh(existing)
        row = existing
    else:
        row = RecommendationFeedback(
            recommendation_id=recommendation_id,
            student_id=student.id,
            difficulty_rating=difficulty_rating,
        )
        db.add(row)
        db.commit()
        db.refresh(row)

    log_audit(
        db,
        org_id=student.org_id,
        actor_id=student.id,
        entity_type="recommendation_feedback",
        entity_id=str(row.id),
        action="difficulty_rating_submitted",
        payload={
            "recommendation_id": recommendation_id,
            "difficulty_rating": difficulty_rating,
        },
    )
    return {"difficulty_rating": row.difficulty_rating, "submitted_at": row.created_at}


def _student_recommendation_to_dict(db: Session, rec: Recommendation, student_id: int) -> dict:
    teacher = db.query(User).filter(User.id == rec.teacher_id).first()
    feedback = _feedback_for_student(db, rec.id, student_id)
    return {
        "id": rec.id,
        "title": rec.title,
        "body": rec.body,
        "planning_topic": rec.planning_topic,
        "status": rec.status,
        "explanation": rec.explanation,
        "explanation_student": simplify_explanation_for_student(rec.explanation),
        "teacher_name": teacher.full_name if teacher else "Docente",
        "published_at": _published_at(db, rec.id),
        "resources": _resources_for_recommendation(db, rec),
        "created_at": rec.created_at,
        "my_difficulty_rating": feedback.difficulty_rating if feedback else None,
    }
