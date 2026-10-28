"""recommendation_feedback (autoevaluación dificultad 1-5)

Revision ID: 009
Revises: 008
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "recommendation_feedback",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recommendation_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("difficulty_rating", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["recommendation_id"], ["recommendations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("recommendation_id", "student_id", name="uq_rec_feedback_student"),
    )
    op.create_index(
        op.f("ix_recommendation_feedback_recommendation_id"),
        "recommendation_feedback",
        ["recommendation_id"],
    )
    op.create_index(
        op.f("ix_recommendation_feedback_student_id"),
        "recommendation_feedback",
        ["student_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_recommendation_feedback_student_id"), table_name="recommendation_feedback")
    op.drop_index(
        op.f("ix_recommendation_feedback_recommendation_id"), table_name="recommendation_feedback"
    )
    op.drop_table("recommendation_feedback")
