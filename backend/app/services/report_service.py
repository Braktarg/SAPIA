import csv
import io
from datetime import datetime

from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.core.enums import RecommendationStatus, UserRole
from app.core.security import hash_password
from app.models import Enrollment, Recommendation, User
from app.services.audit_service import AuditServiceError, _course_students
from app.services.auth_service import log_audit
from app.services.diagnostic_service import get_latest_profile, student_has_profile
from app.services.document_service import teacher_can_access_course

DEFAULT_IMPORT_PASSWORD = "SapiaCambiar2026!"


def _course_report_rows(db: Session, course_id: int, students: list[User], *, anonymize: bool) -> list[list]:
    rows: list[list] = []
    for idx, student in enumerate(students, start=1):
        recs = db.query(Recommendation).filter(Recommendation.student_id == student.id).all()
        profile = get_latest_profile(db, student.id)
        name = f"Estudiante_{idx}" if anonymize else student.full_name
        email = f"estudiante{idx}@anon.local" if anonymize else student.email
        last = max((r.created_at for r in recs), default=None)
        rows.append(
            [
                student.id if not anonymize else idx,
                name,
                email,
                "si" if student_has_profile(db, student.id) else "no",
                profile.version if profile else "",
                len(recs),
                sum(1 for r in recs if r.status == RecommendationStatus.PENDING.value),
                sum(1 for r in recs if r.status == RecommendationStatus.ACCEPTED.value),
                sum(1 for r in recs if r.status == RecommendationStatus.EDITED.value),
                sum(1 for r in recs if r.status == RecommendationStatus.REJECTED.value),
                last.isoformat() if last else "",
            ]
        )
    return rows


_REPORT_HEADERS = [
    "estudiante_id",
    "estudiante_nombre",
    "email",
    "tiene_perfil",
    "version_perfil",
    "recomendaciones_total",
    "pendientes",
    "aceptadas",
    "editadas",
    "rechazadas",
    "ultima_recomendacion",
]


def export_course_csv(
    db: Session,
    teacher: User,
    course_id: int,
    *,
    anonymize: bool = False,
) -> tuple[str, str]:
    course = teacher_can_access_course(db, teacher, course_id)
    if not course:
        raise AuditServiceError("Curso no encontrado", 404)

    students = _course_students(db, course.id)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(_REPORT_HEADERS)
    for row in _course_report_rows(db, course.id, students, anonymize=anonymize):
        writer.writerow(row)

    filename = f"sapia_curso_{course.id}_{datetime.now().strftime('%Y%m%d')}.csv"
    return output.getvalue(), filename


def export_course_xlsx(
    db: Session,
    teacher: User,
    course_id: int,
    *,
    anonymize: bool = False,
) -> tuple[bytes, str]:
    course = teacher_can_access_course(db, teacher, course_id)
    if not course:
        raise AuditServiceError("Curso no encontrado", 404)

    students = _course_students(db, course.id)
    wb = Workbook()
    ws = wb.active
    ws.title = "Curso"
    ws.append(_REPORT_HEADERS)
    for row in _course_report_rows(db, course.id, students, anonymize=anonymize):
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    filename = f"sapia_curso_{course.id}_{datetime.now().strftime('%Y%m%d')}.xlsx"
    return buf.getvalue(), filename


def import_course_students_csv(
    db: Session,
    teacher: User,
    course_id: int,
    content: str,
) -> dict[str, int]:
    course = teacher_can_access_course(db, teacher, course_id)
    if not course:
        raise AuditServiceError("Curso no encontrado", 404)

    reader = csv.DictReader(io.StringIO(content))
    required = {"full_name", "email"}
    if not reader.fieldnames or not required.issubset({h.strip() for h in reader.fieldnames}):
        raise AuditServiceError("CSV debe incluir columnas: full_name, email (birth_year opcional)", 400)

    created = 0
    enrolled = 0
    skipped = 0

    for row in reader:
        full_name = (row.get("full_name") or "").strip()
        email = (row.get("email") or "").strip().lower()
        if not full_name or not email:
            skipped += 1
            continue
        birth_raw = (row.get("birth_year") or "").strip()
        birth_year = int(birth_raw) if birth_raw.isdigit() else None

        student = db.query(User).filter(User.email == email).first()
        if student:
            if student.org_id != teacher.org_id or student.role != UserRole.STUDENT.value:
                skipped += 1
                continue
        else:
            student = User(
                org_id=teacher.org_id,
                email=email,
                password_hash=hash_password(DEFAULT_IMPORT_PASSWORD),
                full_name=full_name,
                birth_year=birth_year,
                role=UserRole.STUDENT.value,
                is_active=True,
            )
            db.add(student)
            db.flush()
            created += 1

        exists = (
            db.query(Enrollment)
            .filter(Enrollment.course_id == course_id, Enrollment.student_id == student.id)
            .first()
        )
        if exists:
            skipped += 1
            continue
        db.add(Enrollment(course_id=course_id, student_id=student.id))
        enrolled += 1

    db.commit()
    log_audit(
        db,
        org_id=teacher.org_id,
        actor_id=teacher.id,
        entity_type="course",
        entity_id=str(course_id),
        action="import_students_csv",
        payload={"created": created, "enrolled": enrolled, "skipped": skipped},
    )
    return {"created": created, "enrolled": enrolled, "skipped": skipped}
