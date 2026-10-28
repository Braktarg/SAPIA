"""diagnostic and pedagogical profile tables

Revision ID: 002
Revises: 001
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "diagnostic_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("options_json", sa.Text(), nullable=False),
        sa.Column("feature_key", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "diagnostic_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "diagnostic_answers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("answer_value", sa.Integer(), nullable=False),
        sa.Column("response_ms", sa.Integer(), nullable=True),
        sa.Column("skipped", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["item_id"], ["diagnostic_items.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["diagnostic_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "pedagogical_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("descriptors_json", sa.Text(), nullable=False),
        sa.Column("feature_importance_json", sa.Text(), nullable=True),
        sa.Column("model_version", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["diagnostic_sessions.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pedagogical_profiles_student_id"), "pedagogical_profiles", ["student_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_pedagogical_profiles_student_id"), table_name="pedagogical_profiles")
    op.drop_table("pedagogical_profiles")
    op.drop_table("diagnostic_answers")
    op.drop_table("diagnostic_sessions")
    op.drop_table("diagnostic_items")
