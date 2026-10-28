from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from app.schemas.auth import CONSENT_VERSION


class GenerateRecommendationRequest(BaseModel):
    student_id: int
    course_id: int
    planning_topic: str = Field(min_length=3, max_length=500)
    ai_consent_accepted: bool = Field(
        description="Consentimiento docente para procesamiento con IA (RNF-37)",
    )
    consent_version: str = Field(default=CONSENT_VERSION, max_length=32)


class GenerateCourseRecommendationRequest(BaseModel):
    course_id: int
    planning_topic: str = Field(min_length=3, max_length=500)
    include_per_student: bool = True
    ai_consent_accepted: bool = Field(
        description="Consentimiento docente para procesamiento con IA (RNF-37)",
    )
    consent_version: str = Field(default=CONSENT_VERSION, max_length=32)


class SourceChunkRef(BaseModel):
    id: int
    unit_name: str
    snippet: str
    score: float


class RecommendationRead(BaseModel):
    id: int
    student_id: int | None
    student_name: str
    course_id: int
    scope: str = "student"
    course_context: dict | None = None
    evidence_chain: dict | None = None
    teacher_id: int
    status: str
    planning_topic: str
    title: str
    body: str
    explanation: str
    source_chunks: list[SourceChunkRef]
    profile_version: int
    degraded_mode: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class RecommendationSummary(BaseModel):
    id: int
    student_id: int | None
    student_name: str
    course_id: int
    scope: str = "student"
    status: str
    planning_topic: str
    title: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CourseBatchGenerateResponse(BaseModel):
    course: RecommendationRead
    students: list[RecommendationSummary]
    student_count: int


class ValidateRecommendationRequest(BaseModel):
    action: str = Field(pattern="^(accept|reject|edit)$")
    reason: str | None = Field(default=None, max_length=2000)
    edited_body: str | None = Field(default=None, max_length=10000)


class StudentResourceRef(BaseModel):
    document_id: int
    unit_name: str
    filename: str


class StudentRecommendationRead(BaseModel):
    id: int
    title: str
    body: str
    planning_topic: str
    status: str
    explanation: str
    explanation_student: str
    teacher_name: str
    published_at: datetime | None
    resources: list[StudentResourceRef]
    created_at: datetime
    my_difficulty_rating: int | None = None


class StudentFeedbackRequest(BaseModel):
    difficulty_rating: int = Field(ge=1, le=5)


class StudentFeedbackRead(BaseModel):
    difficulty_rating: int
    submitted_at: datetime
