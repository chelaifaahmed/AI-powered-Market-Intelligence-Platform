# Session primer — last updated: 2026-03-25

## What was built in the last session
- Investigated Docker demo failures: car_reviews partition migration not being applied
- Found root cause: partition migration file (20260324_a1b2c3d4e5f7_add_review_partitions.py) was missing from Docker image due to stale build context (9.2KB vs expected 1.8MB)
- Verified docker-compose.yml already had correct sequential command order (no background processes, no seed_enriched_data.py)
- Attempted clean Docker rebuild with --no-cache — build took 2+ hours due to full CUDA PyTorch (~2.5GB download at ~400KB/s)
- Identified optimization: use CPU-only PyTorch in Dockerfile.api to reduce build from 2+ hours to ~5 minutes
- Set up Claude Code memory system (CLAUDE.md, memory/*.md files)

## Current state of the project
- API: running on 8099, 25+ endpoints, all returning 200
- Dashboard: 8 pages including Opportunities (flagship) and Analyst (AI chat — in progress)
- Opportunity scores: differentiated, Hyundai 68.9 (strong), AXA XL 66.0 (strong), 9 moderate, 48 weak
- PDF export: working, 2-page TEAMWILL brief
- Real data: 904 scraped reviews, 115 articles, 83 listings
- TN layer: 14 companies seeded, 0 real reviews yet
- Docker: partition migration exists but build needs CPU-only PyTorch fix (next task)
- Next task: Apply CPU-only torch fix to Dockerfile.api, then verify Docker demo

## Decisions made this session
- Use torch CPU-only build in Dockerfile.api (torch==2.1.0+cpu from pytorch.org/whl/cpu) — saves ~2.3GB and 2+ hours build time
- Make Playwright install optional in Dockerfile (only needed for live scraping, not demo)
- Background builds via Claude Code can produce stale/incomplete Docker contexts — always build synchronously

## Known issues to fix
- Docker build slow due to PyTorch CUDA packages — Fix: use torch CPU-only in Dockerfile.api
- TN companies all score 33.0 — need real TN reviews
- Bundle size 703KB — acceptable for now

## Files modified this session
- CLAUDE.md (created)
- memory/PRIMER.md (created)
- memory/DECISIONS.md (created)
- memory/CORRECTIONS.md (created)
- memory/STACK.md (created)
- memory/GIT_LOG.md (created)
- .claude/settings.json (updated)
