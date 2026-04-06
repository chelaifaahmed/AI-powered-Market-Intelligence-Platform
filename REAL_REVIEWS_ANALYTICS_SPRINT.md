# Real Reviews & Provenance-Aware Analytics Sprint

**Date:** 2026-03-19
**Status:** Complete

---

## Sprint Goals

1. Prove one real car review source end-to-end
2. Make review NLP real and verifiable (transformer on real reviews)
3. Make analytics provenance-aware (seeded vs scraped separation)
4. Reground API and dashboard to default to live data
5. Operationalize the live review path

---

## Step 1 — Pipeline Reality Inspection

### Source Accessibility Audit

| Source       | URL Pattern             | HTTP Status | Result              |
|-------------|-------------------------|-------------|---------------------|
| Edmunds     | edmunds.com             | 403         | Blocked (Akamai)    |
| Cars.com    | cars.com                | 403         | Blocked             |
| CarGurus    | cargurus.com            | 418         | Blocked             |
| DealerRater | dealerrater.com         | 403         | Blocked             |
| HonestJohn  | honestjohn.co.uk        | 403         | Blocked             |
| **Trustpilot** | trustpilot.com/review | **200**     | **Accessible**      |
| Parkers     | parkers.co.uk           | 200         | Accessible          |

**Decision:** Trustpilot chosen — structured review cards with rating, title, body, author, date.

### Pre-Sprint State

- `car_reviews` table: ~2,500 rows, all `data_origin='seeded'`
- Analytics: no provenance awareness — seeded and scraped mixed invisibly
- API: no origin filters — all endpoints returned combined data
- Dashboard: no way to distinguish live vs synthetic data

---

## Step 2 — Real Review Ingestion (Trustpilot)

### Script: `scripts/run_reviews_ingest.py`

**Pipeline:** Playwright fetch -> BeautifulSoup extraction -> `car_reviews` (data_origin='scraped') -> NLP

**Trustpilot Brand Pages (8 sources):**
- Toyota, Ford, BMW, Hyundai, Honda, Volkswagen, Tesla, Kia

**Extraction targets per review card:**
- Rating: `<img alt="Rated X out of 5 stars">`
- Title: `<h2>` inside card
- Body: longest `<p>` with >30 chars
- Author: `<span data-consumer-name-typography>`
- Date: `<time datetime="ISO8601">`

### Results

| Brand      | Reviews Inserted |
|-----------|-----------------|
| Ford       | 25              |
| Honda      | 25              |
| Tesla      | 25              |
| Kia        | 25              |
| Toyota     | 24              |
| Hyundai    | 24              |
| BMW        | 24              |
| **Total**  | **172**         |

- Pages fetched: 8/8
- Duplicates skipped: 0 (first run)
- Failures: 0
- All reviews stored with `data_origin='scraped'`, `content_hash` for dedup

---

## Step 3 — Real NLP Verification

**Model:** `distilbert-base-uncased-finetuned-sst-2-english` (DistilBERT SST-2)

| Metric                  | Value                  |
|------------------------|------------------------|
| Reviews processed       | 172                    |
| model_version           | `distilbert-sst2-v1`  |
| Failures                | 0                      |
| Sentiment labels        | POSITIVE / NEGATIVE    |
| Confidence scores       | 0.50 – 0.99 range     |

All 172 scraped reviews have `is_processed=True` with real transformer sentiment scores in `car_review_nlp`.

---

## Step 4 — Provenance-Aware Analytics

### Migration: `20260319_f2a3b4c5d6e7_analytics_provenance.py`

**Schema changes:**
- `brand_reputation_scores.data_origin` — VARCHAR(20) NOT NULL DEFAULT 'all'
- `sentiment_trends.data_origin` — VARCHAR(20) NOT NULL DEFAULT 'all'
- Unique constraints updated: `(brand_id, period_date)` -> `(brand_id, period_date, data_origin)`
- Indexes added: `idx_brs_origin`, `idx_st_origin`

### Aggregator changes: `analytics/aggregators.py`

`compute_brand_reputation()` now runs **3 passes**:

| Pass    | Filter              | data_origin value |
|---------|---------------------|-------------------|
| 1       | All reviews         | `all`             |
| 2       | `data_origin='scraped'` | `scraped`     |
| 3       | `data_origin='seeded'`  | `seeded`      |

**Result:** 704 total aggregation groups (327 all + 82 scraped + 295 seeded)

---

## Step 5 — API & Dashboard Reground

### API Changes (`api/main.py`)

| Endpoint                           | Change                                          |
|------------------------------------|-------------------------------------------------|
| `GET /api/brands/{id}/reputation`  | Added `?origin=` param, **default: `scraped`**  |
| `GET /api/brands/{id}/sentiment`   | Added `?origin=` param, **default: `scraped`**  |
| `GET /api/brands/summary`          | Added `?origin=` param for filtered summaries   |

**Default behavior:** API returns live/scraped data unless explicitly overridden.

### Dashboard Changes

**`dashboard/src/pages/Brands.tsx`:**
- Origin toggle: **Live** (scraped) | All | Seeded
- Default: Live — shows only real scraped review analytics
- Toggle wired to `brandReputation()` and `brandSentiment()` API calls

**`dashboard/src/api/client.ts`:**
- `brandReputation(id, origin?)`, `brandSentiment(id, origin?)`, `brandsSummary(origin?)` updated
- `ReputationScore` and `SentimentTrend` interfaces include `data_origin` field

**`dashboard/src/pages/Overview.tsx`:**
- Fixed TypeScript type inference for `brandsSummary()` wrapper

**Build status:** Clean (`npm run build` succeeds, 0 TypeScript errors)

---

## Step 6 — Operationalization

### Enhancements to `scripts/run_reviews_ingest.py`

| Feature               | Implementation                                                |
|-----------------------|---------------------------------------------------------------|
| **Deduplication**     | `content_hash` (SHA-256 of URL + text) — prevents re-insertion |
| **Freshness check**   | `--freshness-hours N` — skips brands scraped within N hours (default 12) |
| **Failure logging**   | Fetch errors persisted to `data_quality_log` dead-letter table |
| **Observability**     | `PipelineStepRun` recorded with records_seen/processed/skipped/failed + metadata |

### CLI Usage

```bash
# Standard run (skips brands scraped in last 12h)
python scripts/run_reviews_ingest.py

# Force re-scrape all brands
python scripts/run_reviews_ingest.py --freshness-hours 0

# Limit reviews per page
python scripts/run_reviews_ingest.py --max-per-page 10
```

---

## Evidence Summary

| Metric                              | Count  |
|-------------------------------------|--------|
| Real scraped reviews (Trustpilot)   | 172    |
| Real NLP-processed reviews          | 172    |
| NLP model                           | DistilBERT SST-2 |
| Brands with live data               | 7      |
| Provenance-aware aggregation groups | 704    |
| API endpoints with origin filter    | 3      |
| Dashboard origin toggle             | Brands page |
| Failure logging                     | DataQualityLog |
| Step run observability              | PipelineStepRun |

---

## What Remains

1. **More review sources** — Parkers (accessible, 200) could be added as a second source
2. **Multi-page Trustpilot** — currently scrapes page 1 only; pagination (`?page=2`) would increase coverage
3. **Insurance review ingestion** — same pattern could be applied to insurance review sources
4. **Scheduled execution** — cron/task scheduler for periodic re-ingestion
5. **Overview page origin toggle** — Brands page has it; Overview could benefit from similar filtering
6. **Alert on consecutive failures** — `PipelineStepRun` data enables alerting but no alert rules defined yet

---

## Files Modified / Created

| File | Action |
|------|--------|
| `scripts/run_reviews_ingest.py` | Created — Trustpilot review ingestion + NLP + dedup + freshness + failure logging |
| `database/migrations/versions/20260319_f2a3b4c5d6e7_analytics_provenance.py` | Created — data_origin on analytics tables |
| `database/models.py` | Modified — data_origin columns on BrandReputationScore, SentimentTrend |
| `analytics/aggregators.py` | Modified — 3-pass provenance-aware aggregation |
| `api/main.py` | Modified — origin query params on reputation/sentiment/summary endpoints |
| `dashboard/src/api/client.ts` | Modified — origin params + data_origin in interfaces |
| `dashboard/src/pages/Brands.tsx` | Modified — origin toggle (Live/All/Seeded) |
| `dashboard/src/pages/Overview.tsx` | Modified — TypeScript fix for brandsSummary |
