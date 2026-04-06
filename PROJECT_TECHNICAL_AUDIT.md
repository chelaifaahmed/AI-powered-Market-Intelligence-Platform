# Project Technical Audit — Automotive Intelligence Platform

**Date:** 2026-03-21
**Auditor scope:** Full codebase scan — architecture, dependencies, state, SWOT
**Branch:** Ahmed (2 commits)

---

## Table of Contents

1. [Project Identity](#1-project-identity)
2. [Architecture Overview](#2-architecture-overview)
3. [Codebase Metrics](#3-codebase-metrics)
4. [Backend Deep Dive](#4-backend-deep-dive)
5. [Frontend Deep Dive](#5-frontend-deep-dive)
6. [Database & Schema](#6-database--schema)
7. [Dependency Inventory](#7-dependency-inventory)
8. [Test Suite](#8-test-suite)
9. [Current State Assessment](#9-current-state-assessment)
10. [Difficulties & Technical Debt](#10-difficulties--technical-debt)
11. [SWOT Analysis](#11-swot-analysis)
12. [File Inventory](#12-file-inventory)

---

## 1. Project Identity

**Name:** AI-Powered Automotive & Car Insurance Market Intelligence Platform
**Type:** End-to-end data pipeline + analytics dashboard (PFE / Final Year Project)
**Domain:** Automotive reviews, insurance reviews, marketplace listings, market news, competitor pricing

**What it does in one paragraph:**
Scrapes automotive review websites (Trustpilot, AutoScout24, RSS feeds), parses raw HTML into structured records, runs NLP sentiment analysis (DistilBERT transformer), computes brand reputation analytics, and exposes everything through a FastAPI REST API consumed by a React/TypeScript dashboard. Tracks data provenance (seeded vs scraped) and pipeline health throughout.

---

## 2. Architecture Overview

```
                        +-----------------------+
                        |   React Dashboard     |
                        |  (Vite + TailwindCSS) |
                        +---------+-------------+
                                  |
                           HTTP / JSON
                                  |
                        +---------v-------------+
                        |   FastAPI REST API     |
                        |   (25+ endpoints)      |
                        +---------+-------------+
                                  |
                     SQLAlchemy ORM (sync + async)
                                  |
                        +---------v-------------+
                        |   PostgreSQL 14+       |
                        |   (33 tables, ENUMs,   |
                        |    JSONB, ARRAY, UUID)  |
                        +---------+-------------+
                                  ^
                                  |
            +---------------------+---------------------+
            |                     |                     |
   +--------v-------+   +--------v-------+   +---------v------+
   |   Scrapers      |   |   Parsers      |   |   Analytics    |
   | (requests +     |   | (DOM, Schema,  |   | (aggregators)  |
   |  Playwright)    |   |  LLM, Dedup)   |   +----------------+
   +--------+-------+   +--------+-------+
            |                     |
            v                     v
   +--------+-------+   +--------+-------+
   |   Raw Pages     |   |   NLP Pipeline  |
   |   (HTML store)  |   | (DistilBERT +   |
   +----------------+   |  rule-based)     |
                        +----------------+
```

### Pipeline Flow (sequential, orchestrated by `scheduler.py`)

```
1. SCRAPE   →  Raw HTML stored in `raw_pages` table
2. PARSE    →  HTML → clean → DOM extract → schema extract → [LLM fallback]
              → normalize → validate → deduplicate → store domain record
3. NLP      →  Sentiment (transformer) + Topics + Keywords + Complaints
              → NLP result tables (per review/article)
4. ANALYTICS → Brand reputation scores + sentiment trends
              → 3 passes: all / scraped / seeded
5. SERVE    →  FastAPI exposes everything → Dashboard renders
```

### Architectural Pattern

- **Layered monolith** — not microservices, but cleanly separated modules
- **Pipeline architecture** — each stage reads from DB, writes to DB
- **Shared database** — PostgreSQL is the integration point for all modules
- **No message queue** — stages are orchestrated sequentially by scripts
- **No caching layer** — React Query (30s staleTime) is the only cache
- **No authentication** — API is open (assumes internal/local network)

---

## 3. Codebase Metrics

| Metric                     | Count        |
|---------------------------|-------------|
| **Total lines of code**    | ~31,185     |
| Python (backend)           | ~15,783     |
| TypeScript/TSX (frontend)  | ~3,216      |
| CSS                        | ~118        |
| Config/other               | ~1,400      |
| Test code                  | ~1,803      |
| Markdown (docs/reports)    | ~600        |
| Temporary/debug files      | ~8,000+     |
| **Python source files**    | 52          |
| **Frontend source files**  | 17          |
| **Test files**             | 9           |
| **ORM models**             | 33          |
| **API endpoints**          | 25+         |
| **Dashboard pages**        | 6           |
| **Alembic migrations**     | 6           |
| **Scraper classes**        | 9           |

---

## 4. Backend Deep Dive

### 4.1 Scrapers (`scrapers/` — 9 files, ~1,100 lines)

**Architecture:** Two-tier inheritance

```
BaseScraper (requests-based)
  ├── CarListingScraper      (AutoScout24)
  ├── CarReviewScraper       (CarAndDriver, MotorTrend)
  ├── InsuranceReviewScraper (insurance portals)
  ├── MarketNewsScraper      (Reuters, Bloomberg)
  ├── CompetitorPricingScraper
  ├── EdmundsScraper
  ├── ReutersScraper
  └── CarAndDriverScraper

PlaywrightBaseScraper (Chromium-based)
  └── TrustpilotScraper      (insurance reviews)
```

**Infrastructure:**
- `HttpClient` — requests.Session + urllib3 retry + connection pooling (10 conn, max 20)
- `RateLimiter` — thread-safe token bucket (configurable req/s)
- `RetryHandler` — decorator with exponential backoff + jitter
- `UserAgents` — rotating desktop User-Agent strings
- Anti-detection: webdriver property suppression, viewport, locale spoofing

**Key design:** Scrapers only fetch + store raw HTML. Structured extraction is delegated to the parser pipeline. The `parse()` methods on scrapers are deprecated but still present.

### 4.2 Parsers (`parsers/` — 8 files, ~1,100 lines)

**Multi-stage pipeline** orchestrated by `ParserPipeline`:

| Stage | Module | What it does |
|-------|--------|-------------|
| 1 | `html_cleaner.py` | Boilerplate removal via trafilatura + BeautifulSoup fallback |
| 2 | `dom_extractor.py` | CSS selector chains for brand, model, rating, price, author, date |
| 3 | `schema_extractor.py` | JSON-LD `<script type="application/ld+json">` parsing |
| 4 | `llm_extractor.py` | Google Gemini fallback for ambiguous pages (optional) |
| 5 | `normalizer.py` | Field canonicalization (text, rating 0-5, dates) |
| 6 | `validator.py` | Quality gate — URL required, title required, body >= 50 chars |
| 7 | `deduplicator.py` | URL match → content hash → title similarity (95%) |

**Entity routing:** URL hostname + title keywords → entity_type → correct ORM table

### 4.3 NLP (`nlp/` — 6 files, ~560 lines)

| Component | Implementation | Status |
|-----------|---------------|--------|
| **Sentiment** | DistilBERT SST-2 (HuggingFace transformers) | Real transformer |
| Sentiment fallback | Keyword-weighted scoring | Real rule-based |
| **Topics** | Keyword matching against 6 predefined categories | Rule-based |
| **Keywords** | TF-IDF-like unigram/bigram extraction | Rule-based |
| **Complaints** | Keyword matching against 5 complaint categories | Rule-based |
| **Text preprocessing** | Tokenize, stopword removal, cleaning | Rule-based |

**Model versioning:** `distilbert-sst2-v1` (transformer) or `rule-nlp-v1` (fallback). Version stamped on every NLP result row.

**Neutral threshold:** Confidence < 0.65 on the transformer → classified as "neutral" instead of positive/negative.

### 4.4 Analytics (`analytics/` — 1 file, ~274 lines)

Single module `aggregators.py`:
- Joins CarBrand → CarModel → CarReview → CarReviewNlp
- Groups by (brand_id, month)
- Computes: avg_rating, avg_sentiment_score, review_count, positive/neutral/negative counts
- **Provenance-aware:** 3 passes (all / scraped / seeded)
- Upserts into `brand_reputation_scores` + `sentiment_trends`

### 4.5 API (`api/main.py` — ~1,350 lines)

**Framework:** FastAPI with CORS middleware (all origins allowed)

**Endpoints by category:**

| Category | Endpoints | Description |
|----------|----------|-------------|
| Health | `GET /`, `GET /health` | Redirect to docs, DB connectivity probe |
| Brands | 4 endpoints | List, models, reputation, sentiment |
| Reviews | 2 endpoints | Car reviews, insurance reviews (paginated) |
| Listings | 3 endpoints | List, breakdown, summary |
| Articles | 2 endpoints | List (paginated), categories |
| Models | 1 endpoint | Car models with filters |
| Competitors | 2 endpoints | Pricing list, summary |
| Pipeline | 5 endpoints | Runs, status, detail, quality, failures |
| Sources | 1 endpoint | Scraper health |
| Dashboard | 1 endpoint | One-shot summary |
| Provenance | 1 endpoint | Seeded vs scraped counts |
| Summary | 2 endpoints | Brands summary, listings summary |

**Response pattern:** Pydantic response models with `ConfigDict(from_attributes=True)` for ORM compatibility.

**Known issue:** Sync DB queries inside async FastAPI handlers (uses threadpool context switches — works but suboptimal).

### 4.6 Observability (`observability/` — 1 file, ~214 lines)

`StepRecorder` — records `PipelineStepRun` rows:
- Context manager pattern (`with record_step(session, "parser")`)
- Auto-calculates duration, status (SUCCESS/FAILED/PARTIAL)
- Stores metadata as JSONB

### 4.7 Scripts (`scripts/` — 11 files, ~1,500 lines)

| Script | Purpose |
|--------|---------|
| `scheduler.py` | Master orchestrator: scrape → parse → NLP → analytics (loop or once) |
| `run_scrapers.py` | Execute all scraper classes |
| `run_scraping_tasks.py` | Execute ScrapingTask queue |
| `run_parser_pipeline.py` | Parse unparsed raw_pages |
| `run_nlp_pipeline.py` | Process unprocessed reviews/articles |
| `run_analytics.py` | Compute brand reputation |
| `run_rss_ingest.py` | RSS feed ingestion for market articles |
| `run_listings_ingest.py` | AutoScout24 listing ingestion |
| `run_reviews_ingest.py` | Trustpilot review ingestion (Playwright) |
| `seed_realistic_data.py` | Generate synthetic test data |
| `seed_enriched_data.py` | Generate enriched synthetic data |

---

## 5. Frontend Deep Dive

### 5.1 Stack

| Library | Version | Role |
|---------|---------|------|
| React | 18.3.1 | UI framework |
| TypeScript | 5.5.3 | Type safety |
| Vite | 5.4.1 | Build tool + dev server |
| TailwindCSS | 3.4.10 | Utility-first CSS |
| TanStack React Query | 5.51.23 | Server state management |
| Recharts | 2.12.7 | Charts (bar, area, stacked bar) |
| react-router-dom | 6.26.1 | Hash-based routing |
| lucide-react | 0.435.0 | Icon library |
| date-fns | 3.6.0 | Date formatting |
| clsx | 2.1.1 | Conditional CSS classes |

### 5.2 Design System

- **Primary color:** Indigo (#6366f1)
- **Font:** Inter (Google Fonts, weights 300-700)
- **Layout:** Fixed sidebar (240px dark slate) + scrollable main content
- **Component classes:** `.card`, `.badge-*`, `.btn-primary`, `.kpi-label`, `.table-th/td/tr`
- **Shadows:** 3-tier (card, card-hover, card-lg)
- **Responsive:** sm → md → lg → xl breakpoints

### 5.3 Pages

| Page | Lines | Features |
|------|-------|----------|
| **Overview** | 461 | KPI cards (6), provenance banner, brand leaderboard, review sources chart, pipeline steps, scraper health, recent failures |
| **Brands** | 445 | Origin toggle (Live/All/Seeded), brand selector, reputation trend (area chart), sentiment distribution (stacked bar), sentiment score trend |
| **Operations** | 482 | Quality KPIs, rejection chart, expandable pipeline runs table, failure log with pagination + source filter |
| **Articles** | 293 | Grid/list toggle, origin filter, article cards with source domain badges, pagination |
| **Listings** | 275 | Origin filter, brand search, KPI cards, sortable table, pagination |
| **Pricing** | 244 | Coverage type chart, region/coverage filter dropdowns, pricing table |

### 5.4 Shared Components (7)

| Component | Role |
|-----------|------|
| `Layout` | Sidebar + topbar + page routing |
| `KpiCard` | Metric card with icon, trend indicator, skeleton |
| `StatusBadge` | Color-coded status indicator |
| `Pagination` | Offset-based page controls |
| `Skeleton` / `SkeletonTable` / `SkeletonChart` / `SkeletonCard` | Loading placeholders |
| `EmptyState` | No-data placeholder |
| `ErrorState` | Error display with retry |

### 5.5 API Client (`client.ts`)

- 20+ TypeScript interfaces for full type safety
- Generic `get<T>()` function with query param support
- Vite proxy: `/api` → `http://localhost:8000`
- Base URL: empty (relative paths)

---

## 6. Database & Schema

### Engine: PostgreSQL 14+

**Features used:** UUID primary keys, JSONB columns, ARRAY columns, native ENUMs, CHECK constraints, partial indexes, `func.now()` server defaults.

### 33 ORM Models (9 groups)

| Group | Models | Tables |
|-------|--------|--------|
| **Scraping infrastructure** | ScrapingTask, ScrapingRun, ScrapingError, ScraperHealthMetric, PipelineRun, PipelineStepRun | 6 |
| **Raw data storage** | RawPage, RawApiResponse, RawScrapeLog | 3 |
| **Automotive domain** | ReviewSource, CarBrand, CarModel, CarListing, CarPriceHistory, CarReview, ComplaintType | 7 |
| **Insurance domain** | InsuranceCompany, InsurancePolicy, InsuranceQuoteHistory, CompetitorPricing | 4 |
| **Feedback/quality** | InsuranceReview, DataQualityLog | 2 |
| **NLP results** | Topic, CarReviewNlp, InsuranceReviewNlp, ArticleNlpResult | 4 |
| **Keywords** | Keyword, ReviewKeyword | 2 |
| **Market intelligence** | MarketTrendArticle | 1 |
| **Analytics/KPIs** | KpiMetric, BrandReputationScore, SentimentTrend | 3 |

### 15 PostgreSQL ENUMs

TaskStatus, RunStatus, ScrapeLogStatus, PipelineStatus, ListingCondition, PriceType, EngineType, CoverageType, SentimentLabel, EntityDomain, ReviewType, SourceType, KpiGranularity + 2 implicit

### Migration Chain (6 migrations)

```
initial_schema (20260307)
  └── add_analytics_tables (20260316)
      └── add_pipeline_step_runs (20260316)
          └── enrich_vehicle_and_article_fields (20260316)
              └── add_data_origin_provenance (20260318)
                  └── analytics_provenance (20260319)
```

### Hardening

- Indexes on all FK columns + analytics/partition columns
- CHECK constraints on numeric ranges (records_seen >= 0, rating range, etc.)
- UNIQUE constraints with multi-column dedup keys
- `lazy='selectin'` on high-volume relationships
- `TimestampMixin` (created_at, updated_at) on most tables
- `SoftDeleteMixin` (deleted_at) on domain entities

---

## 7. Dependency Inventory

### Python (from `requirements.txt` + implicit)

| Package | Version | Role | In requirements.txt? |
|---------|---------|------|---------------------|
| sqlalchemy | >= 2.0 | ORM | Yes |
| psycopg2-binary | >= 2.9 | PostgreSQL driver (sync) | Yes |
| alembic | >= 1.13 | Database migrations | Yes |
| beautifulsoup4 | >= 4.12 | HTML parsing | Yes |
| trafilatura | >= 1.8 | Article text extraction | Yes |
| lxml | >= 5.0 | XML/HTML parser backend | Yes |
| python-dateutil | >= 2.9 | Date parsing | Yes |
| transformers | >= 4.35.0 | HuggingFace NLP models | Yes |
| torch | >= 2.0.0 | PyTorch (transformer backend) | Yes |
| google-generativeai | >= 0.5 | Gemini LLM (optional) | Yes |
| aiofiles | >= 23.0 | Async file I/O | Yes |
| **fastapi** | — | REST API framework | **Missing** |
| **uvicorn** | — | ASGI server | **Missing** |
| **playwright** | — | Browser automation | **Missing** |
| **requests** | — | HTTP client | **Missing** |
| **httpx** | — | Async HTTP (FastAPI test) | **Missing** |
| **pytest** | — | Test framework | **Missing** |
| **asyncpg** | — | Async PostgreSQL driver | **Missing** |
| **feedparser** | — | RSS feed parsing | **Missing** |
| **pydantic** | — | Data validation (via FastAPI) | **Missing** |

### Frontend (from `package.json`)

| Package | Version | Role |
|---------|---------|------|
| react | 18.3.1 | UI framework |
| react-dom | 18.3.1 | DOM renderer |
| react-router-dom | 6.26.1 | Routing |
| @tanstack/react-query | 5.51.23 | Server state |
| recharts | 2.12.7 | Charts |
| lucide-react | 0.435.0 | Icons |
| date-fns | 3.6.0 | Date utilities |
| clsx | 2.1.1 | CSS utilities |
| typescript | 5.5.3 | Type checking |
| vite | 5.4.1 | Build tool |
| tailwindcss | 3.4.10 | CSS framework |
| postcss | 8.4.40 | CSS processing |
| autoprefixer | 10.4.20 | CSS vendor prefixes |

---

## 8. Test Suite

### Overview

| Metric | Value |
|--------|-------|
| Test files | 9 |
| Total tests | 180 |
| Passing | 179 |
| Failing | 1 (expected — transformer loaded where test assumes fallback) |
| Lines of test code | 1,803 |
| Execution time | ~13s |
| Framework | pytest |

### Coverage by Module

| Test File | Tests | What it covers |
|-----------|-------|----------------|
| `test_validator.py` | ~20 | Validation rules, edge cases |
| `test_normalizer.py` | ~15 | Field normalization (text, rating, dates) |
| `test_schema_extractor.py` | ~15 | JSON-LD parsing |
| `test_deduplicator.py` | ~15 | URL, hash, and similarity dedup |
| `test_sentiment_analyzer.py` | ~20 | Transformer + rule-based sentiment |
| `test_nlp_pipeline.py` | ~25 | Full NLP pipeline orchestration |
| `test_parser_pipeline.py` | ~30 | End-to-end parsing |
| `test_observability.py` | ~20 | StepRecorder, context managers |
| `test_api_operational.py` | ~20 | API endpoint integration tests |

### What's NOT Tested

- Scraper HTTP fetch logic (network-dependent)
- Playwright browser automation
- Alembic migrations (up/down)
- Dashboard (no frontend tests)
- Analytics aggregator (no unit tests)
- Scheduler orchestration
- Database connection pooling / async sessions

---

## 9. Current State Assessment

### What's Real and Working

| Component | Evidence |
|-----------|---------|
| PostgreSQL schema (33 tables) | 6 Alembic migrations applied |
| Trustpilot review scraping | 172 real reviews across 7 brands |
| AutoScout24 listing scraping | 83 real listings |
| RSS article ingestion | 115 real articles |
| Transformer NLP | DistilBERT on all 172 real reviews, 0 failures |
| Provenance tracking | `data_origin` column on all domain tables |
| Provenance-aware analytics | 3-pass aggregation (all/scraped/seeded) |
| API with origin filters | 3 endpoints default to scraped-only |
| Dashboard with origin toggle | Brands page Live/All/Seeded |
| Test suite | 179/180 passing in 13s |
| Dashboard build | Clean TypeScript build (0 errors) |

### What's Seeded / Synthetic

- ~2,500 car reviews with `data_origin='seeded'`
- Insurance reviews (mostly seeded)
- Some market articles (seeded alongside real RSS)
- Competitor pricing data (seeded)

### What's Incomplete or Stubbed

| Item | State |
|------|-------|
| Scraper `parse()` methods | Deprecated but still in code |
| LLM extraction (Gemini) | Optional, needs API key, not tested in production |
| Insurance review scraping | Scraper exists, no proven live path |
| Competitor pricing scraping | Scraper exists, no proven live path |
| Scheduled execution | `scheduler.py` exists but no cron/systemd setup |
| API authentication | None — fully open |
| Frontend tests | None |
| API rate limiting | None |
| Pricing page filters | UI exists but doesn't pass params to API |
| `.gitignore` | Minimal — only `.venv/`, UTF-16 encoded |

### Debris / Cleanup Needed

The repo contains 10+ temporary debug/error files that should be removed:

```
alembic_err.txt, alembic_error.txt, alembic_error2.txt ... alembic_error9.txt
alembic_job_migration.txt, alembic_run_output.txt
autogen_error.txt, error_dump.txt, migration_debug.txt
pgerror.txt, py_error.log
test_async_pure.py, test_asyncpg.py, test_db.py
test_encoding.py, test_encoding2.py, test_encoding3.py
test_password.py, test_raw_psycopg.py, test_v3.py
clean_all.py, drop_enums.py, fix_defaults2.py
fix_enum_defaults.py, force_drop_enums.py
regex_prep.py, remove_all_enums.py, reset_password.py
revert_defaults.py, run_migration.py, validate_db.py, verify_schema.py
```

These are development artifacts — one-off scripts and error logs that shouldn't be in the final repo.

---

## 10. Difficulties & Technical Debt

### 10.1 Bot Protection (Critical)

Most automotive review sites block headless browsers:
- Edmunds: 403 (Akamai WAF)
- Cars.com: 403
- CarGurus: 418
- DealerRater: 403
- HonestJohn: 403

**Impact:** Limits real data sources to Trustpilot and Parkers. The platform's value proposition depends on diverse, real data.

### 10.2 Sync-in-Async API (Architectural)

FastAPI handlers are `async def` but DB queries use sync SQLAlchemy sessions. This forces threadpool context switches on every request. Under load, this becomes a bottleneck.

**Fix required:** Either use `async_session` consistently or make handlers `def` (sync).

### 10.3 Incomplete `requirements.txt`

At least 8 runtime dependencies are missing: FastAPI, Uvicorn, Playwright, requests, asyncpg, feedparser, pydantic, pytest. Anyone cloning the repo cannot `pip install -r requirements.txt` and run the project.

### 10.4 Hardcoded Credentials

`database/connection.py` has fallback credentials visible in source code (password "conservatoire"). No `.env` configuration for database URL — it falls back to hardcoded defaults.

### 10.5 No Authentication

The API has no authentication or authorization. All endpoints are publicly accessible. For a PFE demo this is acceptable; for any deployment it's a blocker.

### 10.6 No CI/CD

No GitHub Actions, no pre-commit hooks, no linting pipeline. The only quality gate is manual `pytest` runs.

### 10.7 `.gitignore` is Broken

The `.gitignore` is UTF-16 encoded with only `.venv/` — it doesn't exclude `__pycache__`, `.pyc`, `.env`, `node_modules`, `dist`, `logs/`, or the many debug files. Several `.cpython-311.pyc` files are already tracked.

### 10.8 Deprecated Code Still Present

Scraper `parse()` methods are marked deprecated but not removed. This creates confusion about where extraction actually happens (answer: ParserPipeline).

### 10.9 Single Trustpilot Page

Review ingestion only scrapes page 1 of each brand (~20-25 reviews). Trustpilot supports `?page=2`, `?page=3`, etc. — pagination would multiply data volume.

### 10.10 No Insurance or Pricing Live Path

The scrapers exist for insurance reviews and competitor pricing, but there's no proven end-to-end live ingestion path (unlike car reviews which have been proven via Trustpilot).

---

## 11. SWOT Analysis

### Strengths

| # | Strength | Evidence |
|---|----------|---------|
| S1 | **Complete end-to-end pipeline** | Scrape → Parse → NLP → Analytics → API → Dashboard. All stages exist and function. |
| S2 | **Production-grade database schema** | 33 tables, 15 ENUMs, indexes on all FKs, CHECK constraints, UNIQUE constraints, soft delete, timestamps, lineage fields. This is not a toy schema. |
| S3 | **Real transformer NLP** | DistilBERT SST-2 running on real data with versioned results. Not a mock or placeholder. |
| S4 | **Provenance tracking** | `data_origin` field distinguishes seeded from scraped data throughout the stack — from DB to API to dashboard toggle. This is unusual sophistication for a PFE. |
| S5 | **Comprehensive observability** | PipelineStepRun with records_seen/processed/skipped/failed/inserted, DataQualityLog dead-letter table, scraper health metrics. Full audit trail. |
| S6 | **Clean parser pipeline design** | 7-stage processing chain with clear separation: clean → extract → normalize → validate → deduplicate → store. Well-architected. |
| S7 | **Robust scraper infrastructure** | Rate limiting, retry with backoff+jitter, connection pooling, User-Agent rotation, anti-detection. Professional-grade. |
| S8 | **Solid test suite** | 179/180 tests passing, covering parsers, NLP, validators, normalizers, observability, and API. |
| S9 | **Polished dashboard** | 6 pages, consistent design system, loading skeletons, error states, empty states, responsive layout, origin toggle. Not a prototype — it's a real UI. |
| S10 | **Multi-extraction strategy** | DOM heuristics + JSON-LD schema + LLM fallback. Graceful degradation when one method fails. |

### Weaknesses

| # | Weakness | Impact |
|---|----------|--------|
| W1 | **Incomplete `requirements.txt`** | New developers can't install and run the project. Missing 8+ critical dependencies. |
| W2 | **Broken `.gitignore`** | `.pyc` files, debug logs, and potentially sensitive files tracked in git. UTF-16 encoding may cause issues on some platforms. |
| W3 | **30+ debris files in repo root** | Error dumps, one-off scripts, debug files. Makes the project look unfinished and unprofessional. |
| W4 | **Sync-in-async API** | Architectural inconsistency that becomes a performance bottleneck under load. |
| W5 | **No authentication on API** | All data publicly accessible. Unacceptable for any non-demo deployment. |
| W6 | **Hardcoded credentials** | Database password visible in source code. Security anti-pattern. |
| W7 | **Only 2 git commits** | No meaningful git history. Appears as a single bulk push rather than incremental development. Weakens the narrative of iterative engineering. |
| W8 | **No CI/CD or pre-commit** | Quality depends entirely on manual discipline. |
| W9 | **No frontend tests** | 0% test coverage on 3,200 lines of TypeScript/React. |
| W10 | **Pricing page filters broken** | Coverage/region dropdowns are UI-only — they don't pass params to the API. |

### Opportunities

| # | Opportunity | Potential |
|---|------------|-----------|
| O1 | **Add Parkers as second review source** | Already confirmed accessible (HTTP 200). Would diversify data and prove multi-source capability. |
| O2 | **Trustpilot pagination** | Adding `?page=2..5` would multiply review volume 4-5x with minimal code change. |
| O3 | **Dockerize the full stack** | Docker Compose with PostgreSQL + API + Dashboard would make deployment trivial and demo-ready. |
| O4 | **Add BERTopic for real topic modeling** | Currently rule-based. BERTopic is already mentioned in model docstrings. Would elevate NLP sophistication. |
| O5 | **Comparative analytics** | The schema supports brand-vs-brand and scraped-vs-seeded comparisons. Dashboard could visualize these. |
| O6 | **Scheduled automation** | `scheduler.py` exists. A cron job or systemd timer would make the pipeline truly autonomous. |
| O7 | **Clean up and present** | Removing debris, fixing requirements.txt, writing a proper README would dramatically improve first impression. |
| O8 | **Insurance review live path** | Trustpilot scraper for insurance brands already exists. Proving this would complete the "insurance intelligence" story. |
| O9 | **Export / report generation** | Analytics data could be exported as PDF/CSV reports for stakeholders. |
| O10 | **API authentication** | Adding JWT or API key auth would make the platform deployable beyond localhost. |

### Threats

| # | Threat | Severity |
|---|--------|---------|
| T1 | **Bot protection escalation** | Trustpilot could add Cloudflare or reCAPTCHA at any time, breaking the proven live data path. Single-source dependency. | **High** |
| T2 | **Terms of Service violation** | Scraping Trustpilot may violate their ToS. Academic use is a gray area. If challenged during PFE defense, this needs a clear answer. | **Medium** |
| T3 | **Model staleness** | DistilBERT SST-2 is trained on movie reviews (SST-2 = Stanford Sentiment Treebank). Automotive review language may have different patterns. The model works but domain-specific fine-tuning would be more defensible. | **Medium** |
| T4 | **Database dependency** | PostgreSQL is a hard requirement — no SQLite fallback, no in-memory mode for demos. If the DB is down, everything is down. | **Medium** |
| T5 | **PyTorch size** | torch >= 2.0.0 is ~2 GB installed. This makes environment setup slow and disk-heavy. Could be a problem for evaluation machines. | **Low** |
| T6 | **No backup or recovery** | If the database is corrupted or lost, all scraped data and analytics are gone. No pg_dump, no replication, no backup strategy. | **Medium** |
| T7 | **Scope creep risk** | 33 tables, 9 modules, 6 dashboard pages — the project is already very large. Adding more features risks incomplete polish. | **Medium** |
| T8 | **PFE evaluation focus** | Evaluators may focus on what's NOT done (insurance live path, competitor pricing, topic modeling) rather than what IS done. The "What Remains" list is visible. | **Low** |

---

## 12. File Inventory

### Source Code (Production)

```
api/
  __init__.py
  main.py                          # FastAPI REST API (1,350 lines)

analytics/
  __init__.py
  aggregators.py                   # Brand reputation computation (274 lines)

database/
  __init__.py
  base.py                          # Base, mixins, UUID helper (56 lines)
  connection.py                    # Engine, session factory (233 lines)
  enums.py                         # 15 PostgreSQL ENUMs (155 lines)
  models.py                        # 33 ORM models (1,494 lines)
  migrations/
    env.py                         # Alembic env
    script.py.mako                 # Migration template
    versions/
      20260307_..._initial_schema.py
      20260316_..._add_analytics_tables.py
      20260316_..._add_pipeline_step_runs.py
      20260316_..._enrich_vehicle_and_article_fields.py
      20260318_..._add_data_origin_provenance.py
      20260319_..._analytics_provenance.py

nlp/
  __init__.py
  complaint_classifier.py          # Rule-based complaint detection (36 lines)
  keyword_extractor.py             # TF-IDF-like keywords (29 lines)
  nlp_pipeline.py                  # Orchestration (259 lines)
  sentiment_analyzer.py            # DistilBERT + fallback (155 lines)
  text_preprocessor.py             # Tokenization, stopwords (37 lines)
  topic_classifier.py              # Rule-based topics (40 lines)

parsers/
  __init__.py
  automotive_pipeline.py           # Pipeline orchestrator (387 lines)
  deduplicator.py                  # URL/hash/similarity dedup (111 lines)
  dom_extractor.py                 # CSS selector extraction (126 lines)
  html_cleaner.py                  # Boilerplate removal (127 lines)
  llm_extractor.py                 # Gemini LLM fallback (133 lines)
  normalizer.py                    # Field normalization (115 lines)
  schema_extractor.py              # JSON-LD parsing (133 lines)
  validator.py                     # Quality gate (50 lines)

scrapers/
  __init__.py
  base_scraper.py                  # Abstract base (310 lines)
  car_listing_scraper.py           # AutoScout24 (125 lines)
  car_review_scraper.py            # CarAndDriver, MotorTrend (112 lines)
  caranddriver_scraper.py          # CarAndDriver specific
  competitor_pricing_scraper.py    # Insurance pricing
  edmunds_scraper.py               # Edmunds
  http_client.py                   # Requests wrapper (189 lines)
  insurance_review_scraper.py      # Insurance reviews
  market_news_scraper.py           # Reuters, Bloomberg
  playwright_base_scraper.py       # Playwright base (218 lines)
  rate_limiter.py                  # Token bucket throttle (75 lines)
  retry_handler.py                 # Exponential backoff (97 lines)
  reuters_scraper.py               # Reuters specific
  trustpilot_scraper.py            # Trustpilot Playwright (56 lines)
  user_agents.py                   # UA rotation

scripts/
  __init__.py
  run_analytics.py                 # Analytics orchestrator
  run_listings_ingest.py           # AutoScout24 ingestion
  run_nlp_pipeline.py              # NLP orchestrator
  run_parser_pipeline.py           # Parser orchestrator
  run_reviews_ingest.py            # Trustpilot review ingestion
  run_rss_ingest.py                # RSS article ingestion
  run_scrapers.py                  # Scraper runner
  run_scraping_tasks.py            # Task queue runner
  scheduler.py                     # Master scheduler
  seed_enriched_data.py            # Synthetic data
  seed_realistic_data.py           # Synthetic data

observability/
  __init__.py
  step_recorder.py                 # Pipeline step tracking (214 lines)

tests/
  __init__.py
  conftest.py                      # Fixtures
  test_api_operational.py
  test_deduplicator.py
  test_nlp_pipeline.py
  test_normalizer.py
  test_observability.py
  test_parser_pipeline.py
  test_schema_extractor.py
  test_sentiment_analyzer.py
  test_validator.py

dashboard/
  index.html
  package.json
  vite.config.ts
  tailwind.config.js
  postcss.config.js
  tsconfig.json / tsconfig.app.json / tsconfig.node.json
  src/
    main.tsx                       # React entry
    App.tsx                        # Routing
    index.css                      # Design system (118 lines)
    api/
      client.ts                    # API client + types (366 lines)
    components/
      Layout.tsx                   # Sidebar + topbar (157 lines)
      KpiCard.tsx                  # Metric card (77 lines)
      StatusBadge.tsx              # Status indicator (59 lines)
      Skeleton.tsx                 # Loading placeholders (59 lines)
      Pagination.tsx               # Page controls (53 lines)
      EmptyState.tsx               # No-data state (23 lines)
      ErrorState.tsx               # Error display (37 lines)
    pages/
      Overview.tsx                 # Dashboard home (461 lines)
      Brands.tsx                   # Brand intelligence (445 lines)
      Operations.tsx               # Pipeline health (482 lines)
      Articles.tsx                 # Market articles (293 lines)
      Listings.tsx                 # Car listings (275 lines)
      Pricing.tsx                  # Competitor pricing (244 lines)
```

### Config Files

```
.env                               # PYTHONPATH=.
.gitignore                         # .venv/ (UTF-16, needs fix)
.pyre_configuration                # Pyre type checker
.vscode/settings.json              # VS Code config
alembic.ini                        # Alembic config
pyproject.toml                     # Minimal (Pyre only)
requirements.txt                   # Python deps (incomplete)
```

### Debug / Temporary (should be removed)

```
alembic_err.txt, alembic_error.txt ... alembic_error9.txt (10 files)
alembic_job_migration.txt, alembic_run_output.txt
autogen_error.txt, error_dump.txt, migration_debug.txt, pgerror.txt
py_error.log
test_async_pure.py, test_asyncpg.py, test_db.py
test_encoding.py, test_encoding2.py, test_encoding3.py
test_password.py, test_raw_psycopg.py, test_v3.py
clean_all.py, drop_enums.py, fix_defaults2.py
fix_enum_defaults.py, force_drop_enums.py
regex_prep.py, remove_all_enums.py
reset_password.py, revert_defaults.py
run_migration.py, validate_db.py, verify_schema.py
```

### Documentation

```
DATA_REALITY_AUDIT.md              # Data reality assessment
REAL_DATA_RECOVERY.md              # Data recovery sprint report
REAL_REVIEWS_ANALYTICS_SPRINT.md   # Reviews sprint report
architecture_design.pdf            # Architecture diagram (binary)
PROJECT_TECHNICAL_AUDIT.md         # This file
```

---

*End of audit.*
