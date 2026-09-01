"""sync users columns

Revision ID: 72ec91f6e21e
Revises: ca8d7d9e9a09
Create Date: 2026-08-31
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "72ec91f6e21e"
down_revision: Union[str, Sequence[str], None] = "ca8d7d9e9a09"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Sync users table with the SQLAlchemy User model."""

    # Rename the existing database column to match the model.
    op.alter_column(
        "users",
        "password_hash",
        new_column_name="hashed_password",
        existing_type=sa.String(length=255),
        existing_nullable=False,
    )

    # Add the column expected by the User model.
    op.add_column(
        "users",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Reverse the users table changes."""

    op.drop_column("users", "updated_at")

    op.alter_column(
        "users",
        "hashed_password",
        new_column_name="password_hash",
        existing_type=sa.String(length=255),
        existing_nullable=False,
    )