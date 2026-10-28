from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.database import get_db
from app.core.security import hash_password
from app.models import User
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services.auth_service import log_audit

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreate,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
) -> User:
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El correo ya está registrado")
    user = User(
        org_id=admin.org_id,
        email=body.email,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        role=body.role.value,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    log_audit(
        db,
        org_id=admin.org_id,
        actor_id=admin.id,
        entity_type="user",
        entity_id=str(user.id),
        action="create_user",
        payload={"email": user.email, "role": user.role},
    )
    return user


@router.get("/users", response_model=list[UserRead])
def list_users(
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
) -> list[User]:
    return db.query(User).filter(User.org_id == admin.org_id).order_by(User.id).all()


@router.patch("/users/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    body: UserUpdate,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
) -> User:
    user = db.query(User).filter(User.id == user_id, User.org_id == admin.org_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    if user.id == admin.id and body.is_active is False:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No puede desactivar su propia cuenta")
    changes: dict = {}
    if body.full_name is not None:
        user.full_name = body.full_name
        changes["full_name"] = body.full_name
    if body.role is not None:
        user.role = body.role.value
        changes["role"] = body.role.value
    if body.is_active is not None:
        user.is_active = body.is_active
        changes["is_active"] = body.is_active
    if body.password is not None:
        user.password_hash = hash_password(body.password)
        changes["password"] = "reset"
    if not changes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sin cambios")
    db.commit()
    db.refresh(user)
    log_audit(
        db,
        org_id=admin.org_id,
        actor_id=admin.id,
        entity_type="user",
        entity_id=str(user.id),
        action="update_user",
        payload=changes,
    )
    return user
