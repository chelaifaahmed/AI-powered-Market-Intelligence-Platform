"""company_intelligence_columns

Adds company-state and CEO intelligence columns to opportunity_signals,
enabling the scorer to record real-time hiring signals, leadership context,
and recommended outreach timing alongside the V2 axis scores.

New columns on opportunity_signals:
  * company_state          — lifecycle phase (e.g. 'growth', 'restructuring', 'stable')
  * ceo_name               — current CEO full name
  * ceo_appointment_date   — date the current CEO took the role
  * is_hiring_aggressively — TRUE when open-role count is above sector threshold
  * open_roles_estimate    — latest scraped open-position count
  * key_hiring_roles       — comma-separated list of role titles signalling ERP spend
  * intervention_level     — recommended TEAMWILL engagement depth ('light'/'medium'/'heavy')
  * outreach_timing        — recommended outreach window ('now'/'3m'/'6m'/'hold')
  * intelligence_updated_at — timestamp of the last intelligence refresh for this row

Uses ADD COLUMN IF NOT EXISTS so the migration is safe to re-run against a
database where the columns already exist (e.g. applied manually in dev).

Revision ID: e5f6g7h8i9j0
Revises:     d6e7f8g9h0i1
Create Date: 2026-05-15
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "e5f6g7h8i9j0"
down_revision: Union[str, None] = "d6e7f8g9h0i1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "opportunity_signals"


def upgrade() -> None:
    # ADD COLUMN IF NOT EXISTS is idempotent on PostgreSQL 9.6+.
    # Using op.execute() mirrors the pattern already used in this project
    # for DDL that needs IF NOT EXISTS semantics.

    # ── Company-state & leadership context ────────────────────────────────────
    op.execute(
        f"ALTER TABLE {_TABLE} ADD COLUMN IF NOT EXISTS "
        "company_state VARCHAR(50)"
    )
    op.execute(
        f"ALTER TABLE {_TABLE} ADD COLUMN IF NOT EXISTS "
        "ceo_name VARCHAR(200)"
    )
    op.execute(
        f"ALTER TABLE {_TABLE} ADD COLUMN IF NOT EXISTS "
        "ceo_appointment_date DATE"
    )

    # ── Hiring signals ─────────────────────────────────────────────────────────
    op.execute(
        f"ALTER TABLE {_TABLE} ADD COLUMN IF NOT EXISTS "
        "is_hiring_aggressively BOOLEAN DEFAULT FALSE"
    )
    op.execute(
        f"ALTER TABLE {_TABLE} ADD COLUMN IF NOT EXISTS "
        "open_roles_estimate INTEGER"
    )
    op.execute(
        f"ALTER TABLE {_TABLE} ADD COLUMN IF NOT EXISTS "
        "key_hiring_roles TEXT"
    )

    # ── Outreach recommendations ───────────────────────────────────────────────
    op.execute(
        f"ALTER TABLE {_TABLE} ADD COLUMN IF NOT EXISTS "
        "intervention_level VARCHAR(50)"
    )
    op.execute(
        f"ALTER TABLE {_TABLE} ADD COLUMN IF NOT EXISTS "
        "outreach_timing VARCHAR(40)"
    )

    # ── Freshness tracking ─────────────────────────────────────────────────────
    op.execute(
        f"ALTER TABLE {_TABLE} ADD COLUMN IF NOT EXISTS "
        "intelligence_updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()"
    )

    # ── Indexes (IF NOT EXISTS is standard in PostgreSQL 9.5+) ─────────────────
    op.execute(
        f"CREATE INDEX IF NOT EXISTS idx_opp_company_state "
        f"ON {_TABLE} (company_state)"
    )
    op.execute(
        f"CREATE INDEX IF NOT EXISTS idx_opp_intervention_level "
        f"ON {_TABLE} (intervention_level)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_opp_intervention_level")
    op.execute("DROP INDEX IF EXISTS idx_opp_company_state")
    op.execute(f"ALTER TABLE {_TABLE} DROP COLUMN IF EXISTS intelligence_updated_at")
    op.execute(f"ALTER TABLE {_TABLE} DROP COLUMN IF EXISTS outreach_timing")
    op.execute(f"ALTER TABLE {_TABLE} DROP COLUMN IF EXISTS intervention_level")
    op.execute(f"ALTER TABLE {_TABLE} DROP COLUMN IF EXISTS key_hiring_roles")
    op.execute(f"ALTER TABLE {_TABLE} DROP COLUMN IF EXISTS open_roles_estimate")
    op.execute(f"ALTER TABLE {_TABLE} DROP COLUMN IF EXISTS is_hiring_aggressively")
    op.execute(f"ALTER TABLE {_TABLE} DROP COLUMN IF EXISTS ceo_appointment_date")
    op.execute(f"ALTER TABLE {_TABLE} DROP COLUMN IF EXISTS ceo_name")
    op.execute(f"ALTER TABLE {_TABLE} DROP COLUMN IF EXISTS company_state")
