"""v2_opportunity_radar — 6 new tables for the Opportunity Radar scorer

Adds:
  * teamwill_competitors           (catalog of 45 competitors with full profile)
  * teamwill_erp_solutions         (catalog of 32 ERPs with full fit scores)
  * teamwill_profile               (single-row TEAMWILL ICP reference)
  * company_profile                (revenue / employees / HQ / ownership per tracked company)
  * company_action_signals         (leadership changes, digital initiatives, M&A — per company)
  * company_tech_stack             (detected ERP deployments — per company, with provenance)

All tables follow project conventions:
  * UUID primary keys via gen_random_uuid()
  * created_at / updated_at timestamps with timezone
  * JSONB columns for flexible / array-like data
  * source_url + scraped_at on every scraped record for provenance
  * data_origin enum-style varchar for seeded vs scraped vs imported

Revises: a2b3c4d5e6f7  (rag_embeddings)
Revision ID: b3c4d5e6f7g8
Created: 2026-05-13

Run with:
    alembic upgrade head

Rollback with:
    alembic downgrade -1
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "b3c4d5e6f7g8"
down_revision = "a2b3c4d5e6f7"  # <- chain after the last migration (rag_embeddings)
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------------------------------------------------------------
    # 1. teamwill_competitors — full competitor catalog
    # ---------------------------------------------------------------
    op.create_table(
        "teamwill_competitors",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  server_default=sa.text("gen_random_uuid()"),
                  primary_key=True),
        sa.Column("company_name", sa.String(255), nullable=False, unique=True),
        sa.Column("headquarters_country", sa.String(100)),
        sa.Column("headquarters_city", sa.String(100)),
        sa.Column("founded_year", sa.SmallInteger),
        sa.Column("employee_count_range", sa.String(50)),
        sa.Column("estimated_revenue_usd_millions", sa.Numeric(12, 2)),
        sa.Column("revenue_year", sa.SmallInteger),
        sa.Column("geographic_presence", postgresql.JSONB),  # array of regions
        sa.Column("countries_count", sa.String(20)),         # "150+" needs string
        sa.Column("primary_services", postgresql.JSONB),     # array
        sa.Column("key_industries", postgresql.JSONB),       # array
        sa.Column("erp_partnerships", postgresql.JSONB),     # array
        sa.Column("competitor_tier", sa.String(30), nullable=False),
        sa.Column("overlap_with_teamwill_score", sa.SmallInteger),
        sa.Column("overlap_rationale", sa.Text),
        sa.Column("website_url", sa.Text),
        sa.Column("linkedin_followers_approx", sa.BigInteger),
        sa.Column("recent_news_headline", sa.Text),
        sa.Column("publicly_traded", sa.Boolean),
        sa.Column("stock_ticker", sa.String(30)),
        sa.Column("data_origin", sa.String(20), nullable=False, server_default="imported"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_competitors_tier", "teamwill_competitors", ["competitor_tier"])
    op.create_index("idx_competitors_overlap", "teamwill_competitors",
                    ["overlap_with_teamwill_score"])

    # ---------------------------------------------------------------
    # 2. teamwill_erp_solutions — full ERP catalog
    # ---------------------------------------------------------------
    op.create_table(
        "teamwill_erp_solutions",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  server_default=sa.text("gen_random_uuid()"),
                  primary_key=True),
        sa.Column("erp_name", sa.String(255), nullable=False, unique=True),
        sa.Column("vendor", sa.String(255), nullable=False),
        sa.Column("vendor_country", sa.String(100)),
        sa.Column("founded_or_launched_year", sa.SmallInteger),
        sa.Column("deployment_model", sa.String(100)),
        sa.Column("target_company_size", sa.String(100)),
        sa.Column("global_market_share_percent", sa.String(50)),  # "18-20"
        sa.Column("estimated_active_customers", sa.Integer),
        sa.Column("pricing_model", sa.String(100)),
        sa.Column("starting_price_usd_per_user_per_month", sa.String(50)),
        sa.Column("key_modules", postgresql.JSONB),
        sa.Column("industries_strong_in", postgresql.JSONB),
        sa.Column("automotive_fit_score", sa.SmallInteger),
        sa.Column("insurance_fit_score", sa.SmallInteger),
        sa.Column("g2_rating", sa.Numeric(3, 2)),
        sa.Column("g2_review_count", sa.Integer),
        sa.Column("gartner_peer_insights_rating", sa.Numeric(3, 2)),
        sa.Column("capterra_rating", sa.Numeric(3, 2)),
        sa.Column("trustradius_rating", sa.Numeric(3, 2)),
        sa.Column("average_rating_normalized", sa.Numeric(3, 2)),
        sa.Column("total_reviews_aggregate", sa.Integer),
        sa.Column("top_pros", sa.Text),
        sa.Column("top_cons", sa.Text),
        sa.Column("typical_implementation_months", sa.String(50)),
        sa.Column("notable_customers", postgresql.JSONB),  # array — CRITICAL for lock-in detection
        sa.Column("mena_africa_adoption", sa.String(30)),
        sa.Column("teamwill_relevance_score", sa.SmallInteger),
        sa.Column("data_origin", sa.String(20), nullable=False, server_default="imported"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_erp_relevance", "teamwill_erp_solutions",
                    ["teamwill_relevance_score"])
    op.create_index("idx_erp_automotive_fit", "teamwill_erp_solutions",
                    ["automotive_fit_score"])
    op.create_index("idx_erp_insurance_fit", "teamwill_erp_solutions",
                    ["insurance_fit_score"])

    # ---------------------------------------------------------------
    # 3. teamwill_profile — single-row reference for the ICP
    # ---------------------------------------------------------------
    op.create_table(
        "teamwill_profile",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  server_default=sa.text("gen_random_uuid()"),
                  primary_key=True),
        sa.Column("company_name", sa.String(255), nullable=False, server_default="TEAMWILL"),
        sa.Column("headquarters_country", sa.String(100)),
        sa.Column("estimated_revenue_eur_millions", sa.Numeric(12, 2)),
        sa.Column("employee_count", sa.Integer),
        sa.Column("countries_present", postgresql.JSONB),       # array of 11 countries
        sa.Column("specializations", postgresql.JSONB),         # array
        sa.Column("ideal_client_industries", postgresql.JSONB), # array
        sa.Column("ideal_client_size_min_employees", sa.Integer),
        sa.Column("ideal_client_size_max_employees", sa.Integer),
        sa.Column("certified_erp_partnerships", postgresql.JSONB),  # ["Sofico Miles", "Alpha", ...]
        sa.Column("service_offerings", postgresql.JSONB),
        sa.Column("differentiators", sa.Text),
        sa.Column("known_clients", postgresql.JSONB),
        sa.Column("primary_competitors", postgresql.JSONB),
        sa.Column("source_urls", postgresql.JSONB),  # provenance
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )

    # ---------------------------------------------------------------
    # 4. company_profile — reachability data for each of the 76 companies
    # ---------------------------------------------------------------
    op.create_table(
        "company_profile",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  server_default=sa.text("gen_random_uuid()"),
                  primary_key=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(20), nullable=False),  # 'brand' or 'insurance'
        sa.Column("entity_name", sa.String(255), nullable=False),
        sa.Column("revenue_usd_millions", sa.Numeric(12, 2)),
        sa.Column("revenue_year", sa.SmallInteger),
        sa.Column("employee_count", sa.Integer),
        sa.Column("employee_count_range", sa.String(50)),
        sa.Column("headquarters_country", sa.String(100)),
        sa.Column("headquarters_city", sa.String(100)),
        sa.Column("active_countries", postgresql.JSONB),     # array
        sa.Column("ownership_type", sa.String(50)),           # public / private / PE-owned / state-owned
        sa.Column("parent_company", sa.String(255)),
        sa.Column("stock_ticker", sa.String(30)),
        sa.Column("sub_segment", sa.String(100)),             # P&C / Life / Multiline / Captive / Lessor / OEM
        sa.Column("website", sa.Text),
        sa.Column("source_urls", postgresql.JSONB, nullable=False),  # array — provenance is mandatory
        sa.Column("confidence", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("data_origin", sa.String(20), nullable=False, server_default="scraped"),
        sa.Column("scraped_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("entity_id", "entity_type", name="uq_company_profile_entity"),
    )
    op.create_index("idx_company_profile_entity", "company_profile",
                    ["entity_id", "entity_type"])
    op.create_index("idx_company_profile_country", "company_profile", ["headquarters_country"])

    # ---------------------------------------------------------------
    # 5. company_action_signals — recovery axis raw data
    # ---------------------------------------------------------------
    op.create_table(
        "company_action_signals",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  server_default=sa.text("gen_random_uuid()"),
                  primary_key=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(20), nullable=False),
        sa.Column("entity_name", sa.String(255), nullable=False),
        sa.Column("signal_type", sa.String(50), nullable=False),
        sa.Column("signal_date", sa.Date, nullable=False),
        sa.Column("headline", sa.Text, nullable=False),
        sa.Column("summary", sa.Text),
        sa.Column("polarity", sa.String(20)),
        sa.Column("source_url", sa.Text, nullable=False),
        sa.Column("source_name", sa.String(255)),
        sa.Column("confidence", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("raw_extract", postgresql.JSONB),
        sa.Column("scraped_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_action_entity", "company_action_signals",
                    ["entity_id", "entity_type"])
    op.create_index("idx_action_type", "company_action_signals", ["signal_type"])
    op.create_index("idx_action_date", "company_action_signals", ["signal_date"])

    # ---------------------------------------------------------------
    # 6. company_tech_stack — detected ERP deployments (reachability axis)
    # ---------------------------------------------------------------
    op.create_table(
        "company_tech_stack",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  server_default=sa.text("gen_random_uuid()"),
                  primary_key=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(20), nullable=False),
        sa.Column("entity_name", sa.String(255), nullable=False),
        sa.Column("vendor", sa.String(255), nullable=False),
        sa.Column("product", sa.String(255)),
        sa.Column("evidence_type", sa.String(50), nullable=False),
        sa.Column("evidence_excerpt", sa.Text),
        sa.Column("source_url", sa.Text, nullable=False),
        sa.Column("source_name", sa.String(255)),
        sa.Column("confidence", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("detected_date", sa.Date),
        sa.Column("still_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("scraped_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_tech_stack_entity", "company_tech_stack",
                    ["entity_id", "entity_type"])
    op.create_index("idx_tech_stack_vendor", "company_tech_stack", ["vendor"])


def downgrade() -> None:
    op.drop_index("idx_tech_stack_vendor", table_name="company_tech_stack")
    op.drop_index("idx_tech_stack_entity", table_name="company_tech_stack")
    op.drop_table("company_tech_stack")

    op.drop_index("idx_action_date", table_name="company_action_signals")
    op.drop_index("idx_action_type", table_name="company_action_signals")
    op.drop_index("idx_action_entity", table_name="company_action_signals")
    op.drop_table("company_action_signals")

    op.drop_index("idx_company_profile_country", table_name="company_profile")
    op.drop_index("idx_company_profile_entity", table_name="company_profile")
    op.drop_table("company_profile")

    op.drop_table("teamwill_profile")

    op.drop_index("idx_erp_insurance_fit", table_name="teamwill_erp_solutions")
    op.drop_index("idx_erp_automotive_fit", table_name="teamwill_erp_solutions")
    op.drop_index("idx_erp_relevance", table_name="teamwill_erp_solutions")
    op.drop_table("teamwill_erp_solutions")

    op.drop_index("idx_competitors_overlap", table_name="teamwill_competitors")
    op.drop_index("idx_competitors_tier", table_name="teamwill_competitors")
    op.drop_table("teamwill_competitors")
