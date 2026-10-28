from pydantic import BaseModel, Field

from app.schemas.auth import CONSENT_VERSION


class DiagnosticOption(BaseModel):
    value: int
    label: str


class DiagnosticItemRead(BaseModel):
    id: int
    sort_order: int
    question_text: str
    options: list[DiagnosticOption]

    model_config = {"from_attributes": True}


class AnswerSubmit(BaseModel):
    item_id: int
    answer_value: int = Field(ge=0, le=2)
    response_ms: int | None = Field(default=None, ge=0)
    skipped: bool = False


class DiagnosticSubmitRequest(BaseModel):
    answers: list[AnswerSubmit]
    consent_accepted: bool = Field(description="Consentimiento informado Ley 19.628 / 21.719")
    consent_version: str = Field(default=CONSENT_VERSION, max_length=32)


class DiagnosticStatusResponse(BaseModel):
    has_profile: bool
    session_id: int | None = None


class ProfileDescriptor(BaseModel):
    key: str
    label: str
    value: float


class PedagogicalProfileRead(BaseModel):
    id: int
    student_id: int
    version: int
    model_version: str
    descriptors: list[ProfileDescriptor]
    feature_importance: dict[str, float]
    created_at: str

    model_config = {"from_attributes": True}
