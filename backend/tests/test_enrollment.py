import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.enums import UserRole
from app.core.security import hash_password
from app.main import app
from app.models import Course, CourseTeacher, Enrollment, Organization, User

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


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
        outsider = User(
            org_id=org.id,
            email="alumno2@test.cl",
            password_hash=hash_password("testpass123"),
            full_name="Alumno Sin Curso",
            role=UserRole.STUDENT.value,
        )
        enrolled = User(
            org_id=org.id,
            email="alumno1@test.cl",
            password_hash=hash_password("testpass123"),
            full_name="Alumno En Curso",
            role=UserRole.STUDENT.value,
        )
        db.add_all([teacher, outsider, enrolled])
        db.flush()
        course = Course(org_id=org.id, name="8º A", grade_level="8°")
        db.add(course)
        db.flush()
        db.add(CourseTeacher(course_id=course.id, teacher_id=teacher.id))
        db.add(Enrollment(course_id=course.id, student_id=enrolled.id))
        db.commit()
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


def _login(client: TestClient) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": "docente@test.cl", "password": "testpass123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_enroll_student_rf_04(client: TestClient, db_session):
    """RF-04: docente matricula estudiante en curso."""
    headers = _login(client)
    course = db_session.query(Course).first()
    student = db_session.query(User).filter(User.email == "alumno2@test.cl").first()
    r = client.post(
        f"/api/v1/courses/{course.id}/students",
        headers=headers,
        json={"student_id": student.id},
    )
    assert r.status_code == 201, r.text
    listed = client.get(f"/api/v1/students?course_id={course.id}", headers=headers)
    assert listed.status_code == 200
    emails = [s["email"] for s in listed.json()]
    assert "alumno2@test.cl" in emails


def test_enroll_duplicate_conflict(client: TestClient, db_session):
    headers = _login(client)
    course = db_session.query(Course).first()
    student = db_session.query(User).filter(User.email == "alumno1@test.cl").first()
    r = client.post(
        f"/api/v1/courses/{course.id}/students",
        headers=headers,
        json={"student_id": student.id},
    )
    assert r.status_code == 409


def test_unenroll_student(client: TestClient, db_session):
    headers = _login(client)
    course = db_session.query(Course).first()
    student = db_session.query(User).filter(User.email == "alumno1@test.cl").first()
    r = client.delete(f"/api/v1/courses/{course.id}/students/{student.id}", headers=headers)
    assert r.status_code == 200
    listed = client.get(f"/api/v1/students?course_id={course.id}", headers=headers)
    emails = [s["email"] for s in listed.json()]
    assert "alumno1@test.cl" not in emails
