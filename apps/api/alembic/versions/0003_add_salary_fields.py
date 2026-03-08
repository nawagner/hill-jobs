"""add salary fields to jobs

Revision ID: 0003_salary
Revises: 0002_sync
Create Date: 2026-03-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_salary"
down_revision: Union[str, Sequence[str], None] = "0002_sync"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("salary_min", sa.Numeric(12, 2), nullable=True))
    op.add_column("jobs", sa.Column("salary_max", sa.Numeric(12, 2), nullable=True))
    op.add_column("jobs", sa.Column("salary_period", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "salary_period")
    op.drop_column("jobs", "salary_max")
    op.drop_column("jobs", "salary_min")
