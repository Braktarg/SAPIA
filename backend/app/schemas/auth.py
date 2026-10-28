from pydantic import BaseModel, EmailStr, Field

from app.core.enums import UserRole

CONSENT_VERSION = "2026-06"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=2, max_length=255)
    org_code: str = Field(min_length=4, max_length=64)
    role: UserRole = Field(description="teacher o student")
    birth_year: int | None = Field(default=None, ge=1990, le=2020)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    role: str
    org_id: int

    model_config = {"from_attributes": True}


class OrgLookupResponse(BaseModel):
    id: int
    name: str
    registration_code: str
