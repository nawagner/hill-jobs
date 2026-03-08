"""create jobs table

Revision ID: 30541b8fa13c
Revises: 
Create Date: 2026-03-08 00:57:46.092730

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '30541b8fa13c'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("slug", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("source_organization", sa.String(255), nullable=False, index=True),
        sa.Column("source_system", sa.String(100), nullable=False),
        sa.Column("source_job_id", sa.String(255)),
        sa.Column("source_url", sa.String(2048), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="open", index=True),
        sa.Column("role_kind", sa.String(50), nullable=False, index=True),
        sa.Column("location_text", sa.String(255)),
        sa.Column("employment_type", sa.String(100)),
        sa.Column("description_html", sa.Text, nullable=False, server_default=""),
        sa.Column("description_text", sa.Text, nullable=False, server_default=""),
        sa.Column("posted_at", sa.DateTime(timezone=True)),
        sa.Column("closing_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("jobs")
