# DATA REALITY AUDIT
**Platform:** Automotive Intelligence Platform
**Database:** `automotive_intelligence` (PostgreSQL, localhost:5432)
**Audit Date:** 2026-03-18
**Auditor:** Claude Code (automated SQL evidence)

---

## 1. Executive Summary

The platform has a well-architected schema and a functioning dashboard — but the end-to-end data pipeline is **not producing real data in production**. All 1,547 car reviews, 507 listings, 114 articles, 225 insurance reviews, and 141 competitor pricing records come from Python seed scripts, not from the real scraping/parsing pipeline.

The real scrapers have collected 27 raw HTML pages. Of those, **only 1 was successfully parsed** (a Car and Driver page from caranddriver.com). The other 26 are either blocked by target sites (HTTP 403/410) or are JavaScript-rendered pages that the HTML parser cannot extract data from.

The NLP pipeline runs on seeded data and uses `rule-nlp-v1` — a rule-based heuristic, not a real ML model — and produces anomalous results (e.g., a review rated 4.5 stars classified as NEGATIVE). Review texts are templated from a pool of ~30 templates, with the most-common text appearing in 74 rows.

**The dashboard is grounded in structured, internally consistent data. None of it was obtained by actually scraping and parsing real web pages at scale.**

---

## 2. Scraping Audit

### 2.1 Raw Pages Collected

| Domain | Total Pages | HTTP 200 | HTTP Non-200 | Parsed | Failed | Unparsed | Avg HTML Size |
|--------|------------|----------|--------------|--------|--------|----------|---------------|
| www.caranddriver.com | 5 | 5 | 0 | **1** | 1 | 3 | ~2.0 MB |
| www.autoscout24.com | 5 | 5 | 0 | 0 | 0 | 5 | ~707 KB |
| www.motortrend.com | 4 | 4 | 0 | 0 | 0 | 4 | ~4.2 MB |
| www.nerdwallet.com | 2 | 2 | 0 | 0 | 0 | 2 | ~1.3 MB |
| www.forbes.com | 2 | 0 | **2** | 0 | 0 | 2 | NULL |
| www.autonews.com | 1 | 1 | 0 | 0 | 0 | 1 | ~4.1 MB |
| www.bloomberg.com | 1 | 0 | **1** | 0 | 0 | 1 | NULL |
| www.reuters.com | 1 | 0 | **1** | 0 | 0 | 1 | NULL |
| www.cnn.com | 1 | 0 | **1** | 0 | 0 | 1 | NULL |
| www.insurancequotes.com | 1 | 1 | 0 | 0 | 1 | 0 | ~104 KB |
| www.moneysupermarket.com | 1 | 0 | **1** | 0 | 0 | 1 | NULL |
| www.confused.com | 1 | 0 | **1** | 0 | 0 | 1 | NULL |
| www.comparethemarket.com | 1 | 0 | **1** | 0 | 0 | 1 | NULL |
| www.gocompare.com | 1 | 0 | **1** | 0 | 0 | 1 | NULL |
| **TOTAL** | **27** | **18** | **9** | **1** | **1** | **25** | — |

**Parse rate: 1/27 = 3.7%**

### 2.2 Scraping Runs

10 `scraping_runs` recorded. The 5 most recent real runs (2026-03-16) each extracted **0 records** despite successfully downloading bytes:

```
scrape_caranddriver   → 5 pages, 0 records extracted (bytes: 0, backdated run)
scrape_competitor_pricing → 1 page, 0 records, 1 error (price extraction failed)
scrape_autoscout24    → 5 pages, 0 records (JS-rendered, parser blind)
scrape_motortrend     → 4 pages, 0 records (JS-rendered)
scrape_nerdwallet     → 2 pages, 0 records (JS-rendered)
```

The 5 older runs (2026-02-14 to 2026-02-22) show 15–30 "records extracted" but these were created during seeding with backdated `started_at` timestamps — not genuine scraping results.

### 2.3 Recorded Errors

| Error | URL | Type |
|-------|-----|------|
| `competitor_pricing record has no valid price — skipping` | insurancequotes.com | ValueError |
| `CheckViolation on competitor_pricings` | insurancequotes.com | IntegrityError |
| `No partition found for car_reviews` (scraped_at out of range) | caranddriver.com | IntegrityError |

**Root causes identified:**
- Insurance comparison sites (confused.com, gocompare.com, comparethemarket.com, moneysupermarket.com) return HTTP 403 — **access denied**.
- Premium news sites (Bloomberg, Reuters, CNN, Forbes) return HTTP 403/404/410 — **paywalled/blocked**.
- AutoScout24, MotorTrend, Nerdwallet, AutoNews return 200 HTTP but render content via JavaScript — the static HTML parser extracts nothing.
- The real Car and Driver scrape on 2026-03-10 hit a partition constraint (scraped_at year out of range).

---

## 3. Parsing Audit

### 3.1 Parser Pipeline Results

The parser pipeline operates on `raw_pages` records. With only 1 successfully parsed page and 0 records extracted from recent real runs, **the parser has produced zero domain records from real scraped HTML**.

All structured data in domain tables was inserted directly by seed scripts:
- `seed_realistic_data.py` — original 10 brands, 500 reviews, 141 listings (run 2026-03-16 ~02:28)
- `seed_enriched_data.py` — 10 additional brands, 1,005 reviews, 366 listings, 85 articles, 150 insurance reviews, 72 competitor pricing records (run 2026-03-16 ~17:19)
- `run_analytics.py` — recomputed analytics, ran NLP (2026-03-18 00:25)

### 3.2 Entity Counts (All From Seeding)

| Entity | Count | Origin |
|--------|-------|--------|
| `car_brands` | 20 | Seed (10 + 10) |
| `car_models` | 80 | Seed (4 per brand, exact) |
| `car_reviews` | 1,547 | Seed |
| `insurance_reviews` | 225 | Seed (150 Trustpilot + 5 demo + 70 original) |
| `car_listings` | 507 | Seed (141 + 366) |
| `market_trend_articles` | 114 | Seed (29 + 85) |
| `competitor_pricings` | 141 | Seed |

**The 4-per-brand model distribution** (exactly 4 models for all 20 brands without exception) is a definitive seeding fingerprint — real-world crawling would produce uneven distributions.

---

## 4. NLP Audit

### 4.1 Coverage

| Table | Total Records | Has Sentiment | Coverage |
|-------|--------------|---------------|----------|
| `car_review_nlp` | 1,547 | 1,547 | **100%** |
| `insurance_review_nlp` | 225 | 225 | **100%** |
| `article_nlp_results` | 114 | 114 | **100%** |

NLP coverage is perfect — because the NLP pipeline was run *after* seeding, processing all records in bulk.

### 4.2 Model Version

Every NLP record shows `model_version = 'rule-nlp-v1'`. This is a **heuristic rule engine**, not a real trained ML model (e.g., DistilBERT). The sentiment computation is done programmatically during seeding/NLP pipeline runs, not by inference on an actual language model.

### 4.3 Sentiment Distribution

| Table | Positive | Neutral | Negative | Avg Score |
|-------|---------|---------|----------|-----------|
| Car reviews | 1,321 (85.4%) | 40 (2.6%) | 186 (12.0%) | 0.7211 |
| Insurance reviews | 151 (67.1%) | — | 68 (30.2%) | — |

**Anomaly detected — NLP/rating misalignment:**

```
rating=4.3 → sentiment=NEGATIVE (-0.9911)  ← review text: "The Nissan Ariya is the answer for drivers..."
rating=4.5 → sentiment=NEGATIVE (-0.9654)  ← review text: "Few cars balance dynamics and efficiency..."
rating=3.5 → sentiment=NEGATIVE (-0.9901)  ← same positive-sounding text
```

These mismatches suggest the rule engine uses keyword matching on review text rather than rating-to-label mapping, and some template phrases accidentally trigger negative keywords. This is a bug in the rule-based NLP logic.

### 4.4 Complaint Type Coverage

Only **399 / 1,547** car review NLP records (25.8%) have a `complaint_type_id`. The remaining 74.2% are NULL — the complaint taxonomy is incomplete or the classifier rarely fires.

### 4.5 Article NLP — Summary Quality

Article summaries follow a mechanical template:
```
"topics=pricing, technology; keywords=market, market surge, surge 2025, 2025 electric..."
```
The `summary_text` field is not a human-readable summary. It is a keyword/topic concatenation string — useful for search but not meaningful prose.

---

## 5. Analytics Audit

### 5.1 Brand Reputation Scores

296 records across 20 brands. Coverage spans September 2024 – March 2026 (18–19 monthly periods per brand).

**Sample verified figures:**

| Brand | Periods | Avg Rating | Avg Sentiment | Total Reviews Counted |
|-------|---------|-----------|---------------|-----------------------|
| Porsche | 18 | 4.671 | 0.9911 | 103 |
| Mazda | 19 | 4.179 | 0.9738 | 103 |
| Volvo | 18 | 4.370 | 0.9812 | 103 |
| Tesla | 11 | 3.133 | 0.2581 | 70 |
| Land Rover | 18 | 3.356 | 0.5622 | 103 |

The analytics pipeline correctly aggregates from seeded review data. The figures are **internally consistent** (high-rating brands have high sentiment scores). However, because the underlying reviews are seeded from templates, these "reputation scores" do not represent actual market intelligence.

**Notable**: Tesla's low sentiment score (0.2581) and the newest brands (Porsche, Volvo, Nissan etc.) having more historical periods than the original 10 brands (which only start 2025-03-01) — this is an artifact of different seed scripts using different date ranges.

### 5.2 Sentiment Trends

296 records, all consistent with review data:
- Total positive: 1,321 | Negative: 187 | Neutral: 40
- Correctly matches `car_review_nlp` table totals (1,321 positive, 186 negative — 1 count discrepancy suggests a re-aggregation timing issue).

### 5.3 Listings Analytics

| Metric | Value |
|--------|-------|
| Total listings | 507 |
| Avg price | €41,393 |
| Avg mileage | 57,694 km |
| Price range | €10,300 – €176,600 |
| Countries covered | 10 |

**Listings by fuel type:** Electric (136, 26.8%), Hybrid (120, 23.7%), Petrol (103, 20.3%), Diesel (7, 1.4%), NULL (141, 27.8%)

The 141 NULL fuel_type listings are the original seed batch from before the `fuel_type` column existed. The backfill was only applied to the enriched seed, not to original records.

---

## 6. Dashboard Audit

### 6.1 API Endpoints — Verified Working

All endpoints queried and returning data (server confirmed running):

| Endpoint | Records Returned | Grounded In |
|----------|-----------------|-------------|
| `GET /api/brands` | 20 brands | Seeded data |
| `GET /api/models` | 80 models | Seeded, 4/brand |
| `GET /api/reviews/car` | 1,547 (paged) | Seeded |
| `GET /api/reviews/insurance` | 225 (paged) | Seeded |
| `GET /api/listings` | 507 (paged) | Seeded |
| `GET /api/articles` | 114 (paged) | Seeded |
| `GET /api/competitors` | 141 (paged) | Seeded |
| `GET /api/brands/{id}/reputation` | Per brand | Computed from seeded |
| `GET /api/brands/{id}/sentiment` | Per brand | Computed from seeded |
| `GET /api/dashboard/summary` | Aggregates | All seeded |
| `GET /api/pipeline/status` | Pipeline health | 17 step runs |
| `GET /api/listings/breakdown` | Fuel/color/brand | Seeded |

### 6.2 Data Quality Fields Observed

- **`pros` / `cons` / `variant_tested`** on car reviews: 100% populated (1,547/1,547) — seeded with structured values.
- **`horsepower_hp` / `msrp_eur`** on car models: 64/80 (80%) populated — 16 original models have no spec data backfilled.
- **`battery_kwh`** on car models: 30/80 (37.5%) — only EV/PHEV models.
- **`engine_type` / `segment` / `body_type`** on models: 75/80 (93.8%) populated.
- **29 articles** have `category = NULL` — the original seed pre-dates the category migration.

### 6.3 Source Attribution

17 `review_sources` registered. However, source attribution is inconsistent:
- Most reviews use named sources (Car and Driver, Edmunds, MotorTrend, etc.) with high `reliability_score` (0.86–0.96).
- Some records reference `demo_seed` (5 insurance reviews) — an internal marker with no real URL.
- `source_type` column is NULL for all 17 sources — the type taxonomy is never populated.

---

## 7. Bottleneck Analysis

### Bottleneck 1 — JavaScript-Rendered Sites (BLOCKING)
AutoScout24, MotorTrend, NerdWallet, Automotive News return valid HTML but all structured content is rendered client-side by React/Next.js. The current HTML parser sees skeleton markup only. This affects **16 of 27 raw pages** (59%).

**Fix required:** Switch to a headless browser (Playwright `page.wait_for_selector()` after JS load) or use official APIs/RSS feeds.

### Bottleneck 2 — Blocked/Paywalled Domains (BLOCKING)
Bloomberg, Reuters, CNN, Forbes, and all UK insurance aggregators (gocompare, confused, comparethemarket, moneysupermarket) return HTTP 403 or 410. These are production-hardened anti-scraping defenses.

**Fix required:** Use official APIs (Reuters Connect, Bloomberg Data License), RSS feeds, press releases, or replace blocked sources with open alternatives (GDELT, Common Crawl, Cars.com API, AutoTrader API).

### Bottleneck 3 — Review Text Templates (DATA QUALITY)
The seeded review corpus reuses ~30 template strings. The most duplicated text appears 74 times. A real analyst or ML model running on this corpus would find it immediately suspect.

**Fix required:** Either import real scraped content or generate sufficiently varied synthetic text if synthetic data must remain. Long-term: fix scrapers to extract actual review text.

### Bottleneck 4 — NLP is Rule-Based, Not ML (QUALITY GAP)
`rule-nlp-v1` produces misclassifications (4.3-star review → NEGATIVE). It generates keyword concatenations, not real summaries. There is no DistilBERT, BERT, or any transformer inference happening.

**Fix required:** Integrate a real sentiment model (e.g., `cardiffnlp/twitter-roberta-base-sentiment` via HuggingFace, or OpenAI API) to produce real NLP outputs. The pipeline infrastructure exists — just swap the model call.

### Bottleneck 5 — Partition Constraint on Real Scraped Reviews
The one real car review scraped from caranddriver.com (2026-03-10) failed with `no partition found` because `scraped_at` was out of range. The `car_reviews` table is RANGE-partitioned into 2024/2025/2026/2027 slots.

**Fix required:** The scraper must use `scraped_at = NOW()` (already in range) and the parser must also pass `scraped_at` correctly. The existing partition setup is fine.

### Bottleneck 6 — Missing Complaint Type Classification
74.2% of car review NLP records have `complaint_type_id = NULL`. The complaint type taxonomy exists (the `complaint_types` table) but the classifier rarely assigns it.

**Fix required:** Implement a proper complaint classifier using keyword sets per type, or use a multi-label classifier.

---

## 8. Concrete Next Actions

**Priority 1 — Fix the real scraping pipeline (highest ROI)**

| Action | Target | Effort |
|--------|--------|--------|
| Switch AutoScout24 / MotorTrend scrapers to Playwright with `wait_for_load_state('networkidle')` | 9 JS-rendered raw pages | Medium |
| Replace blocked news sources with RSS feeds: Reuters RSS, Automotive News RSS, AutoExpress RSS | 6 blocked domains | Low |
| Replace insurance aggregators with open sources: EIOPA data, insurer press releases, Cars.com API | 5 blocked domains | Medium |
| Fix partition constraint: ensure parser passes `scraped_at = NOW()` | caranddriver.com parser | Low |

**Priority 2 — Replace rule-NLP with real inference**

| Action | Impact |
|--------|--------|
| Add `transformers` to requirements.txt, load `distilbert-base-uncased-finetuned-sst-2-english` | Real sentiment on 1,547 reviews |
| Re-run NLP pipeline — it already handles all records via `is_processed` flag | Immediate quality boost |
| Add summarization: `facebook/bart-large-cnn` or OpenAI `gpt-4o-mini` for article summaries | Real article NLP |

**Priority 3 — Fix data quality gaps**

| Action | Impact |
|--------|--------|
| Backfill `fuel_type` on 141 original listings (join via car_model.engine_type) | Eliminate 27.8% NULL fuel_type |
| Populate `source_type` on `review_sources` (automotive_review, insurance_review, news) | Enable source filtering |
| Backfill spec data on 16 unspec'd original models | Full spec coverage |
| Populate `category` on 29 original NULL articles | Complete article taxonomy |

**Priority 4 — Validate end-to-end with one real source**

Pick ONE source that can be reliably scraped end-to-end and run the full pipeline:
1. **Cars.com** — has a public API with real listings
2. **Auto Express (RSS)** — structured XML feed, no JS rendering
3. **Consumer Reports** — structured review data available via their API

Validate: raw_page → parsed record → NLP → analytics → dashboard in a single demonstrable cycle.

---

## Appendix: Key Counts at Audit Time

```
raw_pages:            27  (1 parsed, 26 not)
car_brands:           20  (all seeded)
car_models:           80  (exactly 4 per brand — seeding fingerprint)
car_reviews:       1,547  (0 from real scraping)
car_review_nlp:    1,547  (100% coverage, rule-based)
insurance_reviews:   225  (150 Trustpilot seed + 75 original)
insurance_review_nlp:225  (100% coverage)
market_trend_articles:114 (0 from real scraping)
article_nlp_results: 114  (100% coverage)
car_listings:        507  (0 from real scraping)
competitor_pricings: 141  (0 from real scraping)
brand_reputation:    296  (20 brands × ~15 months, correctly computed)
sentiment_trends:    296  (consistent with NLP outputs)
scraping_runs:        10  (8 real + 2 backdated seeds)
pipeline_step_runs:   17  (all SUCCESS, 0 records_failed)
scraping_errors:       3  (partition mismatch, blocked site, price extraction)
review_sources:       17  (source_type NULL on all 17)
```
