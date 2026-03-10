"""backfill search_document with org and location

Revision ID: 0004_search_doc
Revises: 0003_salary
Create Date: 2026-03-09
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0004_search_doc"
down_revision: Union[str, Sequence[str], None] = "0003_salary"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE jobs
        SET search_document = title
            || ' ' || coalesce(source_organization, '')
            || ' ' || coalesce(location_text, '')
            || ' ' || coalesce(description_text, '')
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE jobs
        SET search_document = title || ' ' || coalesce(description_text, '')
        """
    )
