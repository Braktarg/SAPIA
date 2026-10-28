import io
import json
import os
import tempfile

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("UPLOAD_DIR", tempfile.mkdtemp(prefix="sapia_student_test_"))

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
    CurricularDocument,
    DiagnosticSession,
    Enrollment,
    Organization,
    PedagogicalProfile,
    Recommendation,
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
            full_name="Prof. García",
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
        session = DiagnosticSession(student_id=student.id)
        db.add(session)
        db.flush()
        db.add(
            PedagogicalProfile(
                student_id=student.id,
                session_id=session.id,
                version=1,
                descriptors_json=json.dumps({k: 0.7 for k in DESCRIPTOR_KEYS}),
                feature_importance_json=json.dumps({}),
                model_version="rf_v1",
            )
        )
        db.commit()
        ingest_document(
            db,
            course_id=course.id,
            unit_name="Lenguaje",
            filename="guia.pdf",
            content=make_sample_pdf("Material de clase con apoyos visuales para comprensión lectora."),
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


def _token(client: TestClient, email: str) -> str:
    res = client.post("/api/v1/auth/login", json={"email": email, "password": "testpass123"})
    assert res.status_code == 200
    return res.json()["access_token"]


def _generate_and_validate(client, db_session, action: str, reason: str | None = None) -> int:
    teacher_token = _token(client, "docente@test.cl")
    course = db_session.query(Course).first()
    student = db_session.query(User).filter(User.role == UserRole.STUDENT.value).first()
    created = client.post(
        "/api/v1/recommendations/generate",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={
            "student_id": student.id,
            "course_id": course.id,
            "planning_topic": "Lectura guiada unidad 3",
        **AI_CONSENT,
        },
    )
    rec_id = created.json()["id"]
    payload: dict = {"action": action}
    if reason:
        payload["reason"] = reason
    if action == "edit":
        payload["edited_body"] = "Actividad editada y publicada para el estudiante."
    client.post(
        f"/api/v1/recommendations/{rec_id}/validate",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json=payload,
    )
    return rec_id


def test_pt_f_050_only_approved_listed_for_student(client, db_session):
    """PT-F-050: login alumno → solo aprobadas listadas."""
    accepted_id = _generate_and_validate(client, db_session, "accept")
    edited_id = _generate_and_validate(
        client,
        db_session,
        "edit",
        reason="Ajuste pedagógico",
    )

    teacher_token = _token(client, "docente@test.cl")
    course = db_session.query(Course).first()
    student = db_session.query(User).filter(User.role == UserRole.STUDENT.value).first()
    pending = client.post(
        "/api/v1/recommendations/generate",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={
            "student_id": student.id,
            "course_id": course.id,
            "planning_topic": "Tema pendiente sin publicar",
        **AI_CONSENT,
        },
    ).json()["id"]
    rejected = client.post(
        "/api/v1/recommendations/generate",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={
            "student_id": student.id,
            "course_id": course.id,
            "planning_topic": "Tema rechazado",
        **AI_CONSENT,
        },
    ).json()["id"]
    client.post(
        f"/api/v1/recommendations/{rejected}/validate",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={"action": "reject", "reason": "No corresponde al nivel"},
    )

    student_token = _token(client, "estudiante@test.cl")
    listed = client.get(
        "/api/v1/student/recommendations",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert listed.status_code == 200
    items = listed.json()
    ids = {i["id"] for i in items}
    assert accepted_id in ids
    assert edited_id in ids
    assert pending not in ids
    assert rejected not in ids
    assert all(i["status"] in ("accepted", "edited") for i in items)
    assert all(i["explanation"] for i in items)
    assert all("explanation_student" in i for i in items)
    assert all(i["my_difficulty_rating"] is None for i in items)
    assert all(i["teacher_name"] == "Prof. García" for i in items)


def test_student_cannot_access_teacher_inbox(client, db_session):
    student_token = _token(client, "estudiante@test.cl")
    res = client.get(
        "/api/v1/recommendations/inbox",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert res.status_code == 403


def test_student_cannot_view_pending_detail(client, db_session):
    teacher_token = _token(client, "docente@test.cl")
    course = db_session.query(Course).first()
    student = db_session.query(User).filter(User.role == UserRole.STUDENT.value).first()
    pending_id = client.post(
        "/api/v1/recommendations/generate",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={
            "student_id": student.id,
            "course_id": course.id,
            "planning_topic": "Solo docente",
        **AI_CONSENT,
        },
    ).json()["id"]

    student_token = _token(client, "estudiante@test.cl")
    res = client.get(
        f"/api/v1/student/recommendations/{pending_id}",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert res.status_code == 404


def test_student_can_download_linked_pdf(client, db_session):
    rec_id = _generate_and_validate(client, db_session, "accept")
    student_token = _token(client, "estudiante@test.cl")
    detail = client.get(
        f"/api/v1/student/recommendations/{rec_id}",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert detail.status_code == 200
    resources = detail.json()["resources"]
    assert len(resources) > 0
    doc_id = resources[0]["document_id"]

    download = client.get(
        f"/api/v1/student/documents/{doc_id}/download",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/pdf"
    assert download.content[:4] == b"%PDF"

    foreign_doc = db_session.query(CurricularDocument).first().id + 9999
    denied = client.get(
        f"/api/v1/student/documents/{foreign_doc}/download",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert denied.status_code in (403, 404)


def test_student_difficulty_feedback_and_analytics(client, db_session):
    rec_id = _generate_and_validate(client, db_session, "accept")
    student_token = _token(client, "estudiante@test.cl")

    detail = client.get(
        f"/api/v1/student/recommendations/{rec_id}",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert detail.status_code == 200
    body = detail.json()
    assert body["explanation_student"]
    assert body["my_difficulty_rating"] is None

    bad = client.post(
        f"/api/v1/student/recommendations/{rec_id}/feedback",
        headers={"Authorization": f"Bearer {student_token}"},
        json={"difficulty_rating": 6},
    )
    assert bad.status_code == 422

    ok = client.post(
        f"/api/v1/student/recommendations/{rec_id}/feedback",
        headers={"Authorization": f"Bearer {student_token}"},
        json={"difficulty_rating": 4},
    )
    assert ok.status_code == 201
    assert ok.json()["difficulty_rating"] == 4

    detail2 = client.get(
        f"/api/v1/student/recommendations/{rec_id}",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert detail2.json()["my_difficulty_rating"] == 4

    update = client.post(
        f"/api/v1/student/recommendations/{rec_id}/feedback",
        headers={"Authorization": f"Bearer {student_token}"},
        json={"difficulty_rating": 2},
    )
    assert update.status_code == 201
    assert update.json()["difficulty_rating"] == 2

    teacher_token = _token(client, "docente@test.cl")
    course = db_session.query(Course).first()
    analytics = client.get(
        f"/api/v1/teacher/courses/{course.id}/analytics",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert analytics.status_code == 200
    data = analytics.json()
    assert data["difficulty_feedback_count"] == 1
    assert data["difficulty_rating_avg"] == 2.0