import io
import os
import tempfile

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("UPLOAD_DIR", tempfile.mkdtemp(prefix="sapia_test_uploads_"))

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
from app.models import Course, CourseTeacher, DocumentChunk, Organization, User
from app.services.document_service import DocumentServiceError, count_indexed_chunks, ingest_document
from rag.chunking import chunk_text

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def make_sample_pdf(text: str = "Unidad de matemáticas: fracciones y decimales para octavo básico.") -> bytes:
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
        db.add(teacher)
        db.flush()
        course = Course(org_id=org.id, name="8º A", grade_level="8°")
        db.add(course)
        db.flush()
        db.add(CourseTeacher(course_id=course.id, teacher_id=teacher.id))
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


def _login(client: TestClient, email: str = "docente@test.cl") -> str:
    res = client.post("/api/v1/auth/login", json={"email": email, "password": "testpass123"})
    assert res.status_code == 200
    return res.json()["access_token"]


def test_chunk_text_splits_long_content():
    text = "palabra " * 800
    chunks = chunk_text(text, chunk_size=200, overlap=20)
    assert len(chunks) > 1
    assert all(len(c) <= 220 for c in chunks)


def test_pt_f_020_rejects_invalid_upload(client, db_session):
    """PT-F-020: rechaza archivo que no es PDF válido."""
    token = _login(client)
    course_id = db_session.query(Course).first().id
    res = client.post(
        f"/api/v1/courses/{course_id}/documents",
        headers={"Authorization": f"Bearer {token}"},
        data={"unit_name": "Unidad 1"},
        files={"file": ("nota.txt", b"esto no es pdf", "text/plain")},
    )
    assert res.status_code == 400
    assert "PDF" in res.json()["detail"]


def test_pt_f_022_indexes_pdf_chunks(client, db_session):
    """PT-F-022: PDF válido genera chunks indexados (>0)."""
    token = _login(client)
    course = db_session.query(Course).first()
    pdf_bytes = make_sample_pdf("Contenido curricular sobre ecuaciones lineales y representación gráfica.")
    res = client.post(
        f"/api/v1/courses/{course.id}/documents",
        headers={"Authorization": f"Bearer {token}"},
        data={"unit_name": "Álgebra"},
        files={"file": ("unidad.pdf", pdf_bytes, "application/pdf")},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["document"]["status"] == "indexed"
    assert body["document"]["chunk_count"] > 0
    assert body["processing_ms"] < 30_000

    chunks = count_indexed_chunks(db_session, body["document"]["id"])
    assert chunks > 0
    stored = db_session.query(DocumentChunk).count()
    assert stored == chunks


def test_list_and_delete_document(client, db_session):
    token = _login(client)
    course = db_session.query(Course).first()
    pdf_bytes = make_sample_pdf()
    upload = client.post(
        f"/api/v1/courses/{course.id}/documents",
        headers={"Authorization": f"Bearer {token}"},
        data={"unit_name": "Ciencias"},
        files={"file": ("ciencias.pdf", pdf_bytes, "application/pdf")},
    )
    doc_id = upload.json()["document"]["id"]

    listed = client.get(
        f"/api/v1/courses/{course.id}/documents",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert listed.status_code == 200
    assert any(d["id"] == doc_id for d in listed.json())

    deleted = client.delete(
        f"/api/v1/documents/{doc_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert deleted.status_code == 204
    assert db_session.query(DocumentChunk).count() == 0


def test_ingest_requires_unit_name(db_session):
    course = db_session.query(Course).first()
    pdf_bytes = make_sample_pdf()
    with pytest.raises(DocumentServiceError):
        ingest_document(
            db_session,
            course_id=course.id,
            unit_name="   ",
            filename="a.pdf",
            content=pdf_bytes,
        )
