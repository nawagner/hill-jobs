"""add sync fields and source_sync_runs table

Revision ID: 0002_sync
Revises: 30541b8fa13c
Create Date: 2026-03-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_sync"
down_revision: Union[str, Sequence[str], None] = "30541b8fa13c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns to jobs
    op.add_column("jobs", sa.Column("search_document", sa.Text, nullable=True))
    op.add_column("jobs", sa.Column("raw_payload", sa.JSON, nullable=True))
    op.add_column(
        "jobs", sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "jobs", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "jobs", sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True)
    )

    # Partial unique constraint on (source_system, source_job_id)
    op.create_index(
        "uq_jobs_source_identity",
        "jobs",
        ["source_system", "source_job_id"],
        unique=True,
        postgresql_where=sa.text("source_job_id IS NOT NULL"),
    )

    # GIN index for full-text search
    op.execute(
        "CREATE INDEX ix_jobs_search_document ON jobs "
        "USING GIN (to_tsvector('english', coalesce(search_document, '')))"
    )

    # Create source_sync_runs table
    op.create_table(
        "source_sync_runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("source_system", sa.String(100), nullable=False, index=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(50), nullable=False, server_default="running"),
        sa.Column("jobs_found", sa.Integer, nullable=False, server_default="0"),
        sa.Column("jobs_created", sa.Integer, nullable=False, server_default="0"),
        sa.Column("jobs_updated", sa.Integer, nullable=False, server_default="0"),
        sa.Column("jobs_closed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text),
    )


def downgrade() -> None:
    op.drop_table("source_sync_runs")
    op.execute("DROP INDEX IF EXISTS ix_jobs_search_document")
    op.drop_index("uq_jobs_source_identity", table_name="jobs")
    op.drop_column("jobs", "last_synced_at")
    op.drop_column("jobs", "last_seen_at")
    op.drop_column("jobs", "first_seen_at")
    op.drop_column("jobs", "raw_payload")
    op.drop_column("jobs", "search_document")
