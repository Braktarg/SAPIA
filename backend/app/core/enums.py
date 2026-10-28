from enum import Enum


class UserRole(str, Enum):
    TEACHER = "teacher"
    STUDENT = "student"
    ADMIN = "admin"
    COORDINATOR = "coordinator"


class RecommendationStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EDITED = "edited"


class ValidationAction(str, Enum):
    ACCEPT = "accept"
    REJECT = "reject"
    EDIT = "edit"


class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


class RecommendationScope(str, Enum):
    STUDENT = "student"
    COURSE = "course"
