import io
import json
import os
import tempfile

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("UPLOAD_DIR", tempfile.mkdtemp(prefix="sapia_rec_test_"))

import fitz
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.enums import DocumentStatus, RecommendationStatus, UserRole
from app.core.security import hash_password
from app.main import app
from app.models import (
    Course,
    CourseTeacher,
    DiagnosticSession,
    Enrollment,
    Organization,
    PedagogicalProfile,
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

        pdf = make_sample_pdf(
            "Unidad de lenguaje: comprensión lectora con apoyos visuales y secuencias cortas para estudiantes TEA."
        )
        ingest_document(
            db,
            course_id=course.id,
            unit_name="Lenguaje",
            filename="lenguaje.pdf",
            content=pdf,
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


def _login(client: TestClient) -> str:
    res = client.post("/api/v1/auth/login", json={"email": "docente@test.cl", "password": "testpass123"})
    assert res.status_code == 200
    return res.json()["access_token"]


def test_pt_f_030_generates_pending_recommendation(client, db_session):
    """PT-F-030: docente dispara motor → ítem en bandeja Pendiente."""
    token = _login(client)
    course = db_session.query(Course).first()
    student = db_session.query(User).filter(User.role == UserRole.STUDENT.value).first()
    headers = {"Authorization": f"Bearer {token}"}

    res = client.post(
        "/api/v1/recommendations/generate",
        headers=headers,
        json={
            "student_id": student.id,
            "course_id": course.id,
            "planning_topic": "Comprensión lectora unidad 3",
        **AI_CONSENT,
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["status"] == RecommendationStatus.PENDING.value
    assert body["title"]
    assert body["body"]

    inbox = client.get("/api/v1/recommendations/inbox", headers=headers)
    assert inbox.status_code == 200
    items = inbox.json()
    assert any(i["id"] == body["id"] and i["status"] == "pending" for i in items)


def test_pt_f_031_explanation_visible(client, db_session):
    """PT-F-031: abrir recomendación → texto explicativo no vacío."""
    token = _login(client)
    course = db_session.query(Course).first()
    student = db_session.query(User).filter(User.role == UserRole.STUDENT.value).first()
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post(
        "/api/v1/recommendations/generate",
        headers=headers,
        json={
            "student_id": student.id,
            "course_id": course.id,
            "planning_topic": "Fracciones y representación visual",
        **AI_CONSENT,
        },
    )
    rec_id = created.json()["id"]

    detail = client.get(f"/api/v1/recommendations/{rec_id}", headers=headers)
    assert detail.status_code == 200
    data = detail.json()
    assert data["explanation"]
    assert len(data["explanation"].strip()) > 20
    assert "Por qué" in data["explanation"] or "perfil" in data["explanation"].lower()
    assert len(data["source_chunks"]) > 0
    assert all(c["score"] > 0 for c in data["source_chunks"])


def test_retrieve_returns_chunks_for_course(db_session):
    from rag.retrieve import retrieve_chunks

    course = db_session.query(Course).first()
    chunks = retrieve_chunks(db_session, course.id, "comprensión lectora apoyos visuales")
    assert len(chunks) > 0


def test_generate_without_profile_fails(client, db_session):
    token = _login(client)
    course = db_session.query(Course).first()
    extra = User(
        org_id=course.org_id,
        email="sinperfil@test.cl",
        password_hash=hash_password("testpass123"),
        full_name="Sin Perfil",
        role=UserRole.STUDENT.value,
    )
    db_session.add(extra)
    db_session.flush()
    db_session.add(Enrollment(course_id=course.id, student_id=extra.id))
    db_session.commit()

    res = client.post(
        "/api/v1/recommendations/generate",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "student_id": extra.id,
            "course_id": course.id,
            "planning_topic": "Tema cualquiera",
        **AI_CONSENT,
        },
    )
    assert res.status_code == 400


def test_generate_course_recommendation(client, db_session):
    token = _login(client)
    course = db_session.query(Course).first()
    headers = {"Authorization": f"Bearer {token}"}

    res = client.post(
        "/api/v1/recommendations/generate-course",
        headers=headers,
        json={
            "course_id": course.id,
            "planning_topic": "Comprensión lectora unidad 3",
            "include_per_student": True,
            **AI_CONSENT,
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["course"]["scope"] == "course"
    assert body["course"]["student_id"] is None
    assert "Curso completo" in body["course"]["student_name"]
    assert len(body["course"]["body"]) > 400
    assert body["course"]["course_context"]["student_count"] >= 1
    assert body["student_count"] >= 1
    assert len(body["students"]) == body["student_count"]
    assert all(s["scope"] == "student" for s in body["students"])


def test_generate_course_without_batch(client, db_session):
    token = _login(client)
    course = db_session.query(Course).first()
    headers = {"Authorization": f"Bearer {token}"}

    res = client.post(
        "/api/v1/recommendations/generate-course",
        headers=headers,
        json={
            "course_id": course.id,
            "planning_topic": "Fracciones y representación visual",
            "include_per_student": False,
            **AI_CONSENT,
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["student_count"] == 0
    assert body["students"] == []