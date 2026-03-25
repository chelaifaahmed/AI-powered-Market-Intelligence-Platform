# Corrections log

## 2026-03-21 — Pricing page filters broken
Bug: Filter dropdowns existed in UI but never passed params to API. Query always returned unfiltered results.
Fix: Added coverage_type and region params to API endpoint and passed filter state to queryFn in Pricing.tsx.

## 2026-03-21 — Vite proxy wrong port
Bug: vite.config.ts proxy pointed to port 8000, API was on 8099. Dev server API calls all failed.
Fix: Updated proxy target to http://127.0.0.1:8099

## 2026-03-21 — Migration revision collision
Bug: add_region_field migration had duplicate revision ID
Fix: Revised to b2c3d4e5f6a7, chain validated

## 2026-03-21 — generateBriefing double "market"
Bug: "in the tracked market market" text duplication
Fix: regionLabel now appends " market" itself, removed duplicate from template string

## 2026-03-21 — .gitignore UTF-16 encoded
Bug: .gitignore was UTF-16 LE, not UTF-8
Fix: Rewrote as UTF-8 with complete exclusion list

## 2026-03-25 — Docker partition migration missing from image
Bug: car_reviews partition migration (a1b2c3d4e5f7) was not in Docker image. Alembic stopped at c4d5e6f7a8b9, seed scripts failed with "no partition of relation car_reviews found for row".
Root cause: Background docker build captured only 9.2KB of build context (stale snapshot). Synchronous rebuild captured correct 1.8MB context.
Fix: Always build Docker images synchronously (not via background tasks).
