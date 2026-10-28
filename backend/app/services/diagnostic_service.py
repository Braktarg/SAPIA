import json
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.enums import UserRole
from app.models import DiagnosticAnswer, DiagnosticItem, DiagnosticSession, PedagogicalProfile, User
from app.schemas.diagnostic import AnswerSubmit, ProfileDescriptor
from app.services.auth_service import log_audit
from ml.predictor import get_predictor
from ml.questions import DESCRIPTOR_KEYS

DESCRIPTOR_LABELS = {
    "comprension_lectora": "Comprensión lectora",
    "razonamiento_logico": "Razonamiento lógico",
    "autonomia": "Autonomía en tarea",
    "preferencia_visual": "Preferencia visual",
    "atencion_sostenida": "Atención sostenida",
    "regulacion_emocional": "Regulación emocional",
}


def get_latest_profile(db: Session, student_id: int) -> PedagogicalProfile | None:
    return (
        db.query(PedagogicalProfile)
        .filter(PedagogicalProfile.student_id == student_id)
        .order_by(PedagogicalProfile.version.desc())
        .first()
    )


def student_has_profile(db: Session, student_id: int) -> bool:
    return get_latest_profile(db, student_id) is not None


def complete_diagnostic(
    db: Session,
    student: User,
    answers: list[AnswerSubmit],
    *,
    consent_accepted: bool,
    consent_version: str,
) -> PedagogicalProfile:
    if student.role_enum != UserRole.STUDENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo estudiantes")

    if not consent_accepted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe aceptar el consentimiento informado para procesar el test",
        )

    items = db.query(DiagnosticItem).order_by(DiagnosticItem.sort_order).all()
    if len(items) != 12:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Banco incompleto")

    if len(answers) != 12:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Debe responder 12 ítems")

    item_ids = {i.id for i in items}
    if {a.item_id for a in answers} != item_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ítems inválidos")

    session = DiagnosticSession(
        student_id=student.id,
        consent_given=True,
        consent_version=consent_version,
    )
    db.add(session)
    db.flush()

    values_by_order: list[int] = [0] * 12
    for ans in answers:
        item = next(i for i in items if i.id == ans.item_id)
        db.add(
            DiagnosticAnswer(
                session_id=session.id,
                item_id=ans.item_id,
                answer_value=ans.answer_value,
                response_ms=ans.response_ms,
                skipped=ans.skipped,
            )
        )
        values_by_order[item.sort_order - 1] = 0 if ans.skipped else ans.answer_value

    predictor = get_predictor()
    descriptors, importances = predictor.predict(values_by_order)

    latest = get_latest_profile(db, student.id)
    version = 1 if latest is None else latest.version + 1

    profile = PedagogicalProfile(
        student_id=student.id,
        session_id=session.id,
        version=version,
        descriptors_json=json.dumps(descriptors),
        feature_importance_json=json.dumps(importances),
        model_version=predictor.model_version,
    )
    session.completed_at = datetime.now(UTC)
    db.add(profile)
    db.commit()
    db.refresh(profile)

    log_audit(
        db,
        org_id=student.org_id,
        actor_id=student.id,
        entity_type="pedagogical_profile",
        entity_id=str(profile.id),
        action="profile_generated",
        payload={"model_version": profile.model_version, "version": version},
    )
    return profile


def profile_to_read(profile: PedagogicalProfile) -> dict:
    descriptors_raw = json.loads(profile.descriptors_json)
    importances = json.loads(profile.feature_importance_json or "{}")
    descriptors = [
        ProfileDescriptor(key=k, label=DESCRIPTOR_LABELS.get(k, k), value=descriptors_raw[k])
        for k in DESCRIPTOR_KEYS
        if k in descriptors_raw
    ]
    return {
        "id": profile.id,
        "student_id": profile.student_id,
        "version": profile.version,
        "model_version": profile.model_version,
        "descriptors": descriptors,
        "feature_importance": importances,
        "created_at": profile.created_at.isoformat(),
    }
