---
name: design_system
description: TEAMWILL Market Intelligence design system — full dark theme, colors, typography, spacing, shadows, animations, chart types, anti-patterns
type: reference
---

# TEAMWILL Market Intelligence — Design System

Generated using ui-ux-pro-max skill reasoning rules.
Query: "B2B sales intelligence dashboard fintech consulting dark professional"
Project: TEAMWILL Market Intelligence
Reference products: Palantir Gotham, Linear, Datadog

---

## 1. Product Profile

| Attribute | Value |
|-----------|-------|
| Type | B2B SaaS Dashboard — Sales Intelligence |
| Industry | Automotive + Insurance ERP consulting |
| Audience | Enterprise decision-makers, sales teams, analysts |
| Tone | Professional, data-driven, trustworthy, premium |
| Density | High (data-heavy dashboard with charts, tables, KPIs) |
| Platform | Web desktop-first (1280–1920px primary) |

---

## 2. Style Direction

**Primary style: Full Dark Professional**
- Clean, low-chrome interface — everything dark
- Reference: Palantir Gotham, Linear, Datadog
- No glassmorphism, no gradients on cards, no glow effects
- Elevation via border brightness, not shadows
- Data speaks — decoration is minimal

**Why full dark:**
- Matches premium B2B intelligence tools aesthetic
- Reduces eye strain for analysts spending hours in dashboards
- Amber/emerald/red accents pop clearly against dark surfaces
- Professional, serious tone appropriate for enterprise sales intelligence

---

## 3. Color System

### Core Palette

| Token | Hex | Usage |
|-------|-----|-------|
| `--bg-primary` | `#0A0F1E` | Full page background — deep navy |
| `--bg-surface` | `#111827` | Card backgrounds |
| `--bg-elevated` | `#1F2937` | Hover states, elevated cards |
| `--bg-input` | `#1F2937` | Search inputs, form fields |
| `--border` | `#1F2937` | Subtle borders |
| `--border-strong` | `#374151` | Visible dividers |
| `--text-primary` | `#F9FAFB` | Headings, key numbers |
| `--text-secondary` | `#9CA3AF` | Labels, descriptions |
| `--text-tertiary` | `#6B7280` | Timestamps, footnotes |

### Accent Colors

| Token | Hex | Usage |
|-------|-----|-------|
| `--accent-signal` | `#F59E0B` | Amber — active signals, actionable |
| `--accent-urgent` | `#EF4444` | Red — critical cluster, danger |
| `--accent-ok` | `#10B981` | Emerald — stable/positive |
| `--accent-info` | `#3B82F6` | Blue — informational |
| `--accent-brand` | `#6366F1` | Indigo — TEAMWILL brand |
| `--accent-ai` | `#8B5CF6` | Purple — AI features |

### Semantic Badge Colors (dark bg variants)

| State | Background | Text | Border |
|-------|-----------|------|--------|
| Signal/Amber | `#451a03` | `#F59E0B` | `#92400e` |
| Danger/Red | `#450a0a` | `#EF4444` | `#991b1b` |
| Success/Green | `#052e16` | `#10B981` | `#166534` |
| Info/Blue | `#0c1f3d` | `#3B82F6` | `#1e3a5f` |
| Brand/Indigo | `#1e1b4b` | `#6366F1` | `#312e81` |
| AI/Purple | `#2e1065` | `#8B5CF6` | `#4c1d95` |

### Chart Palette (7 distinct, colorblind-safe)

```
#6366F1  Indigo (primary series)
#8B5CF6  Violet
#EC4899  Pink
#F59E0B  Amber
#10B981  Emerald
#3B82F6  Blue
#F97316  Orange
```

---

## 4. Typography

### Font Pairing

| Role | Font | Weight | Fallback |
|------|------|--------|----------|
| **Display / Hero numbers** | Syne | 700, 800 | system-ui, sans-serif |
| **Body / UI** | DM Sans | 400, 500, 600 | system-ui, sans-serif |
| **Monospace / Data** | JetBrains Mono | 400 | monospace |

**Why Syne:** Already loaded in index.html. Bold geometric display face for hero numbers and page headlines. Creates visual hierarchy contrast with DM Sans body.

**Why DM Sans:** Mandated for premium pages. Geometric, professional, excellent legibility at small sizes.

**Why JetBrains Mono:** Tabular figures for scores, percentages, counts. Clean and readable.

### Type Scale (px)

| Token | Size | Weight | Font | Usage |
|-------|------|--------|------|-------|
| `--text-hero` | 48px+ | 800 | Syne | Hero numbers |
| `--text-display` | 32px | 700 | Syne | Page titles |
| `--text-h1` | 24px | 700 | Syne | Section titles |
| `--text-h2` | 18px | 600 | DM Sans | Card titles, section headers |
| `--text-h3` | 16px | 600 | DM Sans | Card subtitles |
| `--text-body` | 14px | 400 | DM Sans | Primary labels, nav items |
| `--text-sm` | 13px | 400 | DM Sans | Body text, descriptions |
| `--text-xs` | 12px | 500 | DM Sans | Secondary labels, captions |
| `--text-xxs` | 11px | 500 | DM Sans | Timestamps, tertiary labels |
| `--text-micro` | 10px | 500 | DM Sans | Footnotes, model quality |
| `--text-mono` | 13px | 400 | JetBrains Mono | Scores, percentages, counts |

---

## 5. Spacing Scale (4px base)

| Token | Value | Usage |
|-------|-------|-------|
| `--space-1` | 4px | Tight icon gaps |
| `--space-2` | 8px | Badge padding, small gaps |
| `--space-3` | 12px | Card inner padding (compact) |
| `--space-4` | 16px | Standard padding |
| `--space-5` | 20px | Card padding |
| `--space-6` | 24px | Section gaps |
| `--space-8` | 32px | Page padding |
| `--space-10` | 40px | Large section separators |
| `--space-12` | 48px | Page top margin |

---

## 6. Shadow System (minimal on dark)

On dark backgrounds, shadows are less visible. Use border brightness instead.

| Token | Value | Usage |
|-------|-------|-------|
| `--shadow-card` | none | Cards use border, not shadow |
| `--shadow-elevated` | `0 4px 12px rgba(0,0,0,0.3)` | Dropdown, popover |
| `--shadow-modal` | `0 8px 24px rgba(0,0,0,0.4)` | Modal overlay |

---

## 7. Border Radius

| Token | Value | Usage |
|-------|-------|-------|
| `--radius-sm` | 6px | Badges, small buttons |
| `--radius-md` | 8px | Cards, inputs |
| `--radius-lg` | 10px | Large cards |
| `--radius-xl` | 12px | Panels, modals |
| `--radius-full` | 9999px | Pills, status dots |

---

## 8. Component Patterns (Dark Theme)

### KPI Card
- Background: #111827
- Border: 1px solid #1F2937
- Border-radius: 10px
- Padding: 20px
- Hover: border-color #374151, bg #131d2e
- Number: Syne 700 28px, color #F9FAFB
- Label: DM Sans 10px 500, color #6B7280, uppercase, letter-spacing 0.15em
- Trend badge: dark semantic bg + colored text

### Data Table
- Header: DM Sans 10px 600 uppercase, color #6B7280, letter-spacing 0.1em
- Row: 13px 400, color #9CA3AF
- Row hover: bg #1F2937
- Borders: bottom 1px #1F2937 between rows
- Score column: JetBrains Mono 13px 400, color #F9FAFB

### Badge / Tag
- Padding: 2px 8px
- Border-radius: 9999px
- Font: 10px 500
- Dark bg variants (see Semantic Badge Colors above)

### Button (Ghost/Outline — primary style on dark)
- Background: transparent
- Border: 1px solid #374151
- Color: #9CA3AF
- Font: DM Sans 12px 500
- Padding: 7px 14px
- Border-radius: 6px
- Hover: border-color #6366F1, color #F9FAFB
- Active: scale(0.98)
- Transition: all 150ms ease

### Button (Primary — rare, for CTAs only)
- Background: #6366F1
- Color: white
- Font: DM Sans 13px 600
- Padding: 8px 16px
- Border-radius: 8px
- Hover: #4F46E5

---

## 9. Animation & Motion

### Principles
- Duration: 150ms for micro-interactions, 250ms for transitions, 300ms max for page elements
- Easing: ease-out for enter, ease-in for exit
- Never animate width/height — use transform + opacity only
- Max 2 animated elements per view on load
- Respect prefers-reduced-motion

### Key Animations

| Element | Animation | Duration | Easing |
|---------|-----------|----------|--------|
| Card hover | border-color + bg transition | 150ms | ease |
| Score bar fill | width 0 → score% | 600ms | ease-out |
| Page fade-in | opacity 0→1 | 200ms | ease-out |
| Stagger cards | delay 50ms per item, opacity + translateY(8px) | 250ms each | ease-out |
| Skeleton shimmer | opacity 0.4→0.8→0.4 | 1500ms | ease-in-out, infinite |
| Sidebar nav hover | background-color transition | 150ms | ease |
| Button press | scale(0.98) | 100ms | ease |

### Loading States
- Skeleton shimmer on dark: #1F2937 pulsing opacity 0.4–0.8
- Show skeleton for any load >300ms
- 3 skeleton cards for opportunity list

---

## 10. Chart Recommendations

| Data Type | Chart | Notes |
|-----------|-------|-------|
| Trend over time | Area / Line | Gradient fill, 1px stroke |
| Company comparison | Horizontal bar | Sort descending, direct labels |
| Sentiment breakdown | Stacked bar | 3 colors: positive/neutral/negative |
| Score distribution | Donut | Max 5 slices, center label |
| Cluster map | Scatter | Color by cluster |
| KPI with trend | Sparkline | No axes, just line + area fill |

### Chart Styling Rules (Dark)
- Grid lines: #1F2937
- Axis text: 11px DM Sans 500 #6B7280
- Tooltip: #111827 bg, border 1px #374151, 13px body
- No chart borders

---

## 11. Anti-Patterns to AVOID

| Never Do | Do Instead |
|----------|------------|
| Glow effects / neon shadows | Subtle border brightness |
| Gradient backgrounds on cards | Solid #111827 cards |
| ALL CAPS EVERYTHING | Uppercase only for tiny labels (10-11px) |
| Light background for content area | Full dark #0A0F1E everywhere |
| Multiple font families beyond 3 | Syne + DM Sans + JetBrains Mono only |
| Animated gradients | Static, purposeful color |
| Border-radius > 12px on cards | 8–10px |
| "SYSTEM SECURE" / "KERNEL" text | Professional labels only |
| Ping animations on status dots | Simple solid dot or gentle pulse |
| White backgrounds anywhere | Dark surfaces only |
| High-contrast neon text | Muted palette with selective amber/red pops |

---

## 12. Layout Structure

- Sidebar: 220px, bg #0A0F1E, border-right 1px solid #1F2937
- Main content: remaining width, bg #0A0F1E
- Topbar: bg #0A0F1E, border-bottom 1px solid #1F2937, height 56px
- Page padding: 32px 40px
- Everything is dark — no light surfaces

---

## Usage

Before building any page, read this file first. Apply tokens consistently.
For page-specific overrides, create `memory/design_pages/<page-name>.md`.
