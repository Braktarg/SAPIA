import json

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.enums import UserRole
from app.core.security import create_access_token, hash_password, verify_password
from app.models import AuditEvent, Organization, User
from app.schemas.auth import LoginRequest, RegisterRequest


def authenticate_user(db: Session, credentials: LoginRequest) -> User:
    user = db.query(User).filter(User.email == credentials.email).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")
    if not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")
    return user


def issue_token(user: User) -> str:
    return create_access_token(
        subject=str(user.id),
        extra={"role": user.role, "org_id": user.org_id, "email": user.email},
    )


def register_user(db: Session, body: RegisterRequest) -> User:
    if body.role not in (UserRole.TEACHER, UserRole.STUDENT):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se permite registro como docente o estudiante",
        )
    org = (
        db.query(Organization)
        .filter(Organization.registration_code == body.org_code.strip().upper())
        .first()
    )
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Código de establecimiento inválido")
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El correo ya está registrado")
    user = User(
        org_id=org.id,
        email=body.email.lower(),
        password_hash=hash_password(body.password),
        full_name=body.full_name.strip(),
        birth_year=body.birth_year if body.role == UserRole.STUDENT else None,
        role=body.role.value,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    log_audit(
        db,
        org_id=org.id,
        actor_id=user.id,
        entity_type="user",
        entity_id=str(user.id),
        action="register",
        payload={"email": user.email, "role": user.role},
    )
    return user


def log_audit(
    db: Session,
    *,
    org_id: int,
    actor_id: int | None,
    entity_type: str,
    entity_id: str | None,
    action: str,
    payload: dict | None = None,
) -> None:
    event = AuditEvent(
        org_id=org_id,
        actor_id=actor_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        payload_json=json.dumps(payload) if payload else None,
    )
    db.add(event)
    db.commit()


def require_roles(user: User, allowed: set[UserRole]) -> None:
    if user.role_enum not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado para este rol")
