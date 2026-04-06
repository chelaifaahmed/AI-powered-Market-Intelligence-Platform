# Session primer — last updated: 2026-04-06

## What was built in the last session
- TN DATA GAP FIX: Added analyst-sourced signals for 19 Tunisian companies (12 insurers + 7 car dealers)
- NEW COMPANIES: COMAR, BH Assurance, ASTREE, AMI (insurance); AutoStar, Tractafric (dealers); Covea (EU)
- ANALYST SIGNALS: 19 TN signals seeded with data_origin='analyst' in score_reasoning JSONB
- SCORER UPDATED: _upsert_signal() preserves analyst signals when computed score is lower
- GOOGLE MAPS SCRAPER: Created scrapers/google_maps_scraper.py + google_maps_signals table (Google blocks plain HTTP — needs Playwright)
- OPPORTUNITY SCORER: 68 signals (23 strong, 31 moderate, 14 weak) — up from 59
- WEEKLY BRIEF: Added data origin badges ("ANALYST SIGNAL" purple / "VERIFIED DATA" green) + analyst why_text/erp_module
- TN companies now appear in top 25: STAR 78, GAT 74, Ennakl 72, COMAR 71

## Current state of the project
- API: running on 8099, 25+ endpoints, all returning 200
- Dashboard: 12 pages total, 4 in sidebar + 1 admin + hidden routes
- Design: Full dark professional (#0A0F1E everywhere) — Syne display, DM Sans body, JetBrains Mono data
- WeeklyBrief: rebuilt from scratch with priority target cards, animated score bars, AI brief, market sidebar
- DESIGN_SYSTEM.md at memory/DESIGN_SYSTEM.md — read before every frontend build
- Sidebar: 4 main items (Weekly Brief, Company Radar, Market Pulse, AI Analyst) + Admin at bottom
- Admin page: tabs for Operations + Sources (consolidates system pages)
- Build: clean (0 TS errors, tsc -b exits 0, vite build exits 0)
- Bundle: 876KB total (no 3D dependencies)
- **PLATFORM IS 100% REAL DATA** (scraped from Trustpilot, AutoScout24, RSS feeds, TN institutional sites)
- Car reviews: 2,291 (all scraped, all NLP-processed)
- Insurance reviews: 2,054 (all scraped, all NLP-processed)
- Market articles: 413 (all scraped, 95 TN-specific)
- Car listings: 83 (all scraped)
- Opportunity signals: 68 (23 strong, 31 moderate, 14 weak)
- Top opportunities: Budget Direct 96, Hyundai 96, Subaru 96, Tesla 95, NRMA 91, Toyota 91
- TN top signals: STAR 78, GAT 74, Ennakl 72, COMAR 71, Maghrebia 69, Artes 68 (all analyst-sourced)
- Car brands: 33 | Insurance companies: 33
- ERP vendors: 10 (seeded — SAP, Oracle, Guidewire, Odoo, etc.)
- Search keywords: 13 active (12 ERP-specific + 1 TN insurance)
- RSS feeds: 14 configured (6 automotive, 3 TN, 2 insurance, 2 fleet, 1 EV)
- Competitor pricings: 0 (all were seeded, no real source yet)
- ML clusters: 4 (K=4, silhouette=0.4603, 38 companies):
  - Multi-Domain Operational Gaps (15): Fiat, Land Rover, Ford, Honda, Hyundai, Subaru, Toyota, Kia, Tesla, Mazda, Porsche, Chevrolet, Mercedes, Volvo, Nissan
  - Critical Service Failures (9): Zurich, Progressive, RSA, Intact, Budget Direct, State Farm, GEICO, Allstate, AXA
  - Stable Market Leaders (7): Direct Line, Admiral, LV=, NRMA, Hastings Direct, Churchill, Aviva
  - Emerging Market Entrants (7): Audi, Jeep, Renault, BMW, MAIF, Generali, Allianz
- TN layer: 20 companies (12 insurers + 8 dealers), 95 TN articles, 19 analyst signals (no TN reviews — insurers not on Trustpilot)
- google_maps_signals table: created, 19 records (all N/A ratings — Google blocks plain HTTP scraping)
- PDF export: working, 2-page TEAMWILL brief
- Docker: partition migration exists but build needs CPU-only PyTorch fix
- ML Dashboard: Live at `/ml-intelligence` (clusters active)
- Sources page: all counts dynamic (no hardcoded values)
- Company Radar page built at /company. 3 new endpoints: GET /api/search/companies, GET /api/company/car/{id}, GET /api/company/insurance/{id}. Page has 9 sections: search hero, company header, why-now banner, diagnosis box, stats+trend chart, complaints bar chart, pitch cards, real customer quotes, action buttons. Weekly Brief "View Profile" navigates to Company Radar with type+id params.
- Next tasks: Build ERP Vendors dashboard page, add competitor pricing source, refine Atlas Magazine/CGA parsers

## Route mapping
Sidebar routes:
- / → WeeklyBrief (editorial magazine layout, renamed from BriefingRoom)
- /company → CompanyRadar (full pre-call sales intelligence dossier)
- /market → Overview (Market Pulse)
- /analyst → Analyst (AI Analyst)
- /admin → Admin (tabs: Operations + Sources)

Hidden routes (not in sidebar, still accessible):
- /opportunities → Opportunities
- /brands → Brands
- /insurance → InsuranceLandscape
- /listings → Listings
- /pricing → Pricing
- /articles → Articles
- /operations → Operations
- /sources → Sources
- /ml-intelligence → MLDashboard
- /overview → redirects to /market

## Known issues to fix
- npm/node not in PATH for Claude Code shell — use Playwright node: /c/Users/LENOVO/AppData/Local/ms-playwright-go/1.50.1/node.exe
- Do NOT attempt Three.js or R3F in this project (incompatible with Vite setup)
- Docker build slow due to PyTorch CUDA packages — Fix: use torch CPU-only in Dockerfile.api
- TN companies scored 17.0 from reviews — now have analyst signals (STAR 78, GAT 74, etc.) that are preserved by scorer
- Syne font link in dashboard/index.html (used by BriefingRoom)
- car.glb still in dashboard/public/ — can be cleaned up (no longer used)
- Vite chunk size warning at 768KB — acceptable, no code-splitting needed
- Atlas Magazine parser returns 0 articles — may need client-side rendering investigation
- CGA returns articles but all filtered — content is administrative French, not insurance-specific enough

## Files modified this session
- memory/PRIMER.md (updated with real data baseline)
- memory/DECISIONS.md (updated with pipeline re-run results)
- memory/CORRECTIONS.md (updated with real data migration note)
