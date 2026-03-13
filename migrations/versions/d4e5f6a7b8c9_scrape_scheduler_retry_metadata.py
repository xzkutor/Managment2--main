"""scrape_scheduler_retry_metadata

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-03-13 00:00:00.000000

Adds retry persistence fields to scrape_runs:
  - retryable        BOOLEAN  NOT NULL DEFAULT FALSE
  - retry_of_run_id  INTEGER  FK -> scrape_runs.id  NULLABLE
  - retry_exhausted  BOOLEAN  NOT NULL DEFAULT FALSE
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("scrape_runs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "retryable",
                sa.Boolean,
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(
            sa.Column(
                "retry_of_run_id",
                sa.Integer,
                sa.ForeignKey("scrape_runs.id", name="fk_scrape_runs_retry_of_run_id"),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "retry_exhausted",
                sa.Boolean,
                nullable=False,
                server_default=sa.false(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("scrape_runs") as batch_op:
        batch_op.drop_column("retry_exhausted")
        batch_op.drop_column("retry_of_run_id")
        batch_op.drop_column("retryable")

