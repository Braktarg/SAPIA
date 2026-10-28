from pydantic import BaseModel, Field


class CourseCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    grade_level: str | None = None


class CourseRead(BaseModel):
    id: int
    name: str
    grade_level: str | None
    org_id: int

    model_config = {"from_attributes": True}


class EnrollmentCreate(BaseModel):
    student_id: int
