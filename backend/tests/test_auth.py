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
from app.models import Organization, User

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
        db.add_all(
            [
                User(
                    org_id=org.id,
                    email="admin@test.cl",
                    password_hash=hash_password("testpass123"),
                    full_name="Admin Test",
                    role=UserRole.ADMIN.value,
                ),
                User(
                    org_id=org.id,
                    email="docente@test.cl",
                    password_hash=hash_password("testpass123"),
                    full_name="Docente Test",
                    role=UserRole.TEACHER.value,
                ),
                User(
                    org_id=org.id,
                    email="estudiante@test.cl",
                    password_hash=hash_password("testpass123"),
                    full_name="Estudiante Test",
                    role=UserRole.STUDENT.value,
                ),
            ]
        )
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


def auth_header(client: TestClient, email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "testpass123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_login_teacher_pt_f_001(client: TestClient):
    r = client.post("/api/v1/auth/login", json={"email": "docente@test.cl", "password": "testpass123"})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_login_student_pt_f_002(client: TestClient):
    r = client.post("/api/v1/auth/login", json={"email": "estudiante@test.cl", "password": "testpass123"})
    assert r.status_code == 200


def test_rbac_student_cannot_access_admin(client: TestClient):
    headers = auth_header(client, "estudiante@test.cl")
    r = client.get("/api/v1/admin/users", headers=headers)
    assert r.status_code == 403


def test_pt_f_003_admin_creates_user(client: TestClient):
    """PT-F-003: admin crea usuario → registro en BD con rol."""
    headers = auth_header(client, "admin@test.cl")
    r = client.post(
        "/api/v1/admin/users",
        headers=headers,
        json={
            "email": "nuevo@test.cl",
            "password": "testpass123",
            "full_name": "Usuario Nuevo",
            "role": "teacher",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["email"] == "nuevo@test.cl"
    assert body["role"] == UserRole.TEACHER.value
    listed = client.get("/api/v1/admin/users", headers=headers)
    assert any(u["email"] == "nuevo@test.cl" for u in listed.json())


def test_admin_deactivates_user(client: TestClient):
    headers = auth_header(client, "admin@test.cl")
    created = client.post(
        "/api/v1/admin/users",
        headers=headers,
        json={
            "email": "temp@test.cl",
            "password": "testpass123",
            "full_name": "Temporal",
            "role": "student",
        },
    )
    user_id = created.json()["id"]
    r = client.patch(
        f"/api/v1/admin/users/{user_id}",
        headers=headers,
        json={"is_active": False},
    )
    assert r.status_code == 200
    assert r.json()["is_active"] is False


def test_logout_audited(client: TestClient):
    headers = auth_header(client, "docente@test.cl")
    r = client.post("/api/v1/auth/logout", headers=headers)
    assert r.status_code == 200


def test_pt_f_004_student_cannot_access_teacher_routes(client: TestClient):
    """PT-F-004: estudiante no accede a rutas docente."""
    headers = auth_header(client, "estudiante@test.cl")
    assert client.get("/api/v1/recommendations/inbox", headers=headers).status_code == 403
    assert client.get("/api/v1/students", headers=headers).status_code == 403


def test_me_returns_role(client: TestClient):
    headers = auth_header(client, "docente@test.cl")
    r = client.get("/api/v1/auth/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["role"] == UserRole.TEACHER.value


def test_health(client: TestClient):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert isinstance(body["openai_configured"], bool)
    assert isinstance(body["llm_model"], str)
