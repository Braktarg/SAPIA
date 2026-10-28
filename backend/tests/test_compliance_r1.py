"""Tests de cumplimiento R1: registro, import/export, consentimiento."""

import io
import os
import tempfile

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("UPLOAD_DIR", tempfile.mkdtemp(prefix="sapia_r1_"))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.enums import UserRole
from app.core.security import hash_password
from app.main import app
from app.models import Course, CourseTeacher, Organization, User

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture()
def api_client():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        org = Organization(name="Colegio R1", registration_code="DEMO-SAPIA")
        db.add(org)
        db.flush()
        teacher = User(
            org_id=org.id,
            email="docente@r1.cl",
            password_hash=hash_password("testpass123"),
            full_name="Docente R1",
            role=UserRole.TEACHER.value,
        )
        db.add(teacher)
        db.flush()
        course = Course(org_id=org.id, name="7º A", grade_level="7°")
        db.add(course)
        db.flush()
        db.add(CourseTeacher(course_id=course.id, teacher_id=teacher.id))
        db.commit()

        def override_get_db():
            try:
                yield db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app) as client:
            yield client, db, course.id
    finally:
        app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_public_register_with_org_code(api_client):
    client, db, _ = api_client
    res = client.post(
        "/api/v1/auth/register",
        json={
            "email": "nuevo@r1.cl",
            "password": "clave1234",
            "full_name": "Nuevo Estudiante",
            "org_code": "DEMO-SAPIA",
            "role": "student",
            "birth_year": 2012,
        },
    )
    assert res.status_code == 201, res.text
    assert res.json()["access_token"]
    user = db.query(User).filter(User.email == "nuevo@r1.cl").first()
    assert user is not None
    assert user.role == UserRole.STUDENT.value


def test_org_lookup(api_client):
    client, _, _ = api_client
    ok = client.get("/api/v1/auth/org-lookup?code=DEMO-SAPIA")
    assert ok.status_code == 200
    assert ok.json()["name"] == "Colegio R1"
    bad = client.get("/api/v1/auth/org-lookup?code=INVALID")
    assert bad.status_code == 404


def test_export_xlsx(api_client):
    client, db, _ = api_client
    course = db.query(Course).first()
    token = client.post(
        "/api/v1/auth/login",
        json={"email": "docente@r1.cl", "password": "testpass123"},
    ).json()["access_token"]
    res = client.get(
        f"/api/v1/reports/course/{course.id}/xlsx",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert "spreadsheetml" in res.headers["content-type"]
    assert len(res.content) > 100


def test_import_students_csv(api_client):
    client, db, _ = api_client
    course = db.query(Course).first()
    token = client.post(
        "/api/v1/auth/login",
        json={"email": "docente@r1.cl", "password": "testpass123"},
    ).json()["access_token"]
    csv_body = "full_name,email,birth_year\nAlumno CSV,alumno.csv@r1.cl,2011\n"
    res = client.post(
        f"/api/v1/reports/course/{course.id}/import-csv",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("estudiantes.csv", io.BytesIO(csv_body.encode("utf-8")), "text/csv")},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["created"] >= 1
    assert body["enrolled"] >= 1
