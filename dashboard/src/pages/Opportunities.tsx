import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Target, AlertTriangle, Eye, Database, ChevronDown, Download, Loader2, Activity } from "lucide-react";
import clsx from "clsx";
import { api } from "../api/client";
import type { OpportunitySignal, OpportunitySummary } from "../api/client";
import ErrorState from "../components/ErrorState";

// ---------------------------------------------------------------------------
// Text generators
// ---------------------------------------------------------------------------

function generateBriefing(
  signals: OpportunitySignal[],
  summary: OpportunitySummary,
  regionFilter: string
): string {
  const total = signals.length;
  const regionLabel = regionFilter === "all" ? "global market" : `${regionFilter} market`;
  const avgScore = signals.length
    ? Math.round(signals.reduce((s, x) => s + x.overall_score, 0) / signals.length)
    : 0;
  const noDataCount = signals.filter((s) => s.review_volume_score > 70).length;
  const hasComplaints = signals.some((s) => s.complaint_score > 60);
  const top = signals[0];

  if (summary.strong_signals > 0) {
    const sectorCtx = top.score_reasoning?.sector_context;
    const sectorLabel = top.entity_type === "insurance" ? "insurance companies" : "automotive brands";
    const percentileLine = sectorCtx
      ? ` ${top.entity_name} performs worse than ${sectorCtx.percentile}% of tracked ${sectorLabel}.`
      : "";
    return `${summary.strong_signals} ${regionLabel} ${
      summary.strong_signals === 1 ? "company is" : "companies are"
    } showing strong distress signals this month. ${
      top.entity_name
    } leads with a score of ${Math.round(top.overall_score)}/100, driven by ${
      top.top_complaint_types?.[0] ?? "multiple complaint categories"
    }. This represents an immediate outreach opportunity for TEAMWILL's sales team.${percentileLine}`;
  }
  if (noDataCount === total && total > 0) {
    return `All ${total} ${regionLabel} companies score at ${avgScore}/100 — not because of confirmed problems, but because none have a visible online review presence. In market intelligence terms, invisibility is itself a signal: companies without digital feedback loops are more likely to need the kind of CRM and ERP integration TEAMWILL provides. Scraping review data for these companies will sharpen scores significantly.`;
  }
  if (hasComplaints && top) {
    return `${top.entity_name} is the highest-priority opportunity in the ${regionLabel} (score: ${Math.round(
      top.overall_score
    )}/100). Customer complaints center on ${
      top.top_complaint_types?.[0] ?? "operational issues"
    }, which aligns directly with TEAMWILL's core ERP capabilities. ${summary.moderate_signals} companies show moderate signals worth monitoring.`;
  }
  return `${total} companies tracked in the ${regionLabel}. Average opportunity score: ${avgScore}/100. Continue data collection to surface differentiated rankings — more review data will separate strong opportunities from background noise.`;
}

function generateWhyText(signal: OpportunitySignal): string {
  if (signal.review_volume_score > 75)
    return "No online reviews found — significant digital presence gap";
  if (signal.complaint_score > 65)
    return `High complaint rate: ${signal.top_complaint_types?.[0] ?? "multiple categories"}`;
  if (signal.sentiment_drop_score > 65)
    return "Sentiment declining over last 3 months — customer satisfaction at risk";
  return "Moderate signals across all dimensions — worth monitoring";
}

function generateAction(
  signals: OpportunitySignal[],
  summary: OpportunitySummary,
  regionFilter: string
): { text: string; code: string | null; tone: "amber" | "blue" } {
  const tnSignals = signals.filter((s) => s.region === "TN");
  const allTnNoData = tnSignals.length > 0 && tnSignals.every((s) => s.review_volume_score > 70);

  if (regionFilter === "TN" && allTnNoData) {
    return {
      text: `Run the Trustpilot scraper targeting your ${tnSignals.length} Tunisian insurers to get real complaint data. Even 5 reviews per company will sharpen scores from 57 → differentiated rankings.`,
      code: "python scripts/run_reviews_ingest.py",
      tone: "amber",
    };
  }
  if (summary.strong_signals > 0) {
    const top = signals[0];
    return {
      text: `${top.entity_name} is showing strong distress signals. Recommend contacting their operations team about TEAMWILL's ERP solutions — complaint patterns suggest process gaps that your platform addresses directly.`,
      code: null,
      tone: "blue",
    };
  }
  return {
    text: "Continue deepening review scraping across all tracked entities. More data will surface differentiated signal strength and separate high-priority targets from background noise.",
    code: "python scripts/run_reviews_ingest.py",
    tone: "amber",
  };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function scoreColor(score: number): string {
  if (score >= 70) return "text-emerald-500";
  if (score >= 40) return "text-amber-500";
  return "text-slate-500";
}

function scoreBarColor(score: number): string {
  if (score >= 70) return "bg-emerald-500";
  if (score >= 40) return "bg-amber-500";
  return "bg-slate-600";
}

// ---------------------------------------------------------------------------
// Animated counter hook
// ---------------------------------------------------------------------------

function useAnimatedCount(target: number, duration = 800): number {
  const [value, setValue] = useState(0);
  useEffect(() => {
    if (target === 0) { setValue(0); return; }
    const start = performance.now();
    let frame: number;
    const tick = (now: number) => {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(Math.round(eased * target));
      if (progress < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, duration]);
  return value;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ScoreBar({ score, index }: { score: number; index: number }) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setMounted(true), 50 + index * 100);
    return () => clearTimeout(t);
  }, [index]);

  return (
    <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
      <div
        className={clsx("h-full rounded-full transition-all duration-[1200ms] ease-out", scoreBarColor(score))}
        style={{ width: mounted ? `${Math.min(score, 100)}%` : "0%" }}
      />
    </div>
  );
}

function AnimatedScore({ value, className }: { value: number; className?: string }) {
  const display = useAnimatedCount(value);
  return <span className={className}>{display}</span>;
}

function SignalCard({ signal, index }: { signal: OpportunitySignal; index: number }) {
  const glowShadow = signal.signal_strength === "strong" 
    ? "shadow-[0_0_20px_rgba(16,185,129,0.15)] border-emerald-500/50" 
    : signal.signal_strength === "moderate" 
      ? "shadow-[0_0_15px_rgba(245,158,11,0.1)] border-amber-500/30" 
      : "border-slate-800/80";

  return (
    <div
      className={clsx(
        "bg-slate-900/60 backdrop-blur-sm rounded-xl border p-5 transition-all duration-300 hover:-translate-y-1 hover:bg-slate-900",
        glowShadow
      )}
      style={{ animation: `fadeInUp 600ms ease-out ${index * 100}ms both` }}
    >
      <div className="flex flex-col h-full justify-between">
        <div className="mb-4">
          {/* Header */}
          <div className="flex items-start justify-between mb-2">
            <div className="flex-1 min-w-0 pr-4">
              <h4 className="text-base font-bold text-slate-100 truncate">{signal.entity_name}</h4>
              <p className="text-xs text-slate-400 mt-1 line-clamp-2 leading-relaxed">{generateWhyText(signal)}</p>
            </div>
            <div className={clsx("font-mono text-4xl font-black tabular-nums tracking-tighter", scoreColor(signal.overall_score))}>
              <AnimatedScore value={Math.round(signal.overall_score)} />
            </div>
          </div>

          {/* Tags row */}
          <div className="flex flex-wrap gap-2 mt-4">
            <span className="inline-flex items-center px-2 py-0.5 rounded text-[9px] font-black uppercase tracking-widest bg-slate-800 text-slate-300 border border-slate-700">
              {signal.entity_type}
            </span>
            {signal.region && (
              <span className="inline-flex items-center px-2 py-0.5 rounded text-[9px] font-black uppercase tracking-widest bg-blue-500/10 text-blue-400 border border-blue-500/20">
                {signal.region}
              </span>
            )}
            {signal.top_complaint_types?.[0] && (
              <span className="inline-flex items-center px-2 py-0.5 rounded text-[9px] font-black uppercase tracking-widest bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                {signal.top_complaint_types[0]}
              </span>
            )}
            <span
              className={clsx(
                "inline-flex items-center px-2 py-0.5 rounded text-[9px] font-black uppercase tracking-widest border",
                signal.signal_strength === "strong" ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/50" :
                signal.signal_strength === "moderate" ? "bg-amber-500/10 text-amber-500 border-amber-500/30" :
                "bg-slate-800 text-slate-500 border-slate-700"
              )}
            >
              {signal.signal_strength}
            </span>
          </div>
        </div>

        <div>
          <ScoreBar score={signal.overall_score} index={index} />
          {/* Sub-scores */}
          <div className="flex justify-between text-[10px] uppercase font-bold tracking-widest text-slate-500 mt-3">
            <span>C: {Math.round(signal.complaint_score)}</span>
            <span>S: {Math.round(signal.sentiment_drop_score)}</span>
            <span>V: {Math.round(signal.review_volume_score)}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page component
// ---------------------------------------------------------------------------

export default function Opportunities() {
  const [regionFilter, setRegionFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [exporting, setExporting] = useState(false);

  const handleExportBrief = async () => {
    setExporting(true);
    try {
      const res = await fetch("/api/export/weekly-brief");
      if (!res.ok) throw new Error(`Export failed: ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `teamwill-brief-${new Date().toISOString().slice(0, 10)}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("PDF export failed:", err);
    } finally {
      setExporting(false);
    }
  };

  const {
    data: summary,
    isLoading: summaryLoading,
    isError: summaryError,
    error: summaryErr,
    refetch: summaryRefetch,
  } = useQuery({
    queryKey: ["opportunities-summary"],
    queryFn: () => api.opportunitySummary(),
    staleTime: 30000,
  });

  const {
    data: signals,
    isLoading: signalsLoading,
    isError: signalsError,
    error: signalsErr,
    refetch: signalsRefetch,
  } = useQuery({
    queryKey: ["opportunities", regionFilter, typeFilter],
    queryFn: () =>
      api.opportunities({
        region: regionFilter === "all" ? undefined : regionFilter,
        entity_type: typeFilter === "all" ? undefined : typeFilter,
      }),
    staleTime: 30000,
  });

  const isLoading = summaryLoading || signalsLoading;
  const isError = summaryError || signalsError;

  if (isError) {
    return (
      <div className="bg-slate-900 border border-red-500/20 rounded-xl p-6">
        <ErrorState
          title="Failed to load opportunity data"
          error={summaryErr || signalsErr}
          onRetry={() => { summaryRefetch(); signalsRefetch(); }}
        />
      </div>
    );
  }

  const regionOptions = summary ? Object.keys(summary.by_region) : [];
  const totalSignals = summary ? summary.strong_signals + summary.moderate_signals + summary.weak_signals : 0;
  const tnCount = summary?.by_region?.["TN"] ?? 0;

  const displaySignals = signals ?? [];
  const top6 = displaySignals.slice(0, 6);

  const action = summary && displaySignals.length > 0
    ? generateAction(displaySignals, summary, regionFilter)
    : null;

  const dataCoverage = displaySignals.length > 0
    ? Math.round(
        (displaySignals.filter((s) => s.review_volume_score <= 70).length / displaySignals.length) * 100
      )
    : 0;

  return (
    <div className="space-y-10 relative z-10">
      
      {/* Injecting keyframes for animation since we removed external CSS */}
      <style>{`
        @keyframes fadeInUp {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
      
      {/* ============================================================= */}
      {/* SECTION A — Minimalist cinematic header                        */}
      {/* ============================================================= */}
      <div className="flex flex-col md:flex-row justify-between items-end gap-6 border-b border-slate-800/60 pb-6">
        <div>
          <h1 className="text-3xl lg:text-5xl font-black text-white tracking-tighter mb-2">
            Opportunity Scoring Matrix
          </h1>
          <p className="text-sm font-semibold tracking-wide text-slate-500">
            {isLoading
              ? "AGGREGATING INTELLIGENCE DATA..."
              : `${totalSignals} ENTITIES SCORED • ${summary?.strong_signals ?? 0} HIGH PRIORITY • ${summary?.moderate_signals ?? 0} WATCHLIST`}
          </p>
        </div>

        {/* Filters row + export */}
        <div className="flex items-center gap-3">
          <div className="relative">
            <select
              value={regionFilter}
              onChange={(e) => setRegionFilter(e.target.value)}
              className="appearance-none bg-slate-900 text-slate-200 text-xs font-bold uppercase tracking-widest rounded-lg border border-slate-800 px-4 py-2.5 pr-10 focus:outline-none focus:border-brand-500"
            >
              <option value="all">Global view</option>
              {regionOptions.map((r) => (
                <option key={r} value={r === "unset" ? "all" : r}>
                  {r === "unset" ? "Unmapped" : r}
                </option>
              ))}
            </select>
            <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500 pointer-events-none" />
          </div>
          <div className="relative">
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="appearance-none bg-slate-900 text-slate-200 text-xs font-bold uppercase tracking-widest rounded-lg border border-slate-800 px-4 py-2.5 pr-10 focus:outline-none focus:border-brand-500"
            >
              <option value="all">All Sectors</option>
              <option value="insurance">Insurance</option>
              <option value="brand">Automotive</option>
            </select>
            <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500 pointer-events-none" />
          </div>
          <button
            onClick={handleExportBrief}
            disabled={exporting}
            className="flex items-center gap-2 rounded-lg bg-emerald-500/10 border border-emerald-500/30 px-5 py-2.5 text-xs font-black uppercase tracking-widest text-emerald-400 hover:bg-emerald-500/20 transition-colors disabled:opacity-50"
          >
            {exporting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Download className="h-4 w-4" />
            )}
            Compile Brief
          </button>
        </div>
      </div>

      {/* ============================================================= */}
      {/* SECTION B — Tactical Briefing Banner                           */}
      {/* ============================================================= */}
      {!isLoading && displaySignals.length > 0 && summary && (
        <div className="bg-gradient-to-r from-slate-900 to-slate-950 border-l-[4px] border-emerald-500 rounded-lg p-6 shadow-xl relative overflow-hidden">
          <div className="absolute top-0 right-0 p-8 opacity-5">
            <Target className="w-48 h-48 -mt-16 -mr-16" />
          </div>
          <div className="relative z-10">
            <div className="flex items-center gap-3 mb-3">
              <span className="relative flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,1)]"></span>
              </span>
              <span className="text-[10px] font-black uppercase tracking-[0.2em] text-emerald-500">
                AI Strategic Assessment
              </span>
            </div>
            <p className="text-base text-slate-300 leading-relaxed max-w-4xl">
              {generateBriefing(displaySignals, summary, regionFilter)}
            </p>
          </div>
        </div>
      )}

      {/* ============================================================= */}
      {/* SECTION C — KPI row                                            */}
      {/* ============================================================= */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
        <CinematicKpi 
          title="Critical Flags" 
          value={summary?.strong_signals ?? 0} 
          icon={<AlertTriangle className="text-emerald-500 w-5 h-5" />} 
          loading={isLoading} 
        />
        <CinematicKpi 
          title="Watchlist" 
          value={summary?.moderate_signals ?? 0} 
          icon={<Eye className="text-amber-500 w-5 h-5" />} 
          loading={isLoading} 
        />
        <CinematicKpi 
          title="Regional Scope [TN]" 
          value={tnCount} 
          icon={<Target className="text-brand-400 w-5 h-5" />} 
          loading={isLoading} 
        />
        <CinematicKpi 
          title="Data Integrity" 
          value={`${dataCoverage}%`} 
          icon={<Database className="text-emerald-500 w-5 h-5" />} 
          loading={isLoading} 
        />
      </div>

      {/* ============================================================= */}
      {/* SECTION D — Signal cards grid (top 6)                          */}
      {/* ============================================================= */}
      <div className="pb-8">
        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="bg-slate-900 border border-slate-800 rounded-xl h-48 animate-pulse" />
            ))}
          </div>
        ) : top6.length > 0 ? (
          <>
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-black text-white tracking-tight">
                High Priority Pipeline
              </h2>
              <span className="text-[10px] font-bold tracking-widest uppercase text-slate-500">
                Showing top {top6.length} targets
              </span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
              {top6.map((signal, i) => (
                <SignalCard key={signal.entity_id} signal={signal} index={i} />
              ))}
            </div>
          </>
        ) : (
          <div className="h-64 flex flex-col items-center justify-center bg-slate-900/50 border border-slate-800/50 rounded-2xl border-dashed">
            <Target className="w-12 h-12 text-slate-600 mb-4" />
            <h3 className="text-lg font-bold text-slate-400">No priority targets resolved</h3>
            <p className="text-sm text-slate-500 mt-1">Adjust filters or await additional data ingestion.</p>
          </div>
        )}
      </div>

      {/* ============================================================= */}
      {/* SECTION E — Action box                                         */}
      {/* ============================================================= */}
      {action && !isLoading && (
        <div
          className={clsx(
            "rounded-xl p-8 backdrop-blur-xl border relative overflow-hidden",
            action.tone === "amber"
              ? "bg-amber-950/20 border-amber-500/20 shadow-[0_0_30px_rgba(245,158,11,0.05)]"
              : "bg-emerald-950/20 border-emerald-500/20 shadow-[0_0_30px_rgba(16,185,129,0.05)]"
          )}
        >
          <div className="relative z-10">
            <div className={clsx(
              "text-[10px] font-black uppercase tracking-widest mb-3",
              action.tone === "amber" ? "text-amber-500" : "text-emerald-500"
            )}>
              Terminal Execution Recommended
            </div>
            <p className="text-lg font-semibold text-slate-200 leading-relaxed mb-6 max-w-4xl">
              {action.text}
            </p>
            {action.code && (
              <div className="bg-[#050b14] border border-slate-800/80 rounded-lg p-5 font-mono">
                <div className="text-[9px] uppercase tracking-widest text-slate-600 mb-2 font-black">SHELL / TERMINAL</div>
                <pre className="text-emerald-400 text-sm overflow-x-auto">
                  <span className="text-slate-600 select-none">$ </span>
                  {action.code}
                </pre>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function CinematicKpi({ title, value, icon, loading }: { title: string; value: React.ReactNode; icon: React.ReactNode; loading: boolean }) {
  if (loading) return <div className="h-32 bg-slate-900 border border-slate-800 rounded-xl animate-pulse" />;
  
  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 relative overflow-hidden group">
      <div className="absolute -right-4 -top-4 opacity-5 group-hover:scale-110 transition-transform duration-700">
        <div className="scale-[2.5]">{icon}</div>
      </div>
      <div className="relative z-10 flex flex-col justify-between h-full">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 bg-slate-950 rounded-lg border border-slate-800 shadow-inner">
            {icon}
          </div>
        </div>
        <div>
          <div className="text-4xl font-black text-white tracking-tighter mb-1 font-mono">
            {value}
          </div>
          <div className="text-[10px] uppercase tracking-widest font-bold text-slate-500">
            {title}
          </div>
        </div>
      </div>
    </div>
  );
}
