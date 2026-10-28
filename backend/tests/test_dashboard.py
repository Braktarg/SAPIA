import io
import json
import os
import tempfile

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("UPLOAD_DIR", tempfile.mkdtemp(prefix="sapia_dashboard_test_"))

import fitz
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.enums import UserRole
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
from tests.consent_helpers import AI_CONSENT

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def make_pdf(text: str) -> bytes:
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
        course = Course(org_id=org.id, name="8º Básico A", grade_level="8°")
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
            unit_name="Ciencias",
            filename="ciencias.pdf",
            content=make_pdf("Contenido curricular de ciencias con apoyos visuales."),
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


def _token(client: TestClient) -> str:
    res = client.post("/api/v1/auth/login", json={"email": "docente@test.cl", "password": "testpass123"})
    return res.json()["access_token"]


def _full_flow(client, db_session) -> tuple[int, int]:
    token = _token(client)
    course = db_session.query(Course).first()
    student = db_session.query(User).filter(User.role == UserRole.STUDENT.value).first()
    created = client.post(
        "/api/v1/recommendations/generate",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "student_id": student.id,
            "course_id": course.id,
            "planning_topic": "Sistema solar unidad 2",
            **AI_CONSENT,
        },
    )
    rec_id = created.json()["id"]
    client.post(
        f"/api/v1/recommendations/{rec_id}/validate",
        headers={"Authorization": f"Bearer {token}"},
        json={"action": "accept"},
    )
    student_token = client.post(
        "/api/v1/auth/login",
        json={"email": "estudiante@test.cl", "password": "testpass123"},
    ).json()["access_token"]
    student_h = {"Authorization": f"Bearer {student_token}"}
    client.get(
        f"/api/v1/student/recommendations/{rec_id}",
        headers=student_h,
    )
    client.post(
        f"/api/v1/student/recommendations/{rec_id}/feedback",
        headers=student_h,
        json={"difficulty_rating": 4},
    )
    return course.id, rec_id


def test_pt_f_060_timeline_seven_links(client, db_session):
    """PT-F-060: historial con cadena de 7 eslabones (RF-47)."""
    course_id, rec_id = _full_flow(client, db_session)
    token = _token(client)

    res = client.get(
        f"/api/v1/audit/timeline?course_id={course_id}&recommendation_id={rec_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["summary"]["students_total"] == 1
    assert len(body["chains"]) == 1
    steps = body["chains"][0]["steps"]
    assert len(steps) == 7
    stages = [s["stage"] for s in steps]
    assert stages == ["profile", "rag", "ai", "teacher", "student", "consumption", "result"]
    assert steps[3]["timestamp"] is not None
    assert steps[4]["timestamp"] is not None
    assert steps[5]["timestamp"] is not None
    assert steps[6]["timestamp"] is not None


def test_pt_f_061_export_csv(client, db_session):
    """PT-F-061: exportar curso → archivo CSV descargable."""
    course_id, _ = _full_flow(client, db_session)
    token = _token(client)

    res = client.get(
        f"/api/v1/reports/course/{course_id}/csv",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert "attachment" in res.headers["content-disposition"]
    text = res.content.decode("utf-8-sig")
    assert "estudiante_nombre" in text.splitlines()[0]
    assert "Estudiante Test" in text
    assert "aceptadas" in text.splitlines()[0]


def test_csv_anonymize(client, db_session):
    course_id, _ = _full_flow(client, db_session)
    token = _token(client)
    res = client.get(
        f"/api/v1/reports/course/{course_id}/csv?anonymize=true",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    text = res.content.decode("utf-8-sig")
    assert "Estudiante_1" in text
    assert "Estudiante Test" not in text
