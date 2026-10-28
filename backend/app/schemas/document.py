from datetime import datetime

from pydantic import BaseModel, Field


class DocumentRead(BaseModel):
    id: int
    course_id: int
    unit_name: str
    original_filename: str
    status: str
    page_count: int | None
    file_size_bytes: int
    chunk_count: int = 0
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentUploadResponse(BaseModel):
    document: DocumentRead
    processing_ms: int


class CourseRead(BaseModel):
    id: int
    name: str
    grade_level: str | None

    model_config = {"from_attributes": True}
