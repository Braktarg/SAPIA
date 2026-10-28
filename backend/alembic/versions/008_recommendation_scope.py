"""recommendation scope (student | course) and nullable student_id

Revision ID: 008
Revises: 007
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "recommendations",
        sa.Column("scope", sa.String(length=16), nullable=False, server_default="student"),
    )
    op.add_column(
        "recommendations",
        sa.Column("context_json", sa.Text(), nullable=True),
    )
    op.alter_column("recommendations", "student_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    op.alter_column("recommendations", "student_id", existing_type=sa.Integer(), nullable=False)
    op.drop_column("recommendations", "context_json")
    op.drop_column("recommendations", "scope")
