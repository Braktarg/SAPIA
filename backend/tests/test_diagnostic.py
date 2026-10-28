import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.enums import UserRole
from app.core.security import hash_password
from app.main import app
from app.models import DiagnosticItem, Organization, User
from ml.questions import DIAGNOSTIC_QUESTIONS
from tests.consent_helpers import DIAG_CONSENT

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def seed_diagnostic_items_db(db):
    for q in DIAGNOSTIC_QUESTIONS:
        db.add(
            DiagnosticItem(
                sort_order=q["sort_order"],
                question_text=q["question_text"],
                options_json=json.dumps(q["options"]),
                feature_key=q["feature_key"],
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
        db.add(
            User(
                org_id=org.id,
                email="estudiante@test.cl",
                password_hash=hash_password("testpass123"),
                full_name="Estudiante Test",
                role=UserRole.STUDENT.value,
            )
        )
        db.add(
            User(
                org_id=org.id,
                email="docente@test.cl",
                password_hash=hash_password("testpass123"),
                full_name="Docente Test",
                role=UserRole.TEACHER.value,
            )
        )
        seed_diagnostic_items_db(db)
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


def student_headers(client: TestClient) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": "estudiante@test.cl", "password": "testpass123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def teacher_headers(client: TestClient) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": "docente@test.cl", "password": "testpass123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_list_diagnostic_items(client: TestClient):
    headers = student_headers(client)
    r = client.get("/api/v1/diagnostic/items", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) == 12


def test_submit_diagnostic_pt_f_010(client: TestClient):
    headers = student_headers(client)
    items = client.get("/api/v1/diagnostic/items", headers=headers).json()
    answers = [
        {"item_id": it["id"], "answer_value": 1, "response_ms": 1200, "skipped": False}
        for it in items
    ]
    r = client.post("/api/v1/diagnostic/submit", headers=headers, json={"answers": answers, **DIAG_CONSENT})
    assert r.status_code == 201
    assert r.json()["model_version"] == "rf_v1"
    assert len(r.json()["descriptors"]) == 6


def test_profile_generated_under_2s_pt_f_013(client: TestClient):
    import time

    headers = student_headers(client)
    items = client.get("/api/v1/diagnostic/items", headers=headers).json()
    answers = [
        {"item_id": it["id"], "answer_value": 2, "response_ms": 800, "skipped": False}
        for it in items
    ]
    t0 = time.perf_counter()
    r = client.post("/api/v1/diagnostic/submit", headers=headers, json={"answers": answers, **DIAG_CONSENT})
    elapsed = time.perf_counter() - t0
    assert r.status_code == 201
    assert elapsed < 2.0

    student = client.get("/api/v1/auth/me", headers=headers).json()
    t1 = time.perf_counter()
    pr = client.get(f"/api/v1/students/{student['id']}/profile", headers=teacher_headers(client))
    assert pr.status_code == 200
    assert time.perf_counter() - t1 < 2.0
