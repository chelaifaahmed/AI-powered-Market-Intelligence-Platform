# TEAMWILL Platform — Full Project Handoff
**For new Claude chat session — paste this entire document**

---

## WHO I AM
Ahmed Chelaifa. Business Analytics student (IT minor), Tunisia.
PFE (final year project) for TEAMWILL — a consulting firm selling ERP to insurance companies and car dealers in Tunisia and Europe.
**~2 months until defense.**

---

## WHAT THE PROJECT IS

AI-powered Market Intelligence Platform that replaces TEAMWILL's manual sales prospection. The platform scrapes real customer reviews, applies NLP + ML clustering, and surfaces ranked ERP opportunities with business context.

**The story it tells:** "TEAMWILL opens this Monday morning and immediately knows which 3 companies to call this week, why, and what ERP module to pitch."

---

## TECH STACK

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI (port 8099), Python, SQLAlchemy |
| Database | PostgreSQL 14+ (33 tables, 15 ENUMs) |
| Frontend | React 18 + TypeScript + Vite + TailwindCSS + Recharts |
| NLP | DistilBERT SST-2 (HuggingFace) |
| ML | scikit-learn (KMeans K=4, Random Forest planned) |
| AI Chat | Groq API (llama-3.3-70b-versatile) |
| Scraping | Playwright + requests + BeautifulSoup + feedparser |

**Project path:** `C:\Users\LENOVO\Documents\WebScrapper_PFE_Antigravity`
**Node is not in PATH** — Claude Code must find npm via: `powershell -Command "& 'C:\Program Files\nodejs\npm.cmd' run build"` or similar workaround.

---

## MEMORY SYSTEM

Claude Code reads these files every session:
- `CLAUDE.md` — permanent project instructions
- `memory/PRIMER.md` — session summary
- `memory/DECISIONS.md` — architecture decisions log
- `memory/CORRECTIONS.md` — bugs fixed
- `memory/STACK.md` — quick reference commands
- `memory/DESIGN_SYSTEM.md` — design tokens and rules
- `memory/GIT_LOG.md` — auto-populated by git hook

**Always start every Claude Code prompt with:**
`Read memory/PRIMER.md, memory/DECISIONS.md, memory/DESIGN_SYSTEM.md and CLAUDE.md first.`

---

## DESIGN SYSTEM (from memory/DESIGN_SYSTEM.md)

**Style:** Full dark professional (Palantir/Linear/Datadog category)

```css
--bg-primary:     #0A0F1E  /* full page background */
--bg-surface:     #111827  /* card backgrounds */
--bg-elevated:    #1F2937  /* hover, elevated cards */
--border:         #1F2937
--border-strong:  #374151
--text-primary:   #F9FAFB
--text-secondary: #9CA3AF
--text-tertiary:  #6B7280
--accent-signal:  #F59E0B  /* amber — active signals */
--accent-urgent:  #EF4444  /* red — critical cluster */
--accent-ok:      #10B981  /* emerald — stable */
--accent-info:    #3B82F6  /* blue — info */
--accent-brand:   #6366F1  /* indigo — TEAMWILL */
--accent-ai:      #8B5CF6  /* purple — AI features */
```

**Fonts:** Syne 700/800 (headlines + big numbers) + DM Sans 400/500/600 (body) + JetBrains Mono (data values/scores)

**Spacing:** 4/8/12/16/24/32/48/64px

**Border radius:** 6px components, 10px cards, 16px panels

**Animation:** 150ms ease-out enter, 100ms ease-in exit, opacity+translateY only, never >300ms

**Anti-patterns:** No gradients on data cards, no hardcoded hex, no pie charts, no color as only signal, no animations >300ms

---

## PLATFORM STRUCTURE (4 pages)

```
/          → Weekly Brief     (ACTION: "who do I call this week?")
/company   → Company Radar    (RESEARCH: "tell me about this company")
/market    → Market Pulse     (CONTEXT: "what's happening in market?")
/analyst   → AI Analyst       (DEEP DIVE: chat with Groq)
/admin     → Admin            (Operations + Sources tabs — hidden from main nav)
```

**Sidebar (220px, #0A0F1E):**
- TEAMWILL logo + "Market Intelligence" subtitle
- 4 nav items with lucide-react icons
- Admin link at bottom (muted, smaller)
- "v2.0 · Real data only" footer text

**Old pages kept as routes but NOT in sidebar:**
/opportunities, /brands, /insurance, /listings, /sources, /operations

---

## DATA STATE (current, real scraped only)

| Dataset | Count | Source | Notes |
|---------|-------|--------|-------|
| Car reviews | ~904 | Trustpilot (real) | Hyundai, Toyota, Ford, etc. |
| Insurance reviews | ~2,054 | Trustpilot (real) | Budget Direct, NRMA, LV=, etc. |
| Market articles | ~413 | RSS feeds (real) | ERP + insurance focused |
| Car listings | 83 | AutoScout24 (real) | |
| Analyst signals | 19 | Manually seeded | TN companies, marked data_origin='analyst' |

**ALL seeded/synthetic data was deleted.** Only real scraped + analyst-sourced data remains.

**data_origin values:**
- `'scraped'` = real Trustpilot/RSS data
- `'analyst'` = market analysis based (TN companies)

---

## OPPORTUNITY SIGNALS (current)

**Total: 68 signals** (23 strong, 31 moderate, 14 weak)

**Top signals:**
1. STAR Assurances (TN) — 78 — analyst signal
2. Hyundai (EU) — 96 — scraped
3. Budget Direct (EU) — 96 — scraped
4. GAT Assurances (TN) — 74 — analyst signal
5. Ennakl Automobiles (TN) — 72 — analyst signal

**Scoring model (4 dimensions, rule-based):**
- TEAMWILL fit score: 0–40
- Sentiment trend: 0–25
- Market presence: 0–20
- Complaint intensity: 0–15

**UI badge logic:**
- `data_origin='analyst'` → purple "ANALYST SIGNAL" badge
- `data_origin='scraped'` → green "VERIFIED DATA" badge

---

## ML MODELS

### Model 1 — KMeans Clustering ✅ BUILT
- K=4, silhouette=0.4603, 38 companies clustered
- Features: negative_pct, review_volume, avg_rating, complaint_diversity, sector_encoded
- Results stored in car_brands.cluster_id + insurance_companies.cluster_id
- Table: ml_cluster_metadata

**4 Clusters:**
| Cluster | Label | ERP Module | Color |
|---------|-------|-----------|-------|
| 0 | Multi-Domain Operational Gaps | Integrated ERP Suite | Orange |
| 1 | Critical Service Failures | Customer Service Management | Red |
| 2 | Stable Market Leaders | Advanced Analytics | Green |
| 3 | Emerging Market Entrants | Digital Transformation | Yellow |

**API endpoints:**
- GET /api/ml/clusters
- GET /api/ml/companies

### Model 2 — Random Forest ⬜ PLANNED (Week 3)
- Will predict ERP opportunity probability
- Replace rule-based scoring with trained model
- Academic metrics: accuracy, precision, recall, feature importance

---

## WHAT'S BUILT (pages status)

| Page | Status | Notes |
|------|--------|-------|
| Weekly Brief (/) | ✅ Built | Dark theme, priority cards, market sidebar, AI brief sentence, data origin badges |
| Company Radar (/company) | ⬜ Placeholder | Next to build |
| Market Pulse (/market) | ⚠️ Old Overview | Needs redesign |
| AI Analyst (/analyst) | ✅ Working | Groq chat, live DB context |
| Admin (/admin) | ✅ Built | Operations + Sources tabs |

---

## WEEKLY BRIEF — What's working

- Dark #0A0F1E full page background
- Priority cards with: rank, company name, sector/region badges, WHY NOW text, PITCH (erp_module), score with percentile, cluster badge, View Profile + Export Brief buttons
- Left accent bar color = urgency (red/amber/blue/gray)
- Market sidebar: sector temperature bars, top complaint, latest articles, mini stats
- AI-generated brief sentence from Groq (top right)
- "34 SIGNALS ACTIVE" live badge
- Skeleton loading states
- data_origin badges (purple analyst / green verified)
- Collapsible "Show more signals" below top 3
- Build: 0 TypeScript errors, 877KB bundle

---

## COMPANY RADAR — Design spec (next to build)

Layout:
```
[SEARCH BAR — full width autocomplete]

[COMPANY HEADER — name, sector, region, score, cluster, ERP recommendation]

[2-column grid]
Left:                          Right:
- What customers say           - Sentiment trend chart
- Review count + negative %    - "Declining since Aug 2025"

[TOP COMPLAINTS — horizontal bar chart, insight-titled]
[WHY THIS IS AN ERP OPPORTUNITY — AI-generated paragraph]
[WHAT TO PITCH — primary + secondary ERP modules]
[REAL CUSTOMER QUOTES — 3 actual review excerpts]
[Export Brief PDF] [Ask AI about this company →]
```

Key rules:
- Search bar is the hero — first thing you see
- One continuous scroll, no tabs
- "Ask AI" button pre-fills analyst chat with company context
- All section titles state INSIGHT not data type
- Click any company from Weekly Brief → navigates to /company?id=X

---

## CRITICAL DECISIONS (never reverse these)

| Decision | Choice | Reason |
|----------|--------|--------|
| Database | PostgreSQL — stay | Complex joins, JSONB, no migration |
| Sentiment proxy | sentiment_label='NEGATIVE' not complaint_type_id | 46-80% match vs 14% |
| Strong signal threshold | 65 (not 70) | Hyundai 68.9 and AXA XL 66.0 are real signals |
| LLM | Groq llama-3.3-70b | Free, 2s response, replaced Gemini/Anthropic |
| ML framework | scikit-learn | Matches curriculum |
| 3D car viewer | Abandoned forever | R3F/Vite reconciler conflict, not fixable |
| Design | Full dark #0A0F1E | Professional B2B intelligence tool |
| TN company data | data_origin='analyst' | Honest about source — no fake scraping |
| Node in PATH | Not available in shell | Use PowerShell workaround for npm |

---

## KNOWN ISSUES

| Issue | Status | Plan |
|-------|--------|------|
| TN companies have no Trustpilot reviews | Mitigated with analyst signals | Keep monitoring |
| Google Maps scraper blocked by Google | Known — needs Playwright | Week 4 improvement |
| Docker: CUDA PyTorch 2.5GB | Deferred | Week 6: CPU-only torch wheel |
| Sync DB queries in async FastAPI | Low priority | Post-defense |
| KMeans silhouette 0.46 (moderate) | Acceptable | Noted in defense script |

---

## SCHOOL REQUIREMENTS STATUS

| Requirement | Status | Evidence |
|-------------|--------|---------|
| ML model with measurable accuracy | ✅ KMeans done, RF planned | Silhouette 0.46, elbow curve |
| Business insights from data | ✅ 68 opportunity signals | Weekly Brief page |
| Working application | ✅ Full stack running | Live demo ready |
| Written methodology report | ⬜ Planned Week 6 | |

---

## NEXT STEPS (in order)

1. **Company Radar page** — most important missing page
2. **Random Forest classifier** — ML Model 2 (school requirement)
3. **Market Pulse redesign** — replace old Overview
4. **ML Insights page** — elbow curve, silhouette, RF accuracy
5. **Insurance Landscape** — Tunisia deep dive for TEAMWILL
6. **Defense prep** — mock jury, script, README

---

## DEFENSE STORY (15 min)

1. (0-2min) Problem: TEAMWILL prospects manually
2. (2-5min) Data: 4,300+ real reviews, 413 articles, pipeline
3. (5-9min) ML: KMeans segments market → ERP modules. RF predicts probability.
4. (9-12min) Demo: Weekly Brief → Company Radar → AI Analyst
5. (12-15min) Value: 68 active signals, replaces weeks of prospection

**Jury Q&A prep:**
- "Why KMeans?" → Interpretable clusters, elbow justified K=4
- "DistilBERT on car reviews?" → Domain shift acknowledged, still 46-80% signal match
- "Is scraping legal?" → Academic use, rate-limited, fair use research
- "TN company data?" → Analyst-sourced, clearly labeled, honest methodology

---

## HOW TO START A CLAUDE CODE SESSION

Always begin with:
```
Read memory/PRIMER.md, memory/DECISIONS.md, 
memory/DESIGN_SYSTEM.md and CLAUDE.md first.
Then read /mnt/skills/public/frontend-design/SKILL.md.
```

Skills available in project (uploaded by user):
- SKILL(11).md — website-structure
- SKILL(12).md — designing-beautiful-websites
- SKILL(13).md — (frontend skill)
- SKILL(14).md — data-visualization
- SKILL(15).md — ui-ux-pro-max (reference only, scripts not installed)