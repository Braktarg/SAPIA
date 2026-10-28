from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DiagnosticItem(Base):
    __tablename__ = "diagnostic_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    options_json: Mapped[str] = mapped_column(Text, nullable=False)
    feature_key: Mapped[str] = mapped_column(String(64), nullable=False)

    answers: Mapped[list["DiagnosticAnswer"]] = relationship(back_populates="item")


class DiagnosticSession(Base):
    __tablename__ = "diagnostic_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consent_given: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    consent_version: Mapped[str | None] = mapped_column(String(32), nullable=True)

    answers: Mapped[list["DiagnosticAnswer"]] = relationship(back_populates="session")
    profile: Mapped["PedagogicalProfile | None"] = relationship(back_populates="session")


class DiagnosticAnswer(Base):
    __tablename__ = "diagnostic_answers"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("diagnostic_sessions.id"), nullable=False)
    item_id: Mapped[int] = mapped_column(ForeignKey("diagnostic_items.id"), nullable=False)
    answer_value: Mapped[int] = mapped_column(Integer, nullable=False)
    response_ms: Mapped[int | None] = mapped_column(Integer)
    skipped: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    session: Mapped["DiagnosticSession"] = relationship(back_populates="answers")
    item: Mapped["DiagnosticItem"] = relationship(back_populates="answers")


class PedagogicalProfile(Base):
    __tablename__ = "pedagogical_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("diagnostic_sessions.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    descriptors_json: Mapped[str] = mapped_column(Text, nullable=False)
    feature_importance_json: Mapped[str | None] = mapped_column(Text)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped["DiagnosticSession"] = relationship(back_populates="profile")
