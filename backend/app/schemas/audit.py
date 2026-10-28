from datetime import datetime

from pydantic import BaseModel


class TimelineStep(BaseModel):
    order: int
    stage: str
    label: str
    detail: str
    timestamp: datetime | None


class RecommendationChain(BaseModel):
    recommendation_id: int
    student_id: int | None
    student_name: str
    planning_topic: str
    status: str
    steps: list[TimelineStep]


class CourseDashboardSummary(BaseModel):
    course_id: int
    course_name: str
    students_total: int
    students_with_profile: int
    recommendations_total: int
    recommendations_pending: int
    recommendations_published: int
    tai_pct: float


class TimelineResponse(BaseModel):
    course_id: int
    summary: CourseDashboardSummary
    chains: list[RecommendationChain]
