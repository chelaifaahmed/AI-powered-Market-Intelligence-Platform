# TEAMWILL Market Intelligence Platform — Claude Instructions

## Project identity
- Name: AI-Powered Automotive & Insurance Market Intelligence Platform
- Owner: Ahmed (PFE / Final Year Project)
- Company context: Built for TEAMWILL — Tunisian ERP/leasing systems vendor targeting car insurers and dealers in Tunisia + EU
- Stack: FastAPI + PostgreSQL + React/TypeScript/Vite/TailwindCSS
- Python env: .venv (always use .venv/Scripts/python.exe on Windows)
- API runs on port 8099 in dev
- Dashboard runs on port 5174 in dev (Vite proxy → 8099)

## Architecture (read before touching anything)
- database/models.py — 33 ORM models, DO NOT rename columns
- database/migrations/ — always run alembic upgrade head after model changes, always create migration for schema changes
- api/main.py — 25+ endpoints, follow existing patterns exactly
- analytics/opportunity_scorer.py — core business logic, signal_strength threshold is 65 (strong) / 40 (moderate)
- analytics/pdf_exporter.py — ReportLab PDF generation
- dashboard/src/ — React + TypeScript, strict mode, no 'any' types

## Coding standards
- Python: follow existing patterns in aggregators.py exactly
- TypeScript: strict, no any, match existing interface patterns
- New API endpoints: always add to api/main.py, follow existing response model pattern (Pydantic + ConfigDict)
- New DB models: add to database/models.py, create Alembic migration, never edit existing migration files
- New dashboard pages: follow Brands.tsx or Opportunities.tsx structure, use existing KpiCard/EmptyState/ErrorState components
- staleTime: 30000 on all React Query hooks (project standard)
- Always run: cd dashboard && npm run build after frontend changes

## Key decisions already made (do not revisit)
- Opportunity scorer uses NEGATIVE sentiment as complaint proxy (not complaint_type_id — that was too narrow, only 14% match)
- strong signal threshold = 65 (was 70, lowered to surface Hyundai 68.9 and AXA XL 66.0 as strong signals)
- TN companies score 33.0 because zero real reviews — this is intentional, visibility gap IS the signal
- Seeded data marked data_origin='seeded', scraped='scraped' — never mix them in analytics
- DM Sans font only on Opportunities and Analyst pages (brand continuity for premium pages)
- Vite proxy target: http://127.0.0.1:8099

## What's real vs seeded
- REAL scraped: 904 car reviews (Trustpilot), 83 listings (AutoScout24), 115 articles (RSS feeds)
- SEEDED: ~1,547 car reviews, all insurance reviews, all competitor pricing, all TN companies (no real reviews yet)

## Current migration chain (do not break)
350d9942b399 → add_analytics_tables → add_pipeline_step_runs → enrich_vehicle_and_article_fields → add_data_origin_provenance → analytics_provenance → b2c3d4e5f6a7 (add_region_field) → c4d5e6f7a8b9 (add_opportunity_signals) → a1b2c3d4e5f7 (add_review_partitions) ← current HEAD

## Environment
- OS: Windows 11
- Python: 3.11 in .venv
- Node: 20
- PostgreSQL: 14, local instance on port 5432
- All commands use Windows paths and .venv/Scripts/

## Never do these things
- Never delete or rename existing DB columns
- Never hardcode passwords or API keys
- Never use 'any' in TypeScript
- Never edit existing Alembic migration files
- Never run scrapers in parallel (rate limiting breaks)
- Never push debris files (test_*.py, *.log, alembic_err*) to git
