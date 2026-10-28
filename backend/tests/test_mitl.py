import io
import json
import os
import tempfile

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("UPLOAD_DIR", tempfile.mkdtemp(prefix="sapia_mitl_test_"))

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
    AuditEvent,
    Course,
    CourseTeacher,
    DiagnosticSession,
    Enrollment,
    Organization,
    PedagogicalProfile,
    RecommendationValidation,
    User,
)
from app.services.document_service import ingest_document
from ml.questions import DESCRIPTOR_KEYS
from tests.consent_helpers import AI_CONSENT, DIAG_CONSENT

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def make_sample_pdf(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def seed_profile(db, student_id: int) -> None:
    session = DiagnosticSession(student_id=student_id)
    db.add(session)
    db.flush()
    descriptors = {k: 0.75 for k in DESCRIPTOR_KEYS}
    db.add(
        PedagogicalProfile(
            student_id=student_id,
            session_id=session.id,
            version=1,
            descriptors_json=json.dumps(descriptors),
            feature_importance_json=json.dumps({"comprension_lectora": 0.4}),
            model_version="rf_v1",
        )
    )


@pytest.fixture()
def db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        org = Organization(name="Test Org", registration_code="TEST-ORG")
        db.add(org)
        db.flush()
        teacher = User(
            org_id=org.id,
            email="docente@test.cl",
            password_hash=hash_password("testpass123"),
            full_name="Docente Test",
            role=UserRole.TEACHER.value,
        )
        student = User(
            org_id=org.id,
            email="estudiante@test.cl",
            password_hash=hash_password("testpass123"),
            full_name="Estudiante Test",
            role=UserRole.STUDENT.value,
        )
        db.add_all([teacher, student])
        db.flush()
        course = Course(org_id=org.id, name="8º A", grade_level="8°")
        db.add(course)
        db.flush()
        db.add(CourseTeacher(course_id=course.id, teacher_id=teacher.id))
        db.add(Enrollment(course_id=course.id, student_id=student.id))
        seed_profile(db, student.id)
        db.commit()
        ingest_document(
            db,
            course_id=course.id,
            unit_name="Lenguaje",
            filename="lenguaje.pdf",
            content=make_sample_pdf("Comprensión lectora con apoyos visuales para estudiantes TEA."),
        )
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _login(client: TestClient, email: str) -> str:
    res = client.post("/api/v1/auth/login", json={"email": email, "password": "testpass123"})
    assert res.status_code == 200
    return res.json()["access_token"]


def _create_pending(client: TestClient, db_session) -> int:
    token = _login(client, "docente@test.cl")
    course = db_session.query(Course).first()
    student = db_session.query(User).filter(User.role == UserRole.STUDENT.value).first()
    res = client.post(
        "/api/v1/recommendations/generate",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "student_id": student.id,
            "course_id": course.id,
            "planning_topic": "Comprensión lectora unidad 3",
        **AI_CONSENT,
        },
    )
    assert res.status_code == 201
    return res.json()["id"]


def test_pt_f_040_accept_makes_visible_to_student(client, db_session):
    """PT-F-040: aceptar → estado Aceptada; visible para el estudiante."""
    teacher_token = _login(client, "docente@test.cl")
    rec_id = _create_pending(client, db_session)

    accepted = client.post(
        f"/api/v1/recommendations/{rec_id}/validate",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={"action": "accept"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == RecommendationStatus.ACCEPTED.value

    student_token = _login(client, "estudiante@test.cl")
    visible = client.get(
        "/api/v1/student/recommendations",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert visible.status_code == 200
    ids = [r["id"] for r in visible.json()]
    assert rec_id in ids


def test_pt_f_041_reject_without_reason_fails(client, db_session):
    """PT-F-041: rechazar sin motivo → error de validación."""
    teacher_token = _login(client, "docente@test.cl")
    rec_id = _create_pending(client, db_session)

    res = client.post(
        f"/api/v1/recommendations/{rec_id}/validate",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={"action": "reject"},
    )
    assert res.status_code == 422


def test_pt_f_042_reject_with_reason_creates_audit(client, db_session):
    """PT-F-042: rechazar con motivo → registro de auditoría."""
    teacher_token = _login(client, "docente@test.cl")
    rec_id = _create_pending(client, db_session)

    res = client.post(
        f"/api/v1/recommendations/{rec_id}/validate",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={"action": "reject", "reason": "No se ajusta al nivel del curso"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == RecommendationStatus.REJECTED.value

    validation = (
        db_session.query(RecommendationValidation)
        .filter(RecommendationValidation.recommendation_id == rec_id)
        .first()
    )
    assert validation is not None
    assert validation.reason == "No se ajusta al nivel del curso"

    audit = (
        db_session.query(AuditEvent)
        .filter(AuditEvent.entity_id == str(rec_id), AuditEvent.action == "recommendation_reject")
        .first()
    )
    assert audit is not None


def test_edit_requires_reason_and_body(client, db_session):
    teacher_token = _login(client, "docente@test.cl")
    rec_id = _create_pending(client, db_session)

    res = client.post(
        f"/api/v1/recommendations/{rec_id}/validate",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={
            "action": "edit",
            "reason": "Simplificar instrucciones",
            "edited_body": "Actividad revisada por docente con pasos más cortos y apoyo visual.",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == RecommendationStatus.EDITED.value
    assert "revisada por docente" in body["body"]

    student_token = _login(client, "estudiante@test.cl")
    visible = client.get(
        "/api/v1/student/recommendations",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert rec_id in [r["id"] for r in visible.json()]