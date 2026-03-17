"""create subscribers table

Revision ID: 0005_subscribers
Revises: 0004_search_doc
Create Date: 2026-03-16
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0005_subscribers"
down_revision: Union[str, Sequence[str], None] = "0004_search_doc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "subscribers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("confirmed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("confirm_token", sa.String(36), nullable=False),
        sa.Column("unsubscribe_token", sa.String(36), nullable=False),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_subscribers_email", "subscribers", ["email"], unique=True)
    op.create_index(
        "ix_subscribers_confirm_token", "subscribers", ["confirm_token"], unique=True
    )
    op.create_index(
        "ix_subscribers_unsubscribe_token",
        "subscribers",
        ["unsubscribe_token"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("subscribers")
