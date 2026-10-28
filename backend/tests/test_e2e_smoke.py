"""
Smoke E2E — flujo crítico Release 1 (Anexo H, S8).

Login → perfil → PDF → recomendación → MitL → estudiante → trazabilidad → CSV
"""

import io
import json
import os
import tempfile

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("UPLOAD_DIR", tempfile.mkdtemp(prefix="sapia_e2e_"))

import fitz
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.enums import RecommendationStatus, UserRole
from app.core.security import hash_password
from app.main import app
from app.models import (
    Course,
    CourseTeacher,
    DiagnosticItem,
    Enrollment,
    Organization,
    User,
)
from app.services.document_service import ingest_document
from ml.questions import DIAGNOSTIC_QUESTIONS
from tests.consent_helpers import AI_CONSENT, DIAG_CONSENT

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _pdf(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


@pytest.fixture()
def e2e_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        org = Organization(name="Colegio Piloto", registration_code="TEST-ORG")
        db.add(org)
        db.flush()
        teacher = User(
            org_id=org.id,
            email="docente@e2e.cl",
            password_hash=hash_password("e2epass123"),
            full_name="Docente E2E",
            role=UserRole.TEACHER.value,
        )
        student = User(
            org_id=org.id,
            email="estudiante@e2e.cl",
            password_hash=hash_password("e2epass123"),
            full_name="Estudiante E2E",
            role=UserRole.STUDENT.value,
        )
        db.add_all([teacher, student])
        db.flush()
        course = Course(org_id=org.id, name="8º Piloto", grade_level="8°")
        db.add(course)
        db.flush()
        db.add(CourseTeacher(course_id=course.id, teacher_id=teacher.id))
        db.add(Enrollment(course_id=course.id, student_id=student.id))
        for q in DIAGNOSTIC_QUESTIONS:
            db.add(
                DiagnosticItem(
                    sort_order=q["sort_order"],
                    question_text=q["question_text"],
                    options_json=json.dumps(q["options"]),
                    feature_key=q["feature_key"],
                )
            )
        db.commit()
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def e2e_client(e2e_db):
    def override_get_db():
        try:
            yield e2e_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _login(client: TestClient, email: str) -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "e2epass123"})
    assert r.status_code == 200
    return r.json()["access_token"]


def test_e2e_critical_flow_pt_st_001(e2e_client, e2e_db):
    """PT-ST-001: flujo completo MVP sin errores críticos."""
    client = e2e_client
    db = e2e_db

    teacher_h = {"Authorization": f"Bearer {_login(client, 'docente@e2e.cl')}"}
    student_h = {"Authorization": f"Bearer {_login(client, 'estudiante@e2e.cl')}"}
    assert client.get("/api/v1/auth/me", headers=teacher_h).json()["role"] == "teacher"

    assert client.get("/api/v1/recommendations/inbox", headers=student_h).status_code == 403

    items = client.get("/api/v1/diagnostic/items", headers=student_h).json()
    assert len(items) == 12
    answers = [
        {"item_id": i["id"], "answer_value": 1, "response_ms": 400, "skipped": False}
        for i in items
    ]
    profile = client.post("/api/v1/diagnostic/submit", headers=student_h, json={"answers": answers, **DIAG_CONSENT})
    assert profile.status_code == 201
    assert len(profile.json()["descriptors"]) >= 4

    course = db.query(Course).first()
    ingest_document(
        db,
        course_id=course.id,
        unit_name="Ciencias",
        filename="guia.pdf",
        content=_pdf("Sistema solar y apoyos visuales para estudiantes TEA en octavo básico."),
    )

    student = db.query(User).filter(User.email == "estudiante@e2e.cl").first()

    gen = client.post(
        "/api/v1/recommendations/generate",
        headers=teacher_h,
        json={
            "student_id": student.id,
            "course_id": course.id,
            "planning_topic": "Sistema solar unidad 2",
        **AI_CONSENT,
        },
    )
    assert gen.status_code == 201
    rec_id = gen.json()["id"]
    assert gen.json()["explanation"]

    accepted = client.post(
        f"/api/v1/recommendations/{rec_id}/validate",
        headers=teacher_h,
        json={"action": "accept"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == RecommendationStatus.ACCEPTED.value

    visible = client.get("/api/v1/student/recommendations", headers=student_h).json()
    assert any(r["id"] == rec_id for r in visible)

    client.get(f"/api/v1/student/recommendations/{rec_id}", headers=student_h)
    client.post(
        f"/api/v1/student/recommendations/{rec_id}/feedback",
        headers=student_h,
        json={"difficulty_rating": 4},
    )

    timeline = client.get(
        f"/api/v1/audit/timeline?course_id={course.id}&recommendation_id={rec_id}",
        headers=teacher_h,
    )
    assert len(timeline.json()["chains"][0]["steps"]) == 7

    csv_res = client.get(f"/api/v1/reports/course/{course.id}/csv", headers=teacher_h)
    assert csv_res.status_code == 200
    assert b"estudiante_nombre" in csv_res.content