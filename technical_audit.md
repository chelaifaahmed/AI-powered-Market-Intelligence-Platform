Technical Audit — TEAMWILL Market Intelligence Platform
Project: AI-Powered Automotive & Insurance Market Intelligence Platform
Owner: Ahmed (PFE / Final Year Project, INSAT)
Client context: TEAMWILL — Tunisian ERP / leasing-systems vendor targeting auto insurers and dealers in Tunisia + EU
Scope of audit: Full stack — database, ETL, NLP, ML fine-tuning, analytics, API, dashboard
Note: Docker assets exist in repo but are not used per your instruction; deployment is local Windows-native (.venv + npm run dev)

1. Executive Summary
The platform is a vertically-integrated market-radar system that:

Ingests unstructured public data (car reviews, insurance reviews, RSS auto-news, marketplace listings, Reddit, NHTSA complaints, Google Places).
Cleans & normalizes raw HTML into 33 typed PostgreSQL tables with provenance (seeded vs scraped).
Enriches every review/article with NLP — sentiment (fine-tuned DistilBERT 3-class), topics, complaints, keywords, 768-dim BGE embeddings.
Scores each brand/insurer on a 0–100 Opportunity Signal Strength combining article distress signals, sentiment trend slope, market presence, and complaint intensity.
Surfaces actionable sales targets through a 16-page React dashboard, a Groq-powered conversational analyst, and ReportLab-generated PDF briefings.
Maturity assessment: Production-grade architecture with proper migrations, observability, and class-balanced fine-tuning. Real data is partial (~3,000 real reviews vs ~1,500 seeded) but the provenance separation is enforced, so analytics remain trustworthy. Codebase is ~16k LOC of Python + ~10k LOC of TypeScript.

2. Business Use Case
2.1 The problem TEAMWILL needed to solve
TEAMWILL sells ERP modules — Claims Management, Fleet & Service, Customer-Service, etc. — to insurers, leasing companies, and dealerships. Their sales motion was reactive: cold lists, generic outreach. They had no way to know which prospect was bleeding: which insurer was drowning in claims complaints, which dealer was losing customers to fleet downtime, which brand had a recall pattern.

2.2 What this platform delivers
Sales radar: prioritized list of strong-signal targets (signal_strength ≥ 65) with a one-line why now and a recommended ERP module.
Tunisian market visibility gap: TN insurers/dealers score ~33 mechanically because they have zero public reviews — that opacity is itself a sales lever (TEAMWILL can offer them digital-presence tooling).
Conversational analyst: a Groq-LLaMA-3.3-70B endpoint that synthesizes the corpus into a human briefing on demand.
Briefing PDF: ReportLab "Market Intelligence Brief" — printable, board-ready.
2.3 Strategic value
Capability	Business outcome
Opportunity score 0–100	Replaces gut-feel prospecting with quantified pipeline
ERP-module recommendation per cluster	Pre-qualifies the product pitch per target
Sentiment-trend slope (declining_fast / declining / stable)	Catches insurers before the crisis hits the press
Region split (TN / EU / Global)	Supports both home-market and EU expansion narratives
RAG semantic search over 413 articles	Sales reps can answer "what's going on with AXA in Q1?" in seconds
3. Architecture Overview

┌──────────────── INGESTION ────────────────┐
│  20+ scrapers  →  RawPage table           │  HTTP (requests) + Playwright
│  RSS feeds, Reddit OAuth, NHTSA API,      │  Rate-limited 0.2–1.0 req/s
│  Trustpilot, AutoScout24, Google Places   │  UA rotation, urllib3 retry
└───────────────┬───────────────────────────┘
                ▼
┌──────────────── PARSING ──────────────────┐
│  html_cleaner → dom_extractor →           │  BeautifulSoup, trafilatura
│  schema_extractor (JSON-LD) →             │  Gemini LLM fallback (optional)
│  llm_extractor → normalizer →             │  SHA-256 + URL + 95% title sim
│  validator → deduplicator                 │
└───────────────┬───────────────────────────┘
                ▼
┌──────────────── NLP ENRICHMENT ───────────┐
│  Fine-tuned DistilBERT-multi (3-class)    │  models/sentiment-automotive-v1
│  + complaint classifier (rules)           │  + topic classifier (6 topics)
│  + keyword extractor (uni+bi-gram)        │  + BGE-base-en embeddings
└───────────────┬───────────────────────────┘
                ▼
┌──────────────── ANALYTICS ────────────────┐
│  aggregators.py  →  monthly rollups       │  by brand × origin (all/scraped/seeded)
│  clustering.py   →  KMeans k=4            │  silhouette + Davies-Bouldin
│  opportunity_scorer.py → 4-D score        │  scipy percentile + linear regression
│  rag_indexer.py  →  pgvector              │  + Mann-Kendall on sparse data
└───────────────┬───────────────────────────┘
                ▼
┌──────────────── SERVING ──────────────────┐
│  FastAPI 25+ endpoints (port 8099)        │  Pydantic v2 ConfigDict
│  React 18 + Vite + TanStack Query (5174)  │  16 pages, dark-pro design system
│  Groq LLaMA-3.3-70B analyst               │  ReportLab PDF briefings
└───────────────────────────────────────────┘
4. Data Layer
4.1 Database — 33 ORM models, PostgreSQL 14
Grouped into 7 domains:

Scraping infra (7): ScrapingTask, ScrapingRun, ScrapingError, ScraperHealthMetric, PipelineRun, PipelineStepRun, RawPage
Automotive (6): CarBrand, CarModel (with HP, torque, kWh, range), CarListing, CarPriceHistory (RANGE-partitioned by scraped_at), CarReview, ReviewSource
Insurance (5): InsuranceCompany, InsurancePolicy, InsuranceQuoteHistory (partitioned), CompetitorPricing, InsuranceReview
NLP (3): CarReviewNlp, InsuranceReviewNlp, ArticleNlpResult — store sentiment, complaint_type_id, keywords, embedding
Analytics (6): OpportunitySignal (with JSONB score_reasoning), BrandReputationScore, SentimentTrend, KpiMetric, Topic, MarketTrendArticle
ML/Discovery (5): MlClusterMetadata, MlModelMetric, SearchKeyword, Keyword, ErpVendor
Audit (1): DataQualityLog
Key conventions:

Provenance: every fact-table row carries data_origin ∈ {seeded, scraped} — analytics aggregators run 3 parallel passes (all, scraped, seeded) so the dashboard never mixes synthetic with real.
Soft-delete + timestamp mixins on entity tables.
Native PostgreSQL ENUMs via pg_enum for status fields.
Partitioning on high-volume time-series (reviews, price history) by year RANGE.
4.2 Migration chain (16 migrations, all forward-only)
350d9942b399 (initial) → analytics_tables → pipeline_step_runs → enrich_vehicle_fields → data_origin_provenance → analytics_provenance → region_field → opportunity_signals → review_partitions → source_management → search_keywords → sector_percentile → ml_clusters → ml_model_metrics → erp_vendors → rag_embeddings (vector(768)) ← HEAD

Each migration is a hardening pass: indexes on every FK, constraints, then ML-feature columns.

5. ETL & Scraping Pipeline
5.1 Scraping foundation (scrapers/)
Two abstract bases:

BaseScraper — requests.Session + connection pool + urllib3 retry (429/5xx with exponential backoff) + RateLimiter (threading.Lock + monotonic clock).
PlaywrightBaseScraper — Chromium headless, --disable-blink-features=AutomationControlled, scroll hooks for lazy-loaded SPAs.
Anti-bot:

16 modern UA strings rotated per request (Chrome/Firefox/Edge/Safari, desktop + mobile).
Per-scraper RPS budget: Trustpilot 0.2 req/s (1 every 5s), Reddit 0.98 req/s (60/min OAuth limit), RSS 0.5, NHTSA 0.5, Google Places 0.3.
Jittered exponential backoff (0.3s random) on top of urllib3 retry.
5.2 Scraper inventory (20+)
Scraper	Tech	Source	Output
trustpilot_scraper / trustpilot_insurance_scraper	Playwright	Trustpilot car & insurance reviews	904 real car + insurance reviews
car_listing_scraper	Requests	AutoScout24	83 listings
rss_news_scraper	feedparser	Motor1, InsideEVs, InsuranceJournal, BN TN, L'Économiste	413 articles
reddit_scraper	OAuth 2.0	r/CarTalk, r/insurance	Backup JSON 15 MB
nhtsa_complaints_scraper	NHTSA REST API	Vehicle complaints (no key)	Make/model/year
google_places_scraper	Places API	TN insurance/dealer reviews	Geo-tagged
newsapi_scraper / newsdata_scraper / keyword_scraper	RSS+API	Google News, Bing News	Keyword-driven
caranddriver_scraper / edmunds_scraper / reuters_scraper	Playwright	JS-heavy auto press	Articles
atlas_magazine_scraper / automobile_tn_scraper	Requests	TN-local outlets	TN-specific
5.3 Parser pipeline (parsers/automotive_pipeline.py)
8-stage batched processor (default 500 raw_pages/run):

html_cleaner — strip scripts/styles/cookies/nav/footer (BeautifulSoup + trafilatura fallback).
dom_extractor — CSS-selector heuristics in priority order (.brand, [data-brand], meta[property='article:published_time'], etc.).
schema_extractor — JSON-LD/microdata (NewsArticle, Review, Product, Organization).
map_to_schema — entity-type routing (car_review, insurance_review, market_trend_article).
llm_extractor (optional, --llm flag) — Google Gemini fallback when title or body empty; strict JSON output, max 8k chars.
normalizer — whitespace collapse, dateutil fuzzy parse, rating numeric extraction, legal-suffix strip (Inc/Ltd/SA/GmbH).
validator — quality gate: title required, body ≥ 50 chars, rating ∈ [0,5], date valid; rejects logged to data_quality_log.
deduplicator — SHA-256(brand|model|url) → URL match → 95% title SequenceMatcher similarity.
5.4 Orchestration (scripts/scheduler.py)
Master loop runs 4 stages sequentially, fail-soft:

run_scraping_tasks.py — pulls QUEUED tasks, runs scrapers
run_parser_pipeline.py --limit 500
run_nlp_pipeline.py
run_analytics.py (aggregators + opportunity scorer + clustering)
Modes: --once / --interval-hours 6 / --run-on-start. Failures in stage N do not halt stage N+1 — partial success is logged in PipelineStepRun.

5.5 Observability (observability/step_recorder.py)
Every stage writes a PipelineStepRun row: records_seen, records_processed, records_skipped, records_failed, records_inserted, processing_time_seconds, status ∈ {SUCCESS, PARTIAL, FAILED}. Status derivation:

seen=0 → SUCCESS (nothing to process is OK)
all failed → FAILED
some processed + some failed → PARTIAL
The dashboard's Operations page reads this directly.

6. NLP & Fine-Tuning Pipeline
6.1 Production sentiment model — three-tier cascade
Tier 1 (primary): Fine-tuned distilbert-base-multilingual-cased (models/sentiment-automotive-v1/)

6 layers, 768-dim, 119,547 vocab, 3-class head
Max 256 tokens
Validation: accuracy 85.27%, macro-F1 0.8353 (label_map.json)
Held-out test (Protocol 2): accuracy 84.5%, macro-F1 0.834
Multilingual = covers EN + FR (TN context)
Tier 2 (fallback): distilbert-base-uncased-finetuned-sst-2-english (binary → 3-class via 0.65 confidence threshold for neutral). Macro-F1 ≈ 0.528.

Tier 3 (degraded): Pure-Python keyword scorer (15 positive + 10 negative keywords, weighted) for OOM/no-network situations.

All tiers expose the same (label, score ∈ [-1, +1]) interface.

6.2 Fine-tuning pipeline — 4 phases
Phase 1 — Weak labeling (scripts/llm_label_reviews.py)
Annotator: Groq llama-3.3-70b-versatile
Output schema: JSON {sentiment, confidence, complaint_category, language, reasoning}
Rate budget: 5s inter-request (~12 RPM, safe under 30 RPM free tier)
Multi-key rotation: GROQ_API_KEY through GROQ_API_KEY_5/9 — auto-rotates on TPD exhaustion
Resume capability: loads already-labeled IDs at startup
Output: data/llm_labels.jsonl
Phase 2 — Neutral data import (scripts/import_yelp_neutrals.py)
The original DB had only 42 unique neutral reviews → v1/v2 collapsed to 0% neutral recall.

Fix: Stream HuggingFace yelp_review_full 3-star reviews, filter by automotive keywords, import 300 → unblocked neutral class.

Phase 3 — Stratified dataset construction (scripts/build_training_set.py)
Rating-anchored ground truth:

rating ≥ 4.5 → positive
2.5 ≤ rating ≤ 3.5 → neutral
rating ≤ 2.0 → negative
2.0 < rating < 2.5 and 3.5 < rating < 4.5 → excluded as ambiguous
Stratification: sentiment × corpus strata (e.g., positive_car, negative_insurance) split independently to preserve proportional representation.

Sampling strategy:

Split	%	Composition
Train	70%	Balanced 200/200/200 (under-sampled majority + Yelp neutral supplement)
Val	15%	Natural distribution, rating-anchored only
Test	15%	Held-out, never touched during selection
Filters: confidence ≥ 0.85, exact-text dedup, then write train_set.jsonl, val_set.jsonl, test_set.jsonl, split_report.json.

Phase 4 — Fine-tuning (scripts/finetune_sentiment.py)
Base: distilbert-base-multilingual-cased (chosen over English-only for FR/AR-Latin support)
Optimizer: AdamW, LR 2e-5, weight decay 0.01, warmup ratio 0.1
Batch: 16 train / 32 eval
Epochs: 4 with early stopping (patience 2)
Loss: Inverse-frequency weighted cross-entropy — w_c = N / (n_classes × count_c) to prevent collapse to negative-majority
Max seq len: 256
Compute: ~55 min on CPU (no GPU required)
Output: models/sentiment-automotive-v1/ with full HF checkpoint + label_map.json + training_args.bin
Phase 5 — Evaluation (scripts/evaluate_sentiment.py)
Two-protocol comparison prevents data leakage:

Protocol 1: Groq pseudo-labels on val set (sanity check vs the labeler)
Protocol 2: Rating-anchored held-out test (gold standard)
Metrics: accuracy, macro-F1, weighted-F1, per-class P/R/F1, 3×3 confusion matrix, language-stratified (EN vs FR) accuracy.

Headline result: macro-F1 jumped from 0.528 → 0.834 (+58% relative) — and neutral recall went from 0% → 86.3% (the v1/v2 failure mode).

6.3 Production inference (scripts/run_nlp_pipeline.py + nlp/nlp_pipeline.py)
Queries rows where no NlpResult exists for current model_version
Concatenates review_title + review_text (max 2000 chars)
Per-record extraction: sentiment_label, sentiment_score, top-6 topics, top-10 keywords, top-5 complaints
Inserts CarReviewNlp / InsuranceReviewNlp / ArticleNlpResult with model_version tracking
Last full pipeline run (2026-04-23): 1,500 records re-scored, 81 opportunity signals updated
6.4 Other NLP modules
Complaint classifier (nlp/complaint_classifier.py): 5 hard-coded categories — engine_issues, battery_issues, claims_delays, policy_pricing, customer_service. Substring match on cleaned text.
Topic classifier (nlp/topic_classifier.py): 6 topics — pricing, reliability, fuel economy, insurance claims, customer service, technology.
Keyword extractor: unigrams + bigrams via Counter, bigrams weighted ×1.5, top-k=10.
Text preprocessor: lowercase, alphanumeric regex, 65 English stopwords, min token length 3.
6.5 RAG layer (analytics/rag_indexer.py)
Embedding model: BAAI/bge-base-en-v1.5 (768-dim, MTEB top-class)
Storage: PostgreSQL vector(768) column on MarketTrendArticle, CarReview, InsuranceReview (added in migration a2b3c4d5e6f7)
Chunking: title + body[:700] for articles, title + body[:500] for reviews
Normalization: L2 → cosine similarity = dot product
Incremental: only embeds rows where embedding IS NULL
Retrieval: BGE encode query (with "Represent this sentence for searching relevant passages: " prefix) → pgvector cosine top-K → cross-encoder ms-marco-MiniLM-L-6-v2 rerank → return to LLM analyst
6.6 Clustering (analytics/clustering.py)
Algorithm: KMeans, k=4 (selected by elbow + silhouette over k=2..8)
Features (5): negative_pct, review_volume (standardized), avg_rating, complaint_diversity (distinct categories), sector_encoded (0=auto, 1=insurance)
Min company size: ≥5 reviews
Stability: 100 bootstrap runs aligned via Hungarian algorithm
Cluster labels (auto-assigned by distress score):
Critical Service Failures → recommend Customer Service Management ERP
Multi-Domain Operational Gaps → recommend Integrated ERP Suite
Emerging Market Entrants → recommend Digital Transformation Suite
Stable Market Leaders → recommend Advanced Analytics & Reporting
Persisted to: MlClusterMetadata (id, cluster_id, label, erp_module, color_hex, stats) + MlModelMetric (silhouette, davies_bouldin, inertia, k, n_companies, stability_json)
7. Opportunity Scorer — The Core Business Logic
analytics/opportunity_scorer.py (604 lines, the "money function").

7.1 Score composition (0–100, four dimensions)
Dimension	Weight	What it measures	Method
Article Signal	0–35	Distress signal in news/articles	RAG cosine similarity vs sector query × recency decay exp(-days_old/180), top-10 weighted sum, sector-percentile-ranked
Sentiment Trend	0–25	Negativity direction over time	Linear regression slope on monthly negative-% + degree-2 polynomial; Mann-Kendall fallback when R²<0.35
Market Presence	0–20	How visible the entity is	log(review_count) percentile rank in sector
Complaint Intensity	0–20	How nasty current sentiment is	Negative-% percentile rank in sector
Query for article signal: "{entity_name} automotive fleet management ERP operational failures recall defect breakdown"

7.2 Two-pass normalization
Pass 1: collect raw metrics for every brand/insurer (article signal, slope, review count, neg %)
Pass 2: scipy.stats.percentileofscore(kind='rank') within sector — percentile, not absolute → fair comparison
Pass 3: upsert into opportunity_signals with full JSONB score_reasoning including each dimension's percentile/raw/max — drives the dashboard's expandable "why this score" panel
7.3 Thresholds (project-locked)
strong ≥ 65 (lowered from 70 to surface Hyundai 68.9 and AXA XL 66.0)
moderate ≥ 40
weak < 40
7.4 Trend direction taxonomy
declining_fast (slope > 0.02)
declining, stable, improving
7.5 Important design choice
Negative sentiment % is used as the complaint proxy — not complaint_type_id (which only matched 14% of records and was too narrow). This is documented in CLAUDE.md as a locked decision.

7.6 Current state (2026-04-23)
81 opportunity signals computed
22 strong (≥65), 49 moderate, 10 weak
TN companies all sit at 33.0 because they have no real reviews → that visibility gap is the sales angle, by design.
8. API Layer (api/main.py)
FastAPI on port 8099 with Pydantic v2 (ConfigDict) response models. ~25 high-level routes / 66 sub-endpoints across these groups:

Group	Key endpoints	Powers
System	/, /health	Sanity checks
Brands	/api/brands, /api/brands/{id}/{models,reputation,sentiment}, /api/brands/summary	Brands + Overview pages
Reviews	/api/reviews/{car,insurance} paginated	Reviews views
Listings/Articles/Pricing	/api/listings, /api/articles, /api/competitors[/summary]	Marketplace + News pages
Analytics	/api/opportunities[/{id},/summary], /api/dashboard/summary, /api/insurance/landscape, /api/region-summary, /api/data/provenance	Opportunities, BriefingRoom, FieldIntel
Pipeline/Ops	/api/pipeline/{runs,status,quality,failures}, /api/sources/health	Operations dashboard
ML/Search	/api/ml/clusters, /api/models, /api/search	MLDashboard, search
RAG/Analyst	POST /api/rag/ask, POST /api/rag/ask/brief, GET /api/rag/explore	Analyst page (Groq LLaMA-3.3-70B)
Admin	POST /api/admin/trigger-analytics, POST /api/admin/force-refresh-sources, DELETE /api/admin/reset	Admin page
CORS: allow_origins=["*"] for dev; tighten for prod.

9. Dashboard (dashboard/src/)
React 18 + TypeScript strict + Vite + TailwindCSS + TanStack Query. Vite dev proxy → 127.0.0.1:8099. staleTime: 30000 enforced project-wide.

Page	LOC	Purpose
Overview	519	Single-shot KPIs, sparklines, recent articles
Opportunities	541	The flagship — score cards, region filter, expandable score_reasoning
Brands	455	Brand drill-down + reputation/sentiment history
InsuranceLandscape	539	Insurer profiles + policy catalog + quote history
CompanyRadar	1534	Deep entity profile w/ RAG-matched articles
Articles	338	Article feed, NLP-categorized
Listings	275	Marketplace + price histograms
Pricing	255	Insurance competitor pricing trends
MLDashboard	340	KMeans clusters, silhouette, ERP recommendations
Operations	530	Pipeline observability — gauges, error trends, SLA
Sources	732	Source registry, reliability, manual triggers
BriefingRoom	447	Executive briefing UI + PDF export
WeeklyBrief	739	Week-over-week deltas, top movers
FieldIntel	890	Regional drill-down (TN/EU/Global)
Analyst	356	Groq LLaMA conversational analyst (DM Sans premium font)
Admin	41	Pipeline triggers, reset
Component library: KpiCard, EmptyState, ErrorState, Skeleton, StatusBadge, LiveIndicator, Pagination, AskAiDrawer, AiInsightCard, RefreshDataPanel, Layout — consistent dark-pro design system per memory/DESIGN_SYSTEM.md.

10. Test Coverage (tests/, 9 suites)
Test file	Covers
test_nlp_pipeline.py	Mocked sessions, metric shapes, sentiment classification
test_sentiment_analyzer.py	Polarity scoring, label assignment
test_parser_pipeline.py	HTML → structured review
test_deduplicator.py	SHA-256 dedup
test_schema_extractor.py	JSON-LD field extraction
test_normalizer.py	Currency, dates, country names
test_validator.py	Business-rule gates
test_observability.py	StepRecorder, status derivation
test_api_operational.py	FastAPI contract tests on /api/pipeline/*, /api/sources/health
Gap: no end-to-end fine-tuning regression test, no clustering stability test.

11. Real-vs-Seeded Data Reality
This is the audit's most important honest assessment.

Asset	Real (scraped)	Seeded (synthetic)
Car reviews	2,291 (incl. 904 Trustpilot)	~1,547
Insurance reviews	2,299 mixed	most are seeded
Articles	413 RSS + 115 enrichments	0
Listings	83 AutoScout24	0
Tunisian companies	0 real reviews	All seeded
Competitor pricing	0	All seeded
Implication: The TN sales narrative ("we have visibility into the local market") is half-truthful — TN entities exist in the DB but have no public-review signal. The platform's stated framing — "the visibility gap IS the signal" — is intellectually honest but the demo will be stronger once Google Places + local-press scraping lands real reviews.

12. Strengths
Provenance discipline — data_origin flag prevents synthetic data from polluting analytics.
Fine-tuning rigor — rating-anchored stratified split, held-out test, two-protocol evaluation, class-weighted loss. Result is real (+58% macro-F1) and reproducible.
Three-tier inference cascade — fine-tuned → SST-2 → keyword. Production never goes dark.
Audit trail end-to-end — every pipeline run/step persisted, surfaced in the Operations page.
Statistical defenses — Mann-Kendall fallback when regression R² is low; bootstrap for cluster stability; sector-percentile normalization.
Clean migration chain — 16 forward-only migrations, zero rewrites of past migrations.
Resilient ETL — per-page exception isolation, urllib3 retry, rate limiting, UA rotation, dedup via SHA-256 + URL + 95% similarity.
13. Risks & Recommendations
#	Risk	Recommendation	Effort
1	TN companies have zero real reviews — biggest gap for the demo narrative	Light up google_places_scraper + automobile_tn_scraper + atlas_magazine_scraper for TN insurers/dealers; even 50 real reviews/entity changes the picture	Medium
2	All Groq keys exhausted (memory note 2026-04-23)	Add a key-pool monitor + automated rotation health check on the Operations page	Small
3	CORS allow_origins=["*"] in api/main.py	Lock to localhost:5174 in dev, env-driven in prod	Trivial
4	No CI / GitHub Actions found	Add a workflow: pytest, npm run build, alembic upgrade head smoke test	Small
5	LLM extractor is optional — if it ever becomes default, GOOGLE_API_KEY becomes a hard dep	Document in README "with vs without LLM" parser modes	Trivial
6	Repo debris: ~20 SKILL*.md files, root-level =0.26.0, =2.14.0 (pip mishaps), 24 MB car.glb, 15 MB reddit_data_backup.json	Clean before final defense — move docs to docs/, delete debris, git-LFS the binaries	Small
7	No fine-tuning regression test	Add tests/test_finetune_smoke.py — load model, run 3 fixtures, assert macro-F1 ≥ 0.80	Small
8	Reddit/RSS rotation isn't auto-scheduled	The scheduler exists but isn't running as a service — wire it as a Windows Scheduled Task or a systemd-equivalent	Small
9	No alerting layer — pipeline failures are visible only on the dashboard	Add a simple webhook (Discord/email) when PipelineStepRun.status='FAILED' for two consecutive runs	Medium
10	The 1M+ row review tables are partitioned by year, but the partition-creation is manual (one-shot in migration a1b2c3d4e5f7)	Add a yearly cron migration generator	Small
14. Recommended Next Steps (Pre-Defense Order)
Clean repo (debris removal — 30 min) so the file tree shown to jury is professional.
Run TN scraping sprint — even 3 sources × 50 reviews/insurer = real TN signal, kills the "all seeded" objection.
Re-run NLP + opportunity scorer after sprint — TN scores will move off 33.0 organically.
Generate one canonical PDF brief via pdf_exporter.py — print and bring to defense.
Add a 2-min Operations-page screencast — the live observability is your strongest "this is real software" signal.
Tighten CORS + add CI smoke test — defensive, but a question-killer in jury Q&A.
Update CLAUDE.md and the user-memory project_state.md with current data counts and Groq-key status.
15. One-Sentence Summary
You have a real, defensible, end-to-end ML system — fine-tuned multilingual sentiment with macro-F1 0.834, four-dimension percentile-normalized opportunity scoring, KMeans clustering with bootstrap stability, RAG semantic search, full pipeline observability, and a 16-page operational dashboard — and the only thing standing between this and a top-grade PFE defense is closing the real-data gap on Tunisian entities plus a small repo-hygiene + CI pass.

Want me to /schedule a one-time agent in 10 days to re-run the audit and verify items 1–6 above are closed?
