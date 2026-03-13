"""scrape_scheduler_mvp

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-13 00:00:00.000000

Adds:
- scrape_jobs table
- scrape_schedules table
- new columns for scrape_runs: job_id, trigger_type, attempt, queued_at,
  worker_id, checkpoint_in_json, checkpoint_out_json
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # scrape_jobs
    # ------------------------------------------------------------------
    op.create_table(
        "scrape_jobs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("source_key", sa.String(255), nullable=False),
        sa.Column("runner_type", sa.String(100), nullable=False),
        sa.Column("params_json", sa.JSON, nullable=True),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("priority", sa.Integer, nullable=False, server_default="0"),
        sa.Column("allow_overlap", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("timeout_sec", sa.Integer, nullable=True),
        sa.Column("max_retries", sa.Integer, nullable=False, server_default="0"),
        sa.Column("retry_backoff_sec", sa.Integer, nullable=False, server_default="60"),
        sa.Column("concurrency_key", sa.String(255), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ------------------------------------------------------------------
    # scrape_schedules
    # ------------------------------------------------------------------
    op.create_table(
        "scrape_schedules",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "job_id",
            sa.Integer,
            sa.ForeignKey("scrape_jobs.id", name="fk_scrape_schedules_job_id"),
            nullable=False,
        ),
        sa.Column("schedule_type", sa.String(50), nullable=False),
        sa.Column("cron_expr", sa.String(255), nullable=True),
        sa.Column("interval_sec", sa.Integer, nullable=True),
        sa.Column("timezone", sa.String(100), nullable=False, server_default="UTC"),
        sa.Column("jitter_sec", sa.Integer, nullable=False, server_default="0"),
        sa.Column("misfire_policy", sa.String(50), nullable=False, server_default="skip"),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ------------------------------------------------------------------
    # scrape_runs — add scheduler-oriented columns
    # render_as_batch is already set in env.py for SQLite
    # ------------------------------------------------------------------
    with op.batch_alter_table("scrape_runs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "job_id",
                sa.Integer,
                sa.ForeignKey("scrape_jobs.id", name="fk_scrape_runs_job_id"),
                nullable=True,
            )
        )
        batch_op.add_column(sa.Column("trigger_type", sa.String(50), nullable=True))
        batch_op.add_column(
            sa.Column("attempt", sa.Integer, nullable=False, server_default="1")
        )
        batch_op.add_column(
            sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(sa.Column("worker_id", sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("checkpoint_in_json", sa.JSON, nullable=True))
        batch_op.add_column(sa.Column("checkpoint_out_json", sa.JSON, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("scrape_runs") as batch_op:
        batch_op.drop_column("checkpoint_out_json")
        batch_op.drop_column("checkpoint_in_json")
        batch_op.drop_column("worker_id")
        batch_op.drop_column("queued_at")
        batch_op.drop_column("attempt")
        batch_op.drop_column("trigger_type")
        batch_op.drop_column("job_id")

    op.drop_table("scrape_schedules")
    op.drop_table("scrape_jobs")

