import { useState, useEffect, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import {
  Target,
  TrendingUp,
  Eye,
  AlertTriangle,
  HelpCircle,
  X,
  ChevronDown,
  ChevronUp,
  ArrowUp,
  ArrowDown,
  Minus,
  ExternalLink,
} from "lucide-react";
import clsx from "clsx";
import { api } from "../api/client";
import type { V2Opportunity, V2DataQuality, V2Evidence, V2EvidenceItem, V2ErpMatch } from "../api/client";
import ErrorState from "../components/ErrorState";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const TIER_META: Record<string, { label: string; color: string; bg: string; border: string; dot: string }> = {
  engage:              { label: "Engage",              color: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/30", dot: "bg-emerald-400" },
  develop:             { label: "Develop",             color: "text-blue-400",    bg: "bg-blue-500/10",    border: "border-blue-500/30",    dot: "bg-blue-400"    },
  watch:               { label: "Watch",               color: "text-amber-400",   bg: "bg-amber-500/10",   border: "border-amber-500/30",   dot: "bg-amber-400"   },
  needs_investigation: { label: "Investigate",         color: "text-slate-400",   bg: "bg-slate-800/60",   border: "border-slate-700",      dot: "bg-slate-500"   },
};

const EV_META: Record<string, { label: string; color: string }> = {
  high:   { label: "High",   color: "text-emerald-400" },
  medium: { label: "Medium", color: "text-blue-400"    },
  low:    { label: "Low",    color: "text-amber-400"   },
  thin:   { label: "Thin",   color: "text-slate-500"   },
};

// Map V1 signal_strength → a comparable tier name for mover detection
const V1_TO_TIER: Record<string, string> = {
  strong:   "engage",
  moderate: "develop",
  weak:     "watch",
};

const TIER_ORDER: Record<string, number> = { engage: 4, develop: 3, watch: 2, needs_investigation: 1 };

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function tierBadge(tier: string | null) {
  const m = TIER_META[tier ?? ""] ?? TIER_META.needs_investigation;
  return (
    <span className={clsx("inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase tracking-widest border", m.bg, m.border, m.color)}>
      <span className={clsx("w-1.5 h-1.5 rounded-full", m.dot)} />
      {m.label}
    </span>
  );
}

function evBadge(dq: V2DataQuality | undefined) {
  if (!dq) return null;
  const m = EV_META[dq.evidence_strength] ?? EV_META.thin;
  return (
    <span className={clsx("text-[9px] font-black uppercase tracking-widest", m.color)} title={`ev: ${dq.evidence_strength} | ${dq.scraped_review_count} reviews · ${dq.scraped_action_signal_count} actions · ${dq.scraped_tech_stack_count} tech`}>
      {m.label}
    </span>
  );
}

function axisScore(v: number | null | undefined) {
  if (v == null) return <span className="text-slate-600 text-xs">—</span>;
  const color = v >= 70 ? "text-emerald-400" : v >= 40 ? "text-amber-400" : "text-slate-500";
  return <span className={clsx("font-mono text-xs font-bold tabular-nums", color)}>{Math.round(v)}</span>;
}

function moverIcon(v1Tier: string, v2Tier: string | null) {
  if (!v2Tier) return null;
  const v1r = TIER_ORDER[V1_TO_TIER[v1Tier] ?? "watch"] ?? 2;
  const v2r = TIER_ORDER[v2Tier] ?? 2;
  if (v2r > v1r) return <ArrowUp className="w-3 h-3 text-emerald-400" />;
  if (v2r < v1r) return <ArrowDown className="w-3 h-3 text-red-400" />;
  return <Minus className="w-3 h-3 text-slate-600" />;
}

function useAnimatedCount(target: number, duration = 700): number {
  const [value, setValue] = useState(0);
  useEffect(() => {
    if (target === 0) { setValue(0); return; }
    const start = performance.now();
    let frame: number;
    const tick = (now: number) => {
      const t = Math.min((now - start) / duration, 1);
      setValue(Math.round((1 - Math.pow(1 - t, 3)) * target));
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, duration]);
  return value;
}

// ---------------------------------------------------------------------------
// KPI card
// ---------------------------------------------------------------------------

function TierKpi({ tier, count, loading }: { tier: string; count: number; loading: boolean }) {
  const m = TIER_META[tier] ?? TIER_META.needs_investigation;
  const animated = useAnimatedCount(count);
  if (loading) return <div className="h-28 bg-slate-900 border border-slate-800 rounded-xl animate-pulse" />;
  return (
    <div className={clsx("rounded-xl border p-5 relative overflow-hidden group transition-all duration-300", m.bg, m.border)}>
      <div className="relative z-10">
        <div className={clsx("text-[9px] font-black uppercase tracking-[0.18em] mb-3", m.color)}>{m.label}</div>
        <div className={clsx("text-4xl font-black font-mono tracking-tighter", m.color)}>{animated}</div>
        <div className="text-[9px] uppercase tracking-widest text-slate-600 mt-1">entities</div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Movers widget
// ---------------------------------------------------------------------------

function MoversWidget({ items }: { items: V2Opportunity[] }) {
  const movers = items.filter((o) => {
    if (!o.v2_tier) return false;
    const v1r = TIER_ORDER[V1_TO_TIER[o.v1_signal_strength] ?? "watch"] ?? 2;
    const v2r = TIER_ORDER[o.v2_tier] ?? 2;
    return v1r !== v2r;
  });

  const upgraded   = movers.filter((o) => (TIER_ORDER[o.v2_tier!] ?? 2) > (TIER_ORDER[V1_TO_TIER[o.v1_signal_strength] ?? "watch"] ?? 2));
  const downgraded = movers.filter((o) => (TIER_ORDER[o.v2_tier!] ?? 2) < (TIER_ORDER[V1_TO_TIER[o.v1_signal_strength] ?? "watch"] ?? 2));

  if (movers.length === 0) return null;

  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5">
      <div className="flex items-center gap-2 mb-4">
        <TrendingUp className="w-4 h-4 text-brand-400" />
        <span className="text-[10px] font-black uppercase tracking-widest text-slate-400">
          V1 → V2 Movers · {movers.length} entity changes
        </span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {upgraded.length > 0 && (
          <div>
            <div className="flex items-center gap-1.5 mb-2">
              <ArrowUp className="w-3 h-3 text-emerald-400" />
              <span className="text-[9px] font-black uppercase tracking-widest text-emerald-400">Upgraded ({upgraded.length})</span>
            </div>
            <div className="space-y-1.5">
              {upgraded.map((o) => (
                <div key={o.entity_id} className="flex items-center justify-between text-xs">
                  <span className="text-slate-300 truncate max-w-[160px]">{o.entity_name}</span>
                  <div className="flex items-center gap-1.5 flex-shrink-0">
                    <span className="text-slate-600 text-[10px] capitalize">{V1_TO_TIER[o.v1_signal_strength] ?? o.v1_signal_strength}</span>
                    <span className="text-slate-600">→</span>
                    {tierBadge(o.v2_tier)}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
        {downgraded.length > 0 && (
          <div>
            <div className="flex items-center gap-1.5 mb-2">
              <ArrowDown className="w-3 h-3 text-red-400" />
              <span className="text-[9px] font-black uppercase tracking-widest text-red-400">Downgraded ({downgraded.length})</span>
            </div>
            <div className="space-y-1.5">
              {downgraded.map((o) => (
                <div key={o.entity_id} className="flex items-center justify-between text-xs">
                  <span className="text-slate-300 truncate max-w-[160px]">{o.entity_name}</span>
                  <div className="flex items-center gap-1.5 flex-shrink-0">
                    <span className="text-slate-600 text-[10px] capitalize">{V1_TO_TIER[o.v1_signal_strength] ?? o.v1_signal_strength}</span>
                    <span className="text-slate-600">→</span>
                    {tierBadge(o.v2_tier)}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Evidence helpers
// ---------------------------------------------------------------------------

function domainOf(url: string | null): string | null {
  if (!url) return null;
  try { return new URL(url).hostname.replace(/^www\./, ""); }
  catch { return null; }
}

const TAG_STYLE: Record<string, string> = {
  penalty:        "text-red-400 bg-red-500/10 border-red-500/20",
  bonus:          "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
  action:         "text-blue-400 bg-blue-500/10 border-blue-500/20",
  pain:           "text-amber-400 bg-amber-500/10 border-amber-500/20",
  article:        "text-purple-400 bg-purple-500/10 border-purple-500/20",
  erp_match:      "text-indigo-400 bg-indigo-500/10 border-indigo-500/20",
  profile:        "text-slate-400 bg-slate-800/60 border-slate-700",
  profile_source: "text-cyan-400 bg-cyan-500/10 border-cyan-500/20",
  neutral:        "text-slate-400 bg-slate-800/40 border-slate-700",
};

function EvidenceRow({ item }: { item: V2EvidenceItem }) {
  const style = TAG_STYLE[item.tag ?? "neutral"] ?? TAG_STYLE.neutral;
  const domain = domainOf(item.source_url);
  return (
    <div className={clsx("rounded-lg border p-3 text-xs", style)}>
      <div className="flex items-start justify-between gap-2">
        <span className="font-semibold leading-snug flex-1">{item.label}</span>
        {item.source_url && (
          <a
            href={item.source_url}
            target="_blank"
            rel="noreferrer"
            className="flex-shrink-0 opacity-60 hover:opacity-100 transition-opacity"
            onClick={(ev) => ev.stopPropagation()}
          >
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        )}
      </div>
      {item.detail && item.detail !== item.label && (
        <p className="mt-1 text-[10px] opacity-70 leading-snug">{item.detail}</p>
      )}
      <div className="flex items-center gap-2 mt-1.5 flex-wrap">
        {domain && <span className="text-[9px] opacity-50 font-mono">{domain}</span>}
        {item.date && <span className="text-[9px] opacity-50">{item.date.slice(0, 10)}</span>}
        {item.confidence && (
          <span className="text-[9px] uppercase tracking-widest opacity-60">{item.confidence}</span>
        )}
      </div>
    </div>
  );
}

function EvidenceSection({
  title, items, emptyMsg,
}: { title: string; items: V2EvidenceItem[]; emptyMsg: string }) {
  const [open, setOpen] = useState(false);
  if (items.length === 0) {
    return (
      <div className="mt-2 text-[10px] text-slate-600 italic">{emptyMsg}</div>
    );
  }
  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 text-[9px] font-black uppercase tracking-widest text-slate-500 hover:text-slate-300 transition-colors"
      >
        {open ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        {title} · {items.length}
      </button>
      {open && (
        <div className="mt-2 space-y-2">
          {items.map((item, i) => <EvidenceRow key={i} item={item} />)}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// ERP catalog match block
// ---------------------------------------------------------------------------

const REL_DOTS = (score: number) =>
  Array.from({ length: 5 }, (_, i) => (
    <span
      key={i}
      className={clsx("inline-block w-2 h-2 rounded-full", i < score ? "bg-indigo-400" : "bg-slate-700")}
    />
  ));

function ErpCatalogCard({ m }: { m: V2ErpMatch }) {
  const [expanded, setExpanded] = useState(false);

  const toStringList = (v: unknown): string[] =>
    Array.isArray(v) ? (v as string[]) : typeof v === "string" ? v.split(",") : [];
  const industries = toStringList(m.industries_strong_in);
  const modules    = toStringList(m.key_modules);
  const customers  = toStringList(m.notable_customers);

  return (
    <div className="rounded-lg border border-indigo-500/20 bg-indigo-500/5 text-xs overflow-hidden">
      {/* Summary row — always visible */}
      <div className="p-3">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-1.5 min-w-0">
            <span className="text-emerald-400 font-black text-sm leading-none flex-shrink-0">✓</span>
            <div className="min-w-0">
              <span className="font-bold text-slate-100">{m.erp_name}</span>
              <span className="text-slate-500 ml-1.5 text-[10px]">{m.vendor}</span>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <div className="flex items-center gap-0.5" title={`TEAMWILL relevance: ${m.relevance_score}/5`}>
              {REL_DOTS(m.relevance_score)}
            </div>
            <button
              onClick={() => setExpanded((v) => !v)}
              className="text-[9px] font-black uppercase tracking-widest text-indigo-400 hover:text-indigo-300 transition-colors flex items-center gap-0.5"
            >
              {expanded ? "hide" : "details"}
              {expanded ? <ChevronUp className="w-2.5 h-2.5" /> : <ChevronDown className="w-2.5 h-2.5" />}
            </button>
          </div>
        </div>
        <p className="mt-1.5 text-[10px] text-slate-400 leading-snug">{m.match_source}</p>
        <div className="flex items-center gap-3 mt-1.5 flex-wrap">
          <span className="text-[9px] text-slate-600">
            Automotive fit: <span className="text-slate-400 font-mono">{m.automotive_fit_score}/10</span>
          </span>
          <span className="text-[9px] text-slate-600">
            Insurance fit: <span className="text-slate-400 font-mono">{m.insurance_fit_score}/10</span>
          </span>
          <span className="text-[9px] text-slate-600">
            TEAMWILL relevance: <span className="text-indigo-400 font-mono">{m.relevance_score}/5</span>
          </span>
        </div>
      </div>

      {/* Expanded catalog detail */}
      {expanded && (
        <div className="border-t border-indigo-500/15 px-3 pb-3 pt-2.5 space-y-3 bg-slate-950/50">
          {/* Industries served */}
          {industries.length > 0 && (
            <div>
              <div className="text-[9px] font-black uppercase tracking-widest text-slate-500 mb-1.5">Industries served</div>
              <div className="flex flex-wrap gap-1">
                {industries.map((ind: string, i: number) => (
                  <span key={i} className="text-[9px] bg-slate-800 text-slate-300 px-1.5 py-0.5 rounded">
                    {ind.trim()}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Key modules */}
          {modules.length > 0 && (
            <div>
              <div className="text-[9px] font-black uppercase tracking-widest text-slate-500 mb-1.5">Key modules</div>
              <div className="flex flex-wrap gap-1">
                {modules.map((mod: string, i: number) => (
                  <span key={i} className="text-[9px] bg-indigo-900/40 text-indigo-300 border border-indigo-700/30 px-1.5 py-0.5 rounded font-mono">
                    {mod.trim()}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Notable customers */}
          {customers.length > 0 && (
            <div>
              <div className="text-[9px] font-black uppercase tracking-widest text-slate-500 mb-1.5">Notable customers</div>
              <div className="flex flex-wrap gap-1">
                {customers.map((c: string, i: number) => (
                  <span key={i} className="text-[9px] bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded">
                    {c.trim()}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* MENA adoption + top pros */}
          <div className="grid grid-cols-2 gap-2">
            {m.mena_africa_adoption && (
              <div className="bg-slate-900 rounded p-2 border border-slate-800">
                <div className="text-[9px] font-black uppercase tracking-widest text-slate-500 mb-0.5">MENA/Africa adoption</div>
                <div className="text-[10px] text-slate-300">{typeof m.mena_africa_adoption === 'string' ? m.mena_africa_adoption : JSON.stringify(m.mena_africa_adoption)}</div>
              </div>
            )}
            {m.top_pros && (
              <div className="bg-slate-900 rounded p-2 border border-slate-800 col-span-2">
                <div className="text-[9px] font-black uppercase tracking-widest text-slate-500 mb-0.5">Top strengths</div>
                <p className="text-[10px] text-slate-400 leading-snug line-clamp-3">{typeof m.top_pros === 'string' ? m.top_pros : JSON.stringify(m.top_pros)}</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function ErpCatalogMatchBlock({ matches }: { matches: V2ErpMatch[] }) {
  const [open, setOpen] = useState(true);
  if (matches.length === 0) {
    return (
      <div className="mt-2 text-[10px] text-slate-600 italic">
        No ERP catalog entries matched this entity&apos;s sub-segment.
      </div>
    );
  }
  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 text-[9px] font-black uppercase tracking-widest text-slate-500 hover:text-slate-300 transition-colors"
      >
        {open ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        ERP catalog match · {matches.length}
      </button>
      {open && (
        <div className="mt-2 space-y-2">
          {matches.map((m) => <ErpCatalogCard key={m.erp_name} m={m} />)}
          {/* Sourcing footnote — no catalog_source column in DB */}
          <p className="text-[9px] text-slate-700 leading-relaxed pt-1 border-t border-slate-800/60 mt-2">
            Catalog data sourced from Gartner Peer Insights, G2.com, Capterra, and vendor case studies.
            See{" "}
            <span className="text-slate-500 font-mono">claude_methodology_scrapping_summary.md</span>
            {" "}for full sourcing.
          </p>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// ERP profile sources — collapsible list of URL links from company_profile
// ---------------------------------------------------------------------------

function ErpProfileSources({ urls }: { urls: string[] }) {
  const [open, setOpen] = useState(false);
  if (urls.length === 0) {
    return (
      <div className="mt-2 text-[10px] text-slate-600 italic">
        Profile sources not yet documented for this entity.
      </div>
    );
  }
  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 text-[9px] font-black uppercase tracking-widest text-slate-500 hover:text-slate-300 transition-colors"
      >
        {open ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        Company profile sources · {urls.length}
      </button>
      {open && (
        <>
          <p className="mt-1.5 text-[10px] text-slate-600 leading-relaxed italic">
            Articles, LinkedIn, and reports that establish industry, parent group, and geographic footprint.
          </p>
          <div className="mt-2 space-y-2">
            {urls.map((url, i) => {
              const domain = (() => {
                try { return new URL(url).hostname.replace(/^www\./, ""); }
                catch { return url; }
              })();
              const item: V2EvidenceItem = {
                label: domain,
                detail: "Source documenting industry, parent company, or geographic footprint.",
                source_url: url,
                source_name: null,
                date: null,
                confidence: null,
                tag: "profile_source",
              };
              return <EvidenceRow key={i} item={item} />;
            })}
          </div>
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Radar modal
// ---------------------------------------------------------------------------

type RadarModalProps = { entity: V2Opportunity; onClose: () => void };

function RadarModal({ entity: e, onClose }: RadarModalProps) {
  const handleKey = useCallback((ev: KeyboardEvent) => {
    if (ev.key === "Escape") onClose();
  }, [onClose]);

  useEffect(() => {
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [handleKey]);

  const { data: evidence, isLoading: evLoading } = useQuery<V2Evidence>({
    queryKey: ["v2-evidence", e.entity_id],
    queryFn: () => api.evidenceV2(e.entity_id),
    staleTime: 30000,
    retry: 1,
  });

  const radarData = [
    { axis: "Pain",         value: e.v2_pain_score        ?? 0 },
    { axis: "Recovery",     value: e.v2_recovery_score    ?? 0 },
    { axis: "ERP Fit",      value: e.v2_erp_fit_score     ?? 0 },
    { axis: "Reachability", value: e.v2_reachability_score ?? 0 },
  ];

  const dq   = e.v2_reasoning?.data_quality;
  const comb = e.v2_reasoning?.combination;
  const axes = e.v2_reasoning?.axes as Record<string, Record<string, unknown>> | undefined;

  const axisDescriptions: Record<string, string> = {
    pain_score:         "Sector-relative customer distress (complaints + sentiment drop + press articles).",
    recovery_score:     "Observable leadership action signals weighted by recency and confidence.",
    erp_fit_score:      "How well TEAMWILL's Sofico/leasing portfolio fits this entity's sub-segment.",
    reachability_score: "Tech-stack openness — penalised for competitor lock-in or proprietary systems.",
  };

  // Flatten axis JSONB into renderable pills, unwrapping nested objects (components, etc.)
  function axisPills(axisBlock: Record<string, unknown> | undefined): Array<{ k: string; v: string }> {
    if (!axisBlock) return [];
    const pills: Array<{ k: string; v: string }> = [];
    for (const [k, v] of Object.entries(axisBlock)) {
      if (k === "score") continue; // already shown as big number
      if (v !== null && typeof v === "object" && !Array.isArray(v)) {
        // Unwrap one level (e.g. components: { complaint_intensity, ... })
        for (const [sk, sv] of Object.entries(v as Record<string, unknown>)) {
          pills.push({ k: sk.replace(/_/g, " "), v: typeof sv === "number" ? String(Math.round(sv as number)) : String(sv) });
        }
      } else if (Array.isArray(v)) {
        if (v.length > 0) pills.push({ k: k.replace(/_/g, " "), v: (v as unknown[]).join(", ") });
      } else {
        pills.push({ k: k.replace(/_/g, " "), v: typeof v === "number" ? String(Math.round(v as number)) : String(v ?? "—") });
      }
    }
    return pills.slice(0, 6);
  }

  const evidenceBuckets: Record<string, V2EvidenceItem[]> = {
    pain_score:         evidence?.pain_evidence         ?? [],
    recovery_score:     evidence?.recovery_evidence     ?? [],
    erp_fit_score:      evidence?.erp_fit_evidence      ?? [],
    reachability_score: evidence?.reachability_evidence ?? [],
  };

  const evidenceEmptyMsg: Record<string, string> = {
    pain_score:         "No scraped negative reviews or matching articles found.",
    recovery_score:     "No scraped action signals on record.",
    erp_fit_score:      "No sub-segment profile available.",
    reachability_score: "No scraped tech stack records.",
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: "rgba(0,0,0,0.75)", backdropFilter: "blur(4px)" }}
      onClick={(ev) => { if (ev.target === ev.currentTarget) onClose(); }}
    >
      <div
        className="bg-slate-950 border border-slate-700 rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto"
        style={{ animation: "fadeInUp 250ms ease-out both" }}
      >
        {/* Header */}
        <div className="flex items-start justify-between p-6 border-b border-slate-800">
          <div>
            <h2 className="text-xl font-black text-white tracking-tight">{e.entity_name}</h2>
            <div className="flex items-center gap-2 mt-2">
              <span className="text-[9px] font-black uppercase tracking-widest text-slate-500">{e.entity_type}</span>
              {e.region && <span className="text-[9px] font-black uppercase tracking-widest text-blue-400">{e.region}</span>}
              {tierBadge(e.v2_tier)}
              {dq && evBadge(dq)}
            </div>
          </div>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-slate-800 text-slate-500 hover:text-slate-300 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Radar */}
        <div className="p-6 border-b border-slate-800">
          <div className="text-[9px] font-black uppercase tracking-widest text-slate-500 mb-4">Four-Axis Profile</div>
          <ResponsiveContainer width="100%" height={260}>
            <RadarChart data={radarData} margin={{ top: 10, right: 30, bottom: 10, left: 30 }}>
              <PolarGrid stroke="#1F2937" />
              <PolarAngleAxis
                dataKey="axis"
                tick={{ fill: "#9CA3AF", fontSize: 11, fontWeight: 700 }}
              />
              <Radar
                name={e.entity_name}
                dataKey="value"
                stroke="#6366f1"
                fill="#6366f1"
                fillOpacity={0.18}
                strokeWidth={2}
              />
              <Tooltip
                contentStyle={{ backgroundColor: "#0F172A", border: "1px solid #1E293B", borderRadius: 8, fontSize: 11 }}
                formatter={(v: number) => [`${Math.round(v)}`, "Score"]}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        {/* Axis breakdown + evidence */}
        <div className="p-6 border-b border-slate-800">
          <div className="text-[9px] font-black uppercase tracking-widest text-slate-500 mb-4">Axis Scores</div>
          <div className="space-y-5">
            {(["pain_score", "recovery_score", "erp_fit_score", "reachability_score"] as const).map((k) => {
              const rawKey = k.replace("_score", "");
              const scoreKey = `v2_${k}` as keyof V2Opportunity;
              const score = e[scoreKey] as number | null;
              const axisBlock = axes?.[rawKey] as Record<string, unknown> | undefined;
              const pills = axisPills(axisBlock);
              const evItems = evidenceBuckets[k] ?? [];
              const isErpFit = k === "erp_fit_score";

              return (
                <div key={k}>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs font-bold text-slate-300 capitalize">{rawKey.replace(/_/g, " ")}</span>
                    <span className={clsx("font-mono text-sm font-black tabular-nums", score == null ? "text-slate-600" : score >= 70 ? "text-emerald-400" : score >= 40 ? "text-amber-400" : "text-red-400")}>
                      {score == null ? "—" : Math.round(score)}
                    </span>
                  </div>
                  <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                    <div
                      className={clsx("h-full rounded-full transition-all duration-700", score == null ? "bg-slate-700" : score >= 70 ? "bg-emerald-500" : score >= 40 ? "bg-amber-500" : "bg-red-500/60")}
                      style={{ width: score == null ? "0%" : `${Math.min(score, 100)}%` }}
                    />
                  </div>
                  <p className="text-[10px] text-slate-600 mt-1">{axisDescriptions[k]}</p>
                  {pills.length > 0 && (
                    <div className="mt-1.5 flex flex-wrap gap-1">
                      {pills.map(({ k: pk, v: pv }) => (
                        <span key={pk} className="text-[9px] bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded font-mono">
                          {pk}: {pv}
                        </span>
                      ))}
                    </div>
                  )}
                  {evLoading ? (
                    <div className="mt-2 h-4 bg-slate-800 rounded animate-pulse w-32" />
                  ) : isErpFit ? (
                    /* ERP fit: explainer + catalog match block + profile-source URLs */
                    <div className="mt-2 space-y-1.5">
                      <p className="text-[10px] text-slate-500 leading-relaxed">
                        ERP Fit measures how closely this entity matches TEAMWILL&apos;s ideal customer profile —
                        captive auto finance, leasing, insurance, banking. It&apos;s not derived from the entity&apos;s
                        IT problems; it&apos;s derived from what the entity <em>is</em>. The profile sources below
                        document the facts (industry, parent company, geography) that drive the match. Sources
                        won&apos;t mention ERP — they document the company, and the matching is done against
                        TEAMWILL&apos;s product catalog.
                      </p>
                      <EvidenceSection
                        title="Scoring rules"
                        items={evItems}
                        emptyMsg="No sub-segment profile available."
                      />
                      <ErpCatalogMatchBlock
                        matches={evidence?.erp_catalog_matches ?? []}
                      />
                      <ErpProfileSources
                        urls={evidence?.erp_profile_sources ?? []}
                      />
                    </div>
                  ) : (
                    <EvidenceSection
                      title="Evidence"
                      items={evItems}
                      emptyMsg={evidenceEmptyMsg[k]}
                    />
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Combination + gate */}
        {comb && (
          <div className="p-6 border-b border-slate-800">
            <div className="text-[9px] font-black uppercase tracking-widest text-slate-500 mb-3">Combination</div>
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="bg-slate-900 rounded-lg p-3 border border-slate-800">
                <div className="text-[9px] text-slate-600 uppercase tracking-widest mb-1">Geometric mean</div>
                <div className="font-mono font-black text-white text-lg">{comb.geometric_mean != null ? Math.round(comb.geometric_mean) : "—"}</div>
              </div>
              <div className="bg-slate-900 rounded-lg p-3 border border-slate-800">
                <div className="text-[9px] text-slate-600 uppercase tracking-widest mb-1">Weakest axis</div>
                <div className="font-mono font-black text-amber-400 text-lg">{comb.weakest_axis != null ? Math.round(comb.weakest_axis) : "—"}</div>
              </div>
            </div>
            {comb.gate_override && (
              <div className="mt-3 flex items-start gap-2 bg-amber-500/5 border border-amber-500/20 rounded-lg p-3">
                <AlertTriangle className="w-3.5 h-3.5 text-amber-400 flex-shrink-0 mt-0.5" />
                <span className="text-[10px] text-amber-300">{comb.gate_override}</span>
              </div>
            )}
          </div>
        )}

        {/* Evidence quality */}
        {dq && (
          <div className="p-6">
            <div className="text-[9px] font-black uppercase tracking-widest text-slate-500 mb-3">Evidence Quality</div>
            <div className="grid grid-cols-3 gap-3">
              {[
                { label: "Scraped reviews", v: dq.scraped_review_count,       ok: dq.has_scraped_reviews },
                { label: "Action signals",  v: dq.scraped_action_signal_count, ok: dq.has_scraped_action_signals },
                { label: "Tech records",    v: dq.scraped_tech_stack_count,    ok: dq.has_scraped_tech_stack },
              ].map(({ label, v, ok }) => (
                <div key={label} className={clsx("rounded-lg p-3 border text-center", ok ? "bg-emerald-500/5 border-emerald-500/20" : "bg-slate-800/40 border-slate-700")}>
                  <div className={clsx("text-xl font-black font-mono", ok ? "text-emerald-400" : "text-slate-600")}>{v}</div>
                  <div className="text-[9px] uppercase tracking-widest text-slate-500 mt-0.5">{label}</div>
                </div>
              ))}
            </div>
            <div className="mt-3 flex items-center justify-between text-[10px]">
              <span className="text-slate-500">V1 baseline</span>
              <span className="font-mono text-slate-400">{Math.round(e.v1_overall_score)} · <span className="capitalize">{e.v1_signal_strength}</span></span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Table row
// ---------------------------------------------------------------------------

type SortKey = "v2_overall_score" | "v2_pain_score" | "v2_recovery_score" | "v2_erp_fit_score" | "v2_reachability_score" | "v1_overall_score";

function TableRow({ item, rank, onSelect }: { item: V2Opportunity; rank: number; onSelect: (o: V2Opportunity) => void }) {
  const dq = item.v2_reasoning?.data_quality;
  return (
    <tr
      className="border-b border-slate-800/60 hover:bg-slate-800/30 cursor-pointer transition-colors"
      onClick={() => onSelect(item)}
    >
      <td className="py-3 pl-4 pr-2 text-[10px] font-bold text-slate-600 tabular-nums w-8">{rank}</td>
      <td className="py-3 px-3">
        <div className="flex items-center gap-2">
          {moverIcon(item.v1_signal_strength, item.v2_tier)}
          <div>
            <div className="text-sm font-bold text-slate-100">{item.entity_name}</div>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className="text-[9px] text-slate-600 uppercase">{item.entity_type}</span>
              {item.region && <span className="text-[9px] text-blue-500">{item.region}</span>}
            </div>
          </div>
        </div>
      </td>
      <td className="py-3 px-3 text-center">{tierBadge(item.v2_tier)}</td>
      <td className="py-3 px-2 text-center">
        <span className={clsx("font-mono text-sm font-black tabular-nums", item.v2_overall_score == null ? "text-slate-600" : item.v2_overall_score >= 70 ? "text-emerald-400" : item.v2_overall_score >= 45 ? "text-blue-400" : "text-slate-500")}>
          {item.v2_overall_score != null ? Math.round(item.v2_overall_score) : "—"}
        </span>
      </td>
      <td className="py-3 px-2 text-center hidden md:table-cell">{axisScore(item.v2_pain_score)}</td>
      <td className="py-3 px-2 text-center hidden md:table-cell">{axisScore(item.v2_recovery_score)}</td>
      <td className="py-3 px-2 text-center hidden lg:table-cell">{axisScore(item.v2_erp_fit_score)}</td>
      <td className="py-3 px-2 text-center hidden lg:table-cell">{axisScore(item.v2_reachability_score)}</td>
      <td className="py-3 px-3 text-center hidden xl:table-cell">
        <div className="flex flex-col items-center gap-0.5">
          {dq ? evBadge(dq) : <span className="text-slate-700 text-[9px]">—</span>}
        </div>
      </td>
      <td className="py-3 px-3 text-center">
        <button
          onClick={(e) => { e.stopPropagation(); onSelect(item); }}
          className="p-1.5 rounded-lg hover:bg-slate-700 text-slate-600 hover:text-slate-300 transition-colors"
          title="Open radar explainer"
        >
          <HelpCircle className="w-3.5 h-3.5" />
        </button>
      </td>
    </tr>
  );
}

// ---------------------------------------------------------------------------
// Sort header
// ---------------------------------------------------------------------------

function SortTh({ label, col, current, dir, onSort }: {
  label: string; col: SortKey; current: SortKey; dir: "asc" | "desc";
  onSort: (c: SortKey) => void;
}) {
  const active = current === col;
  return (
    <th
      className={clsx("py-2.5 px-2 text-[9px] font-black uppercase tracking-widest cursor-pointer select-none whitespace-nowrap transition-colors", active ? "text-brand-400" : "text-slate-600 hover:text-slate-400")}
      onClick={() => onSort(col)}
    >
      <span className="flex items-center justify-center gap-1">
        {label}
        {active ? (dir === "desc" ? <ChevronDown className="w-3 h-3" /> : <ChevronUp className="w-3 h-3" />) : null}
      </span>
    </th>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function OpportunitiesV2() {
  const [tierFilter,   setTierFilter]   = useState<string>("all");
  const [typeFilter,   setTypeFilter]   = useState<string>("all");
  const [regionFilter, setRegionFilter] = useState<string>("all");
  const [sortKey,      setSortKey]      = useState<SortKey>("v2_overall_score");
  const [sortDir,      setSortDir]      = useState<"asc" | "desc">("desc");
  const [selected,     setSelected]     = useState<V2Opportunity | null>(null);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["opportunities-v2"],
    queryFn: () => api.opportunitiesV2({ limit: 200 }),
    staleTime: 30000,
  });

  const handleSort = (col: SortKey) => {
    if (sortKey === col) setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    else { setSortKey(col); setSortDir("desc"); }
  };

  if (isError) {
    return (
      <div className="p-8">
        <div className="bg-slate-900 border border-red-500/20 rounded-xl p-6">
          <ErrorState title="Failed to load V2 opportunities" error={error} onRetry={refetch} />
        </div>
      </div>
    );
  }

  const all = data ?? [];

  // Tier counts
  const counts = { engage: 0, develop: 0, watch: 0, needs_investigation: 0 };
  for (const o of all) {
    const t = o.v2_tier ?? "needs_investigation";
    if (t in counts) (counts as Record<string, number>)[t]++;
  }

  // Filter + sort
  const filtered = all
    .filter((o) => tierFilter   === "all" || o.v2_tier          === tierFilter)
    .filter((o) => typeFilter   === "all" || o.entity_type       === typeFilter)
    .filter((o) => regionFilter === "all" || (o.region ?? "—")   === regionFilter);

  const sorted = [...filtered].sort((a, b) => {
    const av = (a[sortKey] as number | null) ?? -1;
    const bv = (b[sortKey] as number | null) ?? -1;
    return sortDir === "desc" ? bv - av : av - bv;
  });

  const regions = [...new Set(all.map((o) => o.region ?? "—"))].sort();

  return (
    <div
      className="space-y-8 p-8 min-h-screen"
      style={{ fontFamily: "'DM Sans', sans-serif" }}
    >
      <style>{`
        @keyframes fadeInUp {
          from { opacity: 0; transform: translateY(12px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>

      {/* ── Header ── */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-slate-800/60 pb-6">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Target className="w-5 h-5 text-brand-400" />
            <span className="text-[9px] font-black uppercase tracking-[0.2em] text-brand-400">V2 · Four-Axis Model</span>
          </div>
          <h1 className="text-3xl lg:text-4xl font-black text-white tracking-tighter">
            Opportunity Intelligence
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            {isLoading ? "Loading…" : `${all.length} entities · Pain · Recovery · ERP Fit · Reachability`}
          </p>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-2">
          {[
            { value: tierFilter,   setter: setTierFilter,   options: [["all","All tiers"],["engage","Engage"],["develop","Develop"],["watch","Watch"],["needs_investigation","Investigate"]] },
            { value: typeFilter,   setter: setTypeFilter,   options: [["all","All types"],["insurance","Insurance"],["brand","Automotive"]] },
            { value: regionFilter, setter: setRegionFilter, options: [["all","All regions"], ...regions.map((r) => [r, r])] },
          ].map(({ value, setter, options }, i) => (
            <div key={i} className="relative">
              <select
                value={value}
                onChange={(e) => setter(e.target.value)}
                className="appearance-none bg-slate-900 text-slate-200 text-[10px] font-black uppercase tracking-widest rounded-lg border border-slate-800 px-3 py-2 pr-8 focus:outline-none focus:border-brand-500 cursor-pointer"
              >
                {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
              <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-3 h-3 text-slate-500 pointer-events-none" />
            </div>
          ))}
        </div>
      </div>

      {/* ── KPI strip ── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {(["engage","develop","watch","needs_investigation"] as const).map((t) => (
          <TierKpi
            key={t} tier={t}
            count={isLoading ? 0 : counts[t]}
            loading={isLoading}
          />
        ))}
      </div>

      {/* ── Movers widget ── */}
      {/* MoversWidget hidden — V1→V2 comparison not actionable */}

      {/* ── Table ── */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden">
        <div className="px-5 py-3.5 border-b border-slate-800 flex items-center justify-between">
          <span className="text-[10px] font-black uppercase tracking-widest text-slate-400">
            {sorted.length} {sorted.length === all.length ? "entities" : `of ${all.length} filtered`}
          </span>
          <span className="text-[9px] text-slate-600">Click any row or the ⓘ icon to open the radar explainer</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead className="border-b border-slate-800">
              <tr>
                <th className="py-2.5 pl-4 pr-2 w-8" />
                <th className="py-2.5 px-3 text-[9px] font-black uppercase tracking-widest text-slate-600">Entity</th>
                <th className="py-2.5 px-3 text-[9px] font-black uppercase tracking-widest text-slate-600 text-center">Tier</th>
                <SortTh label="V2"    col="v2_overall_score"    current={sortKey} dir={sortDir} onSort={handleSort} />
                <SortTh label="Pain"  col="v2_pain_score"       current={sortKey} dir={sortDir} onSort={handleSort} />
                <SortTh label="Recov" col="v2_recovery_score"   current={sortKey} dir={sortDir} onSort={handleSort} />
                <SortTh label="Fit"   col="v2_erp_fit_score"    current={sortKey} dir={sortDir} onSort={handleSort} />
                <SortTh label="Reach" col="v2_reachability_score" current={sortKey} dir={sortDir} onSort={handleSort} />
                <th className="py-2.5 px-3 text-[9px] font-black uppercase tracking-widest text-slate-600 text-center hidden xl:table-cell">Evidence</th>
                <th className="py-2.5 px-3 w-10" />
              </tr>
            </thead>
            <tbody>
              {isLoading
                ? Array.from({ length: 8 }).map((_, i) => (
                    <tr key={i} className="border-b border-slate-800/40">
                      <td colSpan={10} className="py-3 px-4">
                        <div className="h-6 bg-slate-800 rounded animate-pulse" />
                      </td>
                    </tr>
                  ))
                : sorted.map((item, i) => (
                    <TableRow key={item.entity_id} item={item} rank={i + 1} onSelect={setSelected} />
                  ))}
            </tbody>
          </table>
        </div>

        {!isLoading && sorted.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 text-slate-600">
            <Eye className="w-10 h-10 mb-3" />
            <p className="text-sm font-bold">No entities match these filters</p>
          </div>
        )}
      </div>

      {/* ── Radar modal ── */}
      {selected && <RadarModal entity={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
