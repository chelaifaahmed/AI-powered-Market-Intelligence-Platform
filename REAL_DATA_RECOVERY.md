# Real Data Recovery — Sprint Report

**Date:** 2026-03-18
**Branch:** Ahmed

---

## What Was Done

The platform was previously running entirely on seeded (fabricated) data with no provenance
separation. This sprint introduced end-to-end real data pipelines, proved them in the database,
and regrounded the dashboard to default to real data.

---

## Step 1 — Provenance Column

Added `data_origin VARCHAR(20) CHECK IN ('seeded', 'scraped', 'imported')` with index to all
five domain tables:

| Table | Alembic revision |
|---|---|
| `car_reviews` | `e1f2a3b4c5d6` |
| `insurance_reviews` | `e1f2a3b4c5d6` |
| `car_listings` | `e1f2a3b4c5d6` |
| `market_trend_articles` | `e1f2a3b4c5d6` |
| `competitor_pricings` | `e1f2a3b4c5d6` |

All pre-existing rows were back-filled to `seeded` via `server_default`.
New real rows are inserted with `data_origin='scraped'`.

---

## Step 2 — Real Article Pipeline (RSS)

**Script:** `scripts/run_rss_ingest.py`
**Method:** `urllib.request` + `xml.etree.ElementTree` — zero new dependencies, no JS required.

| Feed | Status | Articles Inserted |
|---|---|---|
| Autoblog | 403 Forbidden — blocked | 0 |
| InsideEVs | OK | 20 |
| Motor1 | OK | 20 |
| Electrek | OK | 25 |
| Auto Express | OK | 25 |
| Car and Driver | OK | 25 |

**Total real articles in DB:** `115` (`data_origin='scraped'`)
**Storage:** Raw XML stored in `raw_pages` with `scraper_version='rss-ingest-1.0'`
**Sample real article:**
```
Title:  Report: Trump's Tariffs Have Cost Automakers $35 Billion So Far
Source: caranddriver.com
Date:   2026-03-16
URL:    https://www.caranddriver.com/news/a70758296/trump-tariffs-cost-automakers-35-billion/
```

---

## Step 3 — Real Listings Pipeline (AutoScout24)

**Script:** `scripts/run_listings_ingest.py`
**Method:** Playwright (`sync_playwright`) → `__NEXT_DATA__` JSON extraction (20 listings/page).

| Search | Brand | Inserted |
|---|---|---|
| Toyota Germany | Toyota | 20 |
| Volkswagen Germany | Volkswagen | 20 |
| BMW Germany | BMW | 20 |
| Electric Germany | Mixed (EV) | 23 |

**Total real listings in DB:** `83` (`data_origin='scraped'`)
**Fields captured:** brand, model, transmission, fuel_type, mileage_km, listed_price, city, country, listing_year, listing_url
**Sample real listing:**
```
Hyundai Kona EV  |  €22,980  |  26,999 km  |  Andernach, DE  |  2019
```

---

## Step 4 — NLP Model Proof

**Problem found:** `transformers` package was absent from `requirements.txt`, causing
`_get_pipeline()` to always fail and fall back to `rule-nlp-v1`. Model version was also
hardcoded as `"rule-nlp-v1"` regardless of which code path ran.

**Fixes applied:**

1. Added `transformers>=4.35.0` and `torch>=2.0.0` to `requirements.txt` and installed them.
2. Replaced hardcoded `_MODEL_VERSION` with dynamic resolution in `nlp/nlp_pipeline.py`:
   - Calls `_get_pipeline()` at import time
   - Resolves to `"distilbert-sst2-v1"` if transformer loads successfully
   - Falls back to `"rule-nlp-v1"` only if import fails

**DB proof — NLP model version counts:**

| Model Version | Records |
|---|---|
| `distilbert-sst2-v1` | **115** (all real scraped articles) |
| `rule-nlp-v1` | 114 (pre-existing seeded articles) |

The transformer model (`distilbert-base-uncased-finetuned-sst-2-english`) is confirmed running
on all real articles.

---

## Step 5 — Dashboard Regrounded

### API changes (`api/main.py`)
- `data_origin` field added to all five Pydantic output schemas
- `?origin=scraped|seeded|imported` filter added to `/api/reviews/car`, `/api/listings`, `/api/articles`
- New endpoint `GET /api/data/provenance` returns per-table origin counts + NLP model breakdown
- `GET /api/dashboard/summary` includes `provenance: {real_articles, real_listings, real_reviews}`

### Dashboard changes
- **`client.ts`**: `data_origin` added to `CarReview`, `InsuranceReview`, `Listing`, `Article` interfaces; `origin` param added to `listings()`, `articles()`, `carReviews()`; `ProvenanceSummary` interface and `api.dataProvenance()` added
- **`Overview.tsx`**: Provenance banner at top — shows live pill counts for real articles, seeded articles, real listings, seeded listings, transformer NLP count, rule NLP count
- **`Articles.tsx`**: Defaults to `origin=scraped` (Live); toggle to switch All / Live / Seeded; each card shows a green "Live" or grey "Seeded" badge
- **`Listings.tsx`**: Defaults to `origin=scraped` (Live); toggle to switch All / Live / Seeded; table has "Origin" column with green "Live" / grey "Seeded" pills

---

## Final Counts

```
GET /api/data/provenance
{
  "car_reviews":        { "seeded": 1547 },
  "insurance_reviews":  { "seeded": 225 },
  "car_listings":       { "seeded": 507, "scraped": 83 },
  "market_articles":    { "scraped": 115, "seeded": 114 },
  "competitor_pricings":{ "seeded": 141 },
  "nlp_models":         { "distilbert-sst2-v1": 115, "rule-nlp-v1": 114 }
}
```

---

## What Remains Blocked / Future Work

| Item | Status |
|---|---|
| Autoblog RSS | 403 — blocked by CDN |
| Car reviews from real scrapers | Not yet implemented — all 1,547 are seeded |
| Insurance reviews from real scrapers | Not yet implemented — all 225 are seeded |
| Competitor pricing from real sources | Not yet implemented — all 141 are seeded |
| AutoScout24 listing pagination (page 2+) | Script supports it; single page per search URL used |
| Scheduled / cron-based refresh | Not wired — scripts must be run manually |

---

## How to Refresh Real Data

```bash
# Ingest latest articles from all RSS feeds
python scripts/run_rss_ingest.py --max-per-feed 20

# Ingest latest AutoScout24 listings
python scripts/run_listings_ingest.py

# Re-run NLP on any unprocessed rows
python scripts/run_nlp_pipeline.py
```
