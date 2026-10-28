from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.enums import UserRole
from app.core.security import decode_access_token
from app.models import User
from app.services.auth_service import require_roles

security = HTTPBearer(auto_error=False)


def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No autenticado")
    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
    user = db.query(User).filter(User.id == int(user_id), User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado")
    return user


def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    require_roles(user, {UserRole.ADMIN})
    return user


def require_teacher(user: Annotated[User, Depends(get_current_user)]) -> User:
    require_roles(user, {UserRole.TEACHER, UserRole.ADMIN, UserRole.COORDINATOR})
    return user


def require_student(user: Annotated[User, Depends(get_current_user)]) -> User:
    require_roles(user, {UserRole.STUDENT})
    return user
