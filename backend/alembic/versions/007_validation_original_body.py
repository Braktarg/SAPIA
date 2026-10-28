"""validation original_body for MitL comparator

Revision ID: 007
Revises: 006
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("recommendation_validations", sa.Column("original_body", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("recommendation_validations", "original_body")
