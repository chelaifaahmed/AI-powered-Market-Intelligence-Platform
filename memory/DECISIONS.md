# Architectural decisions log

## 2026-03-21 — Opportunity scorer complaint signal
Decision: Use sentiment_label='NEGATIVE' as complaint proxy instead of complaint_type_id IS NOT NULL
Reason: complaint_type_id only matched 14% of reviews. Negative sentiment matched 46-80% — much more signal.
Impact: Scores changed from flat 57.0 to differentiated (Hyundai 68.9, Honda 62.5, etc.)

## 2026-03-21 — Strong signal threshold
Decision: Lowered from 70 to 65
Reason: Hyundai at 68.9 and AXA XL at 66.0 are genuine strong signals — threshold of 70 was too conservative.
Impact: strong_signals went from 0 to 2

## 2026-03-21 — Tunisia visibility gap as signal
Decision: TN companies scoring 33.0 is intentional behavior
Reason: No online review presence IS the signal — companies without digital feedback loops are TEAMWILL's target market.
Impact: Briefing narrative explains this correctly.

## 2026-03-21 — Seeded data isolation
Decision: Never use seeded data in opportunity scoring analytics without provenance filter
Reason: Seeded data inflates scores artificially. Real data: 904 scraped reviews. Rest is synthetic.

## 2026-03-25 — CPU-only PyTorch for Docker
Decision: Use torch CPU-only build in Dockerfile.api instead of full CUDA version
Reason: Full CUDA PyTorch downloads ~2.5GB of GPU libraries unnecessary for CPU-only inference in Docker demo. CPU-only build is ~200MB, reducing build time from 2+ hours to ~5 minutes.
Impact: Docker image size drops from ~10.5GB to ~4-5GB, build time drops dramatically.

## 2026-03-25 — Playwright optional in Docker
Decision: Make Playwright install non-fatal in Dockerfile.api (|| echo WARNING)
Reason: Playwright is only needed for live scraping, not for the demo API. If chromium install fails, API still works for seeded data demo.
