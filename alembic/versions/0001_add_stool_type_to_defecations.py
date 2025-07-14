"""
Add stool_type to defecations

Revision ID: 0001_add_stool_type_to_defecations
Revises:
Create Date: 2025-07-15 00:00:00
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001_add_stool_type_to_defecations"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    stool_enum = postgresql.ENUM("normal", "hard", "liquid", name="stooltype")
    stool_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "defecations",
        sa.Column(
            "stool_type", sa.Enum("normal", "hard", "liquid", name="stooltype"), nullable=False, server_default="normal"
        ),
    )

    op.alter_column("defecations", "stool_type", server_default=None)


def downgrade():
    op.drop_column("defecations", "stool_type")
    stool_enum = postgresql.ENUM("normal", "hard", "liquid", name="stooltype")
    stool_enum.drop(op.get_bind(), checkfirst=True)
