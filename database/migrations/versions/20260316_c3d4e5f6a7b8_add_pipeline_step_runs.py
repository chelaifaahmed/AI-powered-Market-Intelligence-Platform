"""add_pipeline_step_runs

Revision ID: c3d4e5f6a7b8
Revises: a1b2c3d4e5f6
Create Date: 2026-03-16

Phase 10 — Operational Visibility.

Adds the pipeline_step_runs table: one row per pipeline stage per run,
capturing granular records_seen / processed / skipped / failed / inserted
counts, duration_ms, and a JSONB metadata payload.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM, JSONB

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Re-use the existing PostgreSQL enum (values are uppercase in the DB) — do NOT recreate it.
_pipeline_status = PG_ENUM(
    "RUNNING", "SUCCESS", "FAILED", "PARTIAL",
    name="pipeline_status",
    create_type=False,
)


def upgrade() -> None:
    op.create_table(
        "pipeline_step_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "pipeline_run_id", sa.UUID(), nullable=True,
            comment="Optional FK to parent pipeline_runs row.",
        ),
        sa.Column(
            "step_name", sa.String(100), nullable=False,
            comment="Stage identifier: 'parser', 'nlp_car_reviews', 'analytics', etc.",
        ),
        sa.Column(
            "status",
            _pipeline_status,
            nullable=False,
            server_default="RUNNING",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "duration_ms", sa.Integer(), nullable=True,
            comment="Wall-clock duration in milliseconds.",
        ),
        sa.Column("records_seen",      sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_skipped",   sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_failed",    sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_inserted",  sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count",       sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "step_metadata",
            JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Arbitrary extra context for this step.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("records_seen >= 0",      name="chk_step_seen"),
        sa.CheckConstraint("records_processed >= 0", name="chk_step_processed"),
        sa.CheckConstraint("records_skipped >= 0",   name="chk_step_skipped"),
        sa.CheckConstraint("records_failed >= 0",    name="chk_step_failed"),
        sa.CheckConstraint("records_inserted >= 0",  name="chk_step_inserted"),
        sa.CheckConstraint("error_count >= 0",       name="chk_step_errors"),
        sa.ForeignKeyConstraint(
            ["pipeline_run_id"], ["pipeline_runs.id"], ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="Per-stage operational metrics for parser / NLP / analytics runs.",
    )
    op.create_index("idx_step_name",       "pipeline_step_runs", ["step_name"])
    op.create_index("idx_step_status",     "pipeline_step_runs", ["status"])
    op.create_index("idx_step_created",    "pipeline_step_runs", ["created_at"])
    op.create_index("idx_step_pipeline",   "pipeline_step_runs", ["pipeline_run_id"])
    op.create_index(
        "idx_step_name_start", "pipeline_step_runs", ["step_name", "started_at"]
    )


def downgrade() -> None:
    op.drop_index("idx_step_name_start",  table_name="pipeline_step_runs")
    op.drop_index("idx_step_pipeline",    table_name="pipeline_step_runs")
    op.drop_index("idx_step_created",     table_name="pipeline_step_runs")
    op.drop_index("idx_step_status",      table_name="pipeline_step_runs")
    op.drop_index("idx_step_name",        table_name="pipeline_step_runs")
    op.drop_table("pipeline_step_runs")
