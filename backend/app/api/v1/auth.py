from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import Organization, User
from app.schemas.auth import (
    LoginRequest,
    OrgLookupResponse,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth_service import authenticate_user, issue_token, log_audit, register_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    user = authenticate_user(db, body)
    token = issue_token(user)
    log_audit(
        db,
        org_id=user.org_id,
        actor_id=user.id,
        entity_type="user",
        entity_id=str(user.id),
        action="login",
        payload={"email": user.email},
    )
    return TokenResponse(access_token=token)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(
    body: RegisterRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    user = register_user(db, body)
    token = issue_token(user)
    return TokenResponse(access_token=token)


@router.get("/org-lookup", response_model=OrgLookupResponse)
def org_lookup(
    db: Annotated[Session, Depends(get_db)],
    code: str = Query(min_length=4, max_length=64),
) -> Organization:
    org = (
        db.query(Organization)
        .filter(Organization.registration_code == code.strip().upper())
        .first()
    )
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Código no encontrado")
    return org


@router.get("/me", response_model=UserResponse)
def me(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    return current_user


@router.post("/logout")
def logout(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    log_audit(
        db,
        org_id=current_user.org_id,
        actor_id=current_user.id,
        entity_type="user",
        entity_id=str(current_user.id),
        action="logout",
    )
    return {"message": "Sesión cerrada"}
