"""add_retry_processed

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-03-14 00:00:00.000000

RFC-012 Commit 2 — Add ``retry_processed`` to ``scrape_runs``.

Semantic purpose:
  ``retry_processed`` is set by the scheduler once it has evaluated a source
  run for retry creation.  It prevents a second retry child from being
  generated for the same source run and replaces the dual-use overloading of
  ``retry_exhausted``.

  ``retry_exhausted`` is preserved and now strictly means "retry budget
  exhausted — no more retries allowed under policy".

Backfill logic:
  Existing rows where ``retry_exhausted=TRUE`` are backfilled with
  ``retry_processed=TRUE`` because they were already handled by the scheduler
  (either a retry child was created OR the budget was exhausted).
  All other rows receive ``retry_processed=FALSE`` (the default).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("scrape_runs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "retry_processed",
                sa.Boolean,
                nullable=False,
                server_default=sa.false(),
            )
        )
    # Backfill: rows already handled by the scheduler (retry_exhausted=TRUE)
    # are considered processed.
    # Note: use TRUE/FALSE literals — compatible with both SQLite and PostgreSQL.
    op.execute(
        text(
            "UPDATE scrape_runs SET retry_processed = TRUE WHERE retry_exhausted = TRUE"
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("scrape_runs") as batch_op:
        batch_op.drop_column("retry_processed")

