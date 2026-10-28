"""Estado demo y resúmenes para panel docente (demo tesis)."""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.enums import DocumentStatus, RecommendationStatus, UserRole
from app.models import (
    Course,
    CourseTeacher,
    CurricularDocument,
    DiagnosticAnswer,
    Enrollment,
    Recommendation,
    RecommendationFeedback,
    User,
)
from app.services.diagnostic_service import DESCRIPTOR_LABELS, get_latest_profile, profile_to_read, student_has_profile
from app.services.document_service import teacher_can_access_course
from ml.questions import DESCRIPTOR_KEYS


def student_attention_level(db: Session, student_id: int, has_profile: bool) -> str:
    counts = dict(
        db.query(Recommendation.status, func.count(Recommendation.id))
        .filter(Recommendation.student_id == student_id)
        .group_by(Recommendation.status)
        .all()
    )
    rejected = counts.get(RecommendationStatus.REJECTED.value, 0)
    pending = counts.get(RecommendationStatus.PENDING.value, 0)
    if not has_profile:
        return "no_profile"
    if rejected >= 3:
        return "alert"
    if pending > 0:
        return "pending"
    published = counts.get(RecommendationStatus.ACCEPTED.value, 0) + counts.get(
        RecommendationStatus.EDITED.value, 0
    )
    if published > 0:
        return "ok"
    return "monitor"


def _teacher_course_ids(db: Session, teacher: User) -> list[int]:
    rows = (
        db.query(CourseTeacher.course_id)
        .filter(CourseTeacher.teacher_id == teacher.id)
        .all()
    )
    return [r[0] for r in rows]


def get_teacher_setup_status(db: Session, teacher: User, course_id: int | None = None) -> dict:
    course_ids = _teacher_course_ids(db, teacher)
    if not course_ids:
        return {
            "course_id": None,
            "course_name": None,
            "has_indexed_documents": False,
            "indexed_documents_count": 0,
            "students_total": 0,
            "students_with_profile": 0,
            "students_needing_attention": 0,
            "recommendations_total": 0,
            "recommendations_pending": 0,
            "recommendations_published": 0,
            "has_generated_recommendation": False,
            "has_published_recommendation": False,
        }

    cid = course_id if course_id is not None else course_ids[0]
    if cid not in course_ids and not teacher_can_access_course(db, teacher, cid):
        cid = course_ids[0]

    course = db.query(Course).filter(Course.id == cid).first()
    doc_count = (
        db.query(CurricularDocument)
        .filter(
            CurricularDocument.course_id == cid,
            CurricularDocument.status == DocumentStatus.INDEXED.value,
        )
        .count()
    )
    enrolled_ids = [
        r[0]
        for r in db.query(Enrollment.student_id).filter(Enrollment.course_id == cid).all()
    ]
    students_total = len(enrolled_ids)
    with_profile = sum(1 for sid in enrolled_ids if student_has_profile(db, sid))
    needing_attention = sum(
        1
        for sid in enrolled_ids
        if student_attention_level(db, sid, student_has_profile(db, sid))
        in ("no_profile", "alert", "pending")
    )

    rec_q = db.query(Recommendation).filter(
        Recommendation.course_id == cid,
        Recommendation.teacher_id == teacher.id,
    )
    pending = rec_q.filter(Recommendation.status == RecommendationStatus.PENDING.value).count()
    published = rec_q.filter(
        Recommendation.status.in_(
            [RecommendationStatus.ACCEPTED.value, RecommendationStatus.EDITED.value]
        )
    ).count()
    total = rec_q.count()

    return {
        "course_id": cid,
        "course_name": course.name if course else None,
        "has_indexed_documents": doc_count > 0,
        "indexed_documents_count": doc_count,
        "students_total": students_total,
        "students_with_profile": with_profile,
        "students_needing_attention": needing_attention,
        "recommendations_total": total,
        "recommendations_pending": pending,
        "recommendations_published": published,
        "has_generated_recommendation": total > 0,
        "has_published_recommendation": published > 0,
    }


def _diagnostic_telemetry(db: Session, session_id: int) -> dict | None:
    answers = db.query(DiagnosticAnswer).filter(DiagnosticAnswer.session_id == session_id).all()
    if not answers:
        return None
    times = [a.response_ms for a in answers if a.response_ms is not None]
    skipped = sum(1 for a in answers if a.skipped)
    return {
        "items_answered": len(answers),
        "items_skipped": skipped,
        "avg_response_ms": int(sum(times) / len(times)) if times else None,
        "total_duration_ms": sum(times) if times else None,
    }


def get_student_teacher_summary(db: Session, teacher: User, student_id: int) -> dict:
    student = db.query(User).filter(
        User.id == student_id,
        User.org_id == teacher.org_id,
        User.role == UserRole.STUDENT.value,
    ).first()
    if not student:
        raise ValueError("Estudiante no encontrado")

    enrollments = (
        db.query(Course.name)
        .join(Enrollment, Enrollment.course_id == Course.id)
        .filter(Enrollment.student_id == student_id)
        .all()
    )
    course_names = [e[0] for e in enrollments]

    profile = get_latest_profile(db, student_id)
    top_descriptors: list[dict] = []
    model_version: str | None = None
    diagnostic_telemetry: dict | None = None
    if profile:
        data = profile_to_read(profile)
        model_version = profile.model_version
        diagnostic_telemetry = _diagnostic_telemetry(db, profile.session_id)
        ranked = sorted(data["descriptors"], key=lambda d: d.value, reverse=True)[:3]
        top_descriptors = [{"key": d.key, "label": d.label, "value": d.value} for d in ranked]

    latest = (
        db.query(Recommendation)
        .filter(Recommendation.student_id == student_id)
        .order_by(Recommendation.created_at.desc())
        .first()
    )
    latest_rec = None
    if latest:
        latest_rec = {
            "id": latest.id,
            "title": latest.title,
            "status": latest.status,
            "planning_topic": latest.planning_topic,
            "created_at": latest.created_at.isoformat(),
        }

    counts = dict(
        db.query(Recommendation.status, func.count(Recommendation.id))
        .filter(Recommendation.student_id == student_id)
        .group_by(Recommendation.status)
        .all()
    )

    return {
        "id": student.id,
        "full_name": student.full_name,
        "email": student.email,
        "age": (2026 - student.birth_year) if student.birth_year else None,
        "has_profile": profile is not None,
        "model_version": model_version,
        "diagnostic_telemetry": diagnostic_telemetry,
        "course_names": course_names,
        "top_descriptors": top_descriptors,
        "latest_recommendation": latest_rec,
        "recommendation_counts": {
            "pending": counts.get(RecommendationStatus.PENDING.value, 0),
            "published": counts.get(RecommendationStatus.ACCEPTED.value, 0)
            + counts.get(RecommendationStatus.EDITED.value, 0),
            "rejected": counts.get(RecommendationStatus.REJECTED.value, 0),
        },
    }


def get_course_analytics(db: Session, teacher: User, course_id: int) -> dict:
    if not teacher_can_access_course(db, teacher, course_id):
        raise ValueError("Curso no encontrado")

    recs = db.query(Recommendation).filter(Recommendation.course_id == course_id).all()
    status_breakdown = {
        RecommendationStatus.PENDING.value: 0,
        RecommendationStatus.ACCEPTED.value: 0,
        RecommendationStatus.EDITED.value: 0,
        RecommendationStatus.REJECTED.value: 0,
    }
    for r in recs:
        if r.status in status_breakdown:
            status_breakdown[r.status] += 1

    students = (
        db.query(User)
        .join(Enrollment, Enrollment.student_id == User.id)
        .filter(Enrollment.course_id == course_id, User.role == UserRole.STUDENT.value)
        .all()
    )
    descriptor_sums = {k: 0.0 for k in DESCRIPTOR_KEYS}
    descriptor_count = 0
    for s in students:
        profile = get_latest_profile(db, s.id)
        if not profile:
            continue
        data = profile_to_read(profile)
        for d in data["descriptors"]:
            key = d.key if hasattr(d, "key") else d["key"]
            val = d.value if hasattr(d, "value") else d["value"]
            if key in descriptor_sums:
                descriptor_sums[key] += float(val)
        descriptor_count += 1

    descriptor_averages = [
        {
            "key": k,
            "label": DESCRIPTOR_LABELS.get(k, k),
            "value": round(descriptor_sums[k] / descriptor_count, 3) if descriptor_count else 0,
        }
        for k in DESCRIPTOR_KEYS
    ]

    feedback_rows = (
        db.query(RecommendationFeedback)
        .join(Recommendation, Recommendation.id == RecommendationFeedback.recommendation_id)
        .filter(
            Recommendation.course_id == course_id,
            Recommendation.scope == "student",
        )
        .all()
    )
    difficulty_avg = None
    if feedback_rows:
        difficulty_avg = round(
            sum(r.difficulty_rating for r in feedback_rows) / len(feedback_rows), 2
        )

    return {
        "status_breakdown": status_breakdown,
        "descriptor_averages": descriptor_averages,
        "students_with_profile": descriptor_count,
        "students_total": len(students),
        "difficulty_feedback_count": len(feedback_rows),
        "difficulty_rating_avg": difficulty_avg,
    }
