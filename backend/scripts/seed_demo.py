"""Seed organización demo, usuarios y banco de preguntas diagnóstico."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal
from app.core.enums import UserRole
from app.core.security import hash_password
from app.models import Course, CourseTeacher, DiagnosticItem, Organization, User
from ml.questions import DIAGNOSTIC_QUESTIONS

DEMO_PASSWORD = "Sapia2026!"
COORDINATOR_EMAIL = "pie@demo.sapia.cl"


def ensure_coordinator(db) -> None:
    org = db.query(Organization).first()
    if not org:
        return
    existing = db.query(User).filter(User.email == COORDINATOR_EMAIL).first()
    if existing:
        return
    coordinator = User(
        org_id=org.id,
        email=COORDINATOR_EMAIL,
        password_hash=hash_password(DEMO_PASSWORD),
        full_name="Coordinadora PIE Demo",
        role=UserRole.COORDINATOR.value,
    )
    db.add(coordinator)
    db.commit()
    print(f"  coordinador: {COORDINATOR_EMAIL} / {DEMO_PASSWORD}")


def seed_diagnostic_items(db) -> None:
    if db.query(DiagnosticItem).count() > 0:
        return
    for q in DIAGNOSTIC_QUESTIONS:
        db.add(
            DiagnosticItem(
                sort_order=q["sort_order"],
                question_text=q["question_text"],
                options_json=json.dumps(q["options"]),
                feature_key=q["feature_key"],
            )
        )
    print("Banco diagnóstico: 12 ítems cargados.")


def seed() -> None:
    db = SessionLocal()
    try:
        org = db.query(Organization).first()
        if not org:
            org = Organization(name="Colegio Demo SAPIA", registration_code="DEMO-SAPIA")
            db.add(org)
            db.flush()

            admin = User(
                org_id=org.id,
                email="admin@demo.sapia.cl",
                password_hash=hash_password(DEMO_PASSWORD),
                full_name="Administrador Demo",
                role=UserRole.ADMIN.value,
            )
            teacher = User(
                org_id=org.id,
                email="docente@demo.sapia.cl",
                password_hash=hash_password(DEMO_PASSWORD),
                full_name="Profesora Demo",
                role=UserRole.TEACHER.value,
            )
            db.add_all([admin, teacher])
            db.flush()

            course = Course(org_id=org.id, name="8° Básico A", grade_level="8°")
            db.add(course)
            db.flush()
            db.add(CourseTeacher(course_id=course.id, teacher_id=teacher.id))
            db.commit()
            print("Seed demo OK:")
            print(f"  admin:      admin@demo.sapia.cl / {DEMO_PASSWORD}")
            print(f"  docente:    docente@demo.sapia.cl / {DEMO_PASSWORD}")
            print(f"  coordinador:{COORDINATOR_EMAIL} / {DEMO_PASSWORD}")
        else:
            if not org.registration_code:
                org.registration_code = "DEMO-SAPIA"
                db.commit()
            print("Organización demo ya existe — omitiendo usuarios.")

        ensure_coordinator(db)
        seed_diagnostic_items(db)
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed()
