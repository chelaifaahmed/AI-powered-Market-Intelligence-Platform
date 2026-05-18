"""add_intervention_brief

Adds intervention_brief JSONB column to opportunity_signals.
This column caches the AI-generated sales intervention brief produced by
analytics/intervention_brief_generator.py (Groq LLaMA-3.3-70B).

New column on opportunity_signals:
  * intervention_brief  — JSONB, nullable. Contains keys:
      entry_strategy, positioning, outreach_tone, best_timing, avoid,
      pain_escalation_days, pain_escalation_label, confidence_note,
      suggested_entry_message.
    Set to {"error": "parse_failed", "raw": "..."} on generation failure.

Uses ADD COLUMN IF NOT EXISTS so the migration is safe to re-run.

Revision ID: f6g7h8i9j0k1
Revises:     e5f6g7h8i9j0
Create Date: 2026-05-15
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "f6g7h8i9j0k1"
down_revision: Union[str, None] = "e5f6g7h8i9j0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "opportunity_signals"


def upgrade() -> None:
    op.execute(
        f"ALTER TABLE {_TABLE} ADD COLUMN IF NOT EXISTS "
        "intervention_brief JSONB"
    )
    op.execute(
        f"CREATE INDEX IF NOT EXISTS idx_opp_brief_null "
        f"ON {_TABLE} ((intervention_brief IS NULL))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_opp_brief_null")
    op.execute(f"ALTER TABLE {_TABLE} DROP COLUMN IF EXISTS intervention_brief")
