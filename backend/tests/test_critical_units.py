"""Pruebas unitarias de módulos críticos (cobertura S8)."""

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

import numpy as np
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.core.enums import UserRole
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.models import Course, Organization, User
from app.schemas.auth import LoginRequest
from app.services.auth_service import authenticate_user, require_roles
from app.services.audit_service import build_course_summary
from ml.predictor import get_predictor
from tests.consent_helpers import AI_CONSENT, DIAG_CONSENT
from rag.chunking import chunk_text, estimate_tokens
from rag.embeddings import embed_text
from rag.generate import generate_recommendation
from rag.retrieve import cosine_similarity

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
Session = sessionmaker(bind=engine)


def test_security_password_and_jwt_roundtrip():
    hashed = hash_password("Sapia2026!")
    assert verify_password("Sapia2026!", hashed)
    assert not verify_password("wrong", hashed)

    token = create_access_token("42", extra={"role": "teacher"})
    payload = decode_access_token(token)
    assert payload["sub"] == "42"
    assert payload["role"] == "teacher"


def test_security_invalid_token_raises():
    with pytest.raises(ValueError, match="Token"):
        decode_access_token("not.a.valid.jwt")


def test_auth_service_authenticate_and_rbac():
    Base.metadata.create_all(bind=engine)
    db = Session()
    try:
        org = Organization(name="Org", registration_code="TEST-ORG")
        db.add(org)
        db.flush()
        user = User(
            org_id=org.id,
            email="t@test.cl",
            password_hash=hash_password("secret123"),
            full_name="T",
            role=UserRole.TEACHER.value,
        )
        db.add(user)
        db.commit()

        ok = authenticate_user(db, LoginRequest(email="t@test.cl", password="secret123"))
        assert ok.id == user.id

        with pytest.raises(HTTPException) as exc:
            authenticate_user(db, LoginRequest(email="t@test.cl", password="wrong12"))
        assert exc.value.status_code == 401

        require_roles(ok, {UserRole.TEACHER})
        with pytest.raises(HTTPException):
            require_roles(ok, {UserRole.STUDENT})
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_chunking_and_embeddings():
    long_text = "palabra " * 500
    chunks = chunk_text(long_text, chunk_size=100, overlap=10)
    assert len(chunks) > 1
    assert estimate_tokens("uno dos tres") == 3

    vec = embed_text("comprensión lectora apoyos visuales")
    assert len(vec) > 0
    assert abs(np.linalg.norm(np.array(vec)) - 1.0) < 0.01


def test_cosine_similarity_identical():
    v = [0.1, 0.2, 0.3]
    assert cosine_similarity(v, v) == pytest.approx(1.0, abs=0.001)


def test_generate_template_fallback():
    result = generate_recommendation(
        planning_topic="Fracciones",
        descriptors=[{"label": "Comprensión lectora", "value": 0.8}],
        chunks=[],
        student_name="Ana",
    )
    assert result.title
    assert len(result.body) > 400
    assert "Objetivos" in result.body or "Secuencia" in result.body
    assert "Por qué" in result.explanation or "perfil" in result.explanation.lower()
    assert result.degraded_mode is True


def test_generate_course_template():
    from rag.generate import StudentProfileSnapshot, generate_course_recommendation

    profiles = [
        StudentProfileSnapshot(
            student_id=1,
            student_name="Ana",
            descriptors=[{"label": "Apoyo visual", "value": 0.85}],
            profile_version=1,
        ),
        StudentProfileSnapshot(
            student_id=2,
            student_name="Luis",
            descriptors=[{"label": "Atención sostenida", "value": 0.35}],
            profile_version=1,
        ),
    ]
    result = generate_course_recommendation(
        planning_topic="Ecuaciones",
        course_name="8° A",
        student_profiles=profiles,
        chunks=[],
    )
    assert "Ana" in result.body
    assert "Luis" in result.body
    assert "Anclaje curricular" in result.body
    assert "cadena de evidencia" in result.explanation.lower()
    assert result.evidence_chain is not None
    assert len(result.body) > 500
    assert result.degraded_mode is True


def test_predictor_returns_descriptors():
    predictor = get_predictor()
    answers = [1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1, 2]
    descriptors, importances = predictor.predict(answers)
    assert len(descriptors) == 6
    assert all(0.0 <= v <= 1.0 for v in descriptors.values())


def test_predictor_rejects_wrong_length():
    predictor = get_predictor()
    with pytest.raises(ValueError):
        predictor.predict([1, 2, 3])


def test_audit_course_summary():
    Base.metadata.create_all(bind=engine)
    db = Session()
    try:
        org = Organization(name="Org", registration_code="TEST-ORG")
        db.add(org)
        db.flush()
        course = Course(org_id=org.id, name="8A", grade_level="8")
        db.add(course)
        db.commit()
        summary = build_course_summary(db, course)
        assert summary.course_name == "8A"
        assert summary.tai_pct == 0.0
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_parse_llm_response_accepts_markdown_section_headers():
    from rag.generate import _parse_llm_response

    text = """## TITULO: Ecuaciones para 8° básico

## CUERPO:
Objetivos de aprendizaje claros para todo el curso.
Inicio con agenda visual y activación con material del PDF.
Desarrollo con estaciones diferenciadas según perfil pedagógico.
Cierre con ticket de salida y retroalimentación específica.
Adaptaciones TEA: pictogramas, pasos numerados y pausas programadas.
Materiales: recta numérica, fichas de trabajo y glosario visual.
Evaluación formativa con rúbrica de tres niveles y evidencias heterogéneas.

## EXPLICACION:
¿Por qué se sugiere?
Porque el perfil del curso requiere apoyos visuales y segmentación temporal.
"""
    title, body, explanation, used_fallback = _parse_llm_response(
        text, "Ecuaciones", [], [], "8° A"
    )
    assert used_fallback is False
    assert "Ecuaciones" in title
    assert len(body) >= 200
    assert "¿Por qué" in explanation


def test_parse_llm_response_heuristic_without_labels():
    from rag.generate import _parse_llm_response

    intro = "Planificación diferenciada sobre fracciones.\n" + ("Párrafo pedagógico. " * 40)
    text = intro + "\n\n¿Por qué se sugiere?\nPor el perfil visual del estudiante."
    _, body, explanation, used_fallback = _parse_llm_response(
        text, "Fracciones", [], [], "Ana"
    )
    assert used_fallback is False
    assert len(body) >= 200
    assert "perfil visual" in explanation