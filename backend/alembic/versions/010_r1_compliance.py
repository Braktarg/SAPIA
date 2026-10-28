"""R1 compliance: org registration_code, diagnostic consent

Revision ID: 010
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("registration_code", sa.String(64), nullable=True))
    op.create_index(
        "ix_organizations_registration_code",
        "organizations",
        ["registration_code"],
        unique=True,
    )
    op.add_column(
        "diagnostic_sessions",
        sa.Column("consent_given", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("diagnostic_sessions", sa.Column("consent_version", sa.String(32), nullable=True))
    op.execute(
        sa.text(
            "UPDATE organizations SET registration_code = 'DEMO-SAPIA' "
            "WHERE registration_code IS NULL AND name ILIKE '%Demo%'"
        )
    )


def downgrade() -> None:
    op.drop_column("diagnostic_sessions", "consent_version")
    op.drop_column("diagnostic_sessions", "consent_given")
    op.drop_index("ix_organizations_registration_code", table_name="organizations")
    op.drop_column("organizations", "registration_code")
