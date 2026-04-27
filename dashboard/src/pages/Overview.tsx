import { useQuery } from "@tanstack/react-query";
import {
  MessageSquare, Car, MapPin, Newspaper, Activity,
  AlertTriangle, RefreshCw, ShieldCheck,
  ExternalLink, Star,
} from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell,
} from "recharts";
import { api, BrandSummary } from "../api/client";
import ErrorState from "../components/ErrorState";
import { formatDistanceToNow } from "date-fns";
import clsx from "clsx";
import RefreshDataPanel from "../components/RefreshDataPanel";

const PALETTE = ["#6366f1","#3b82f6","#10b981","#f59e0b","#ef4444","#8b5cf6","#06b6d4","#84cc16"];

export default function Overview() {
  const { data: summary, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["dashboard-summary"],
    queryFn: api.dashboardSummary,
    staleTime: 0,
  });

  const { data: brands } = useQuery<BrandSummary[]>({
    queryKey: ["brands-summary"],
    queryFn: () => api.brandsSummary(),
  });

  const { data: provenance } = useQuery({
    queryKey: ["data-provenance"],
    queryFn: api.dataProvenance,
    staleTime: 60_000,
  });

  if (isError) {
    return (
      <div className="bg-slate-900 border border-red-500/20 rounded-xl p-6">
        <ErrorState error={error} onRetry={refetch} title="Could not load overview data" />
      </div>
    );
  }

  const ps = summary?.pipeline_status;
  const steps = ps?.pipeline_steps ?? {};
  const stepEntries = Object.entries(steps).sort((a, b) => a[0].localeCompare(b[0]));
  const sources = summary?.source_health ?? [];
  const failures = summary?.recent_failures ?? [];
  const reviewSources = summary?.review_sources ?? [];

  // Brand leaderboard — top 5 by review count
  const topBrands = (brands ?? []).slice(0, 8);

  // Provenance totals
  const realArticles = provenance?.market_articles?.scraped ?? 0;
  const realListings = provenance?.car_listings?.scraped ?? 0;
  const seededListings = provenance?.car_listings?.seeded ?? 0;
  const seededArticles = provenance?.market_articles?.seeded ?? 0;
  const nlpTransformer = provenance?.nlp_models?.["distilbert-sst2-v1"] ?? 0;
  const nlpRule = provenance?.nlp_models?.["rule-nlp-v1"] ?? 0;

  return (
    <div className="space-y-10 relative z-10 text-slate-200">
      
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-end gap-6 border-b border-slate-800/60 pb-6">
        <div>
          <h1 className="text-3xl lg:text-5xl font-black text-white tracking-tighter mb-2">
            Market Pulse
          </h1>
          <p className="text-sm font-semibold tracking-wide text-slate-500 uppercase">
            Global Database Telemetry & Operations
          </p>
        </div>
        <RefreshDataPanel variant="compact" />
      </div>

      {/* Provenance Banner */}
      {provenance && (
        <div className="rounded-xl border border-indigo-500/30 bg-indigo-950/20 px-6 py-5 backdrop-blur-md shadow-[0_0_20px_rgba(99,102,241,0.05)]">
          <div className="flex flex-wrap items-center gap-x-8 gap-y-4">
            <div>
              <p className="text-[10px] font-black uppercase tracking-widest text-indigo-400 mb-1">DATA PROVENANCE MATRIX</p>
              <p className="text-xs font-semibold text-slate-400">Sources separated by organic vs. seeded origins.</p>
            </div>
            <div className="flex flex-wrap gap-3">
              <ProvenancePill label="Real Articles" value={realArticles} color="emerald" />
              <ProvenancePill label="Seeded Articles" value={seededArticles} color="slate" />
              <ProvenancePill label="Real Listings" value={realListings} color="emerald" />
              <ProvenancePill label="Seeded Listings" value={seededListings} color="slate" />
              <ProvenancePill label="Transformer NLP" value={nlpTransformer} color="indigo" />
              <ProvenancePill label="Rule NLP" value={nlpRule} color="amber" />
            </div>
          </div>
        </div>
      )}

      {/* KPI Row */}
      <div>
        <h2 className="text-base font-bold uppercase tracking-widest text-slate-500 mb-6">Intelligence Corpus</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-6">
          <CinKpi label="Car Reviews"        value={isLoading ? "—" : (summary?.total_car_reviews ?? 0)}        icon={<MessageSquare className="w-5 h-5" />} color="brand"   />
          <CinKpi label="Ins. Reviews"  value={isLoading ? "—" : (summary?.total_insurance_reviews ?? 0)} icon={<MessageSquare className="w-5 h-5" />} color="blue"    />
          <CinKpi label="Car Listings"        value={isLoading ? "—" : (summary?.total_listings ?? 0)}           icon={<MapPin className="w-5 h-5" />}        color="emerald" />
          <CinKpi label="Market Articles"     value={isLoading ? "—" : (summary?.total_articles ?? 0)}           icon={<Newspaper className="w-5 h-5" />}     color="amber"   />
          <CinKpi label="Brands Tracked"      value={isLoading ? "—" : (summary?.total_brands ?? 0)}             icon={<Car className="w-5 h-5" />}           color="brand"   />
          <CinKpi label="Pricing Quotes"      value={isLoading ? "—" : (summary?.total_competitors ?? 0)}        icon={<ShieldCheck className="w-5 h-5" />}   color="red"     />
        </div>
      </div>

      {/* NLP Coverage */}
      {(isLoading || ps) && (
        <div className="pt-4">
          <h2 className="text-base font-bold uppercase tracking-widest text-slate-500 mb-6">NLP Sentiment Coverage</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <NlpCoverageCard label="Auto Review Sentiment Base" loading={isLoading}
              total={ps?.nlp_coverage.car_reviews.total ?? 0}
              processed={ps?.nlp_coverage.car_reviews.nlp_processed ?? 0}
              pct={ps?.nlp_coverage.car_reviews.coverage_pct ?? 0} color="brand" />
            <NlpCoverageCard label="Insurance Review Sentiment Base" loading={isLoading}
              total={ps?.nlp_coverage.insurance_reviews.total ?? 0}
              processed={ps?.nlp_coverage.insurance_reviews.nlp_processed ?? 0}
              pct={ps?.nlp_coverage.insurance_reviews.coverage_pct ?? 0} color="blue" />
          </div>
        </div>
      )}

      {/* Dual Tables Row */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-8 pt-4">

        {/* Brand Leaderboard */}
        <div>
          <h2 className="text-base font-bold uppercase tracking-widest text-slate-500 mb-6">Brand Reputation Leaderboard</h2>
          <div className="bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden backdrop-blur-md">
            {!brands ? (
              <div className="divide-y divide-slate-800">
                {[...Array(8)].map((_, i) => (
                  <div key={i} className="flex items-center gap-3 px-6 py-4 animate-pulse">
                    <div className="h-3 w-6 bg-slate-800 rounded" />
                    <div className="h-3 w-20 bg-slate-800 rounded flex-1" />
                    <div className="h-4 w-12 bg-slate-800 rounded-full" />
                  </div>
                ))}
              </div>
            ) : topBrands.length === 0 ? (
              <div className="py-10 text-center text-sm text-slate-500 font-bold uppercase tracking-widest">No brand data established</div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-800/80 bg-slate-900">
                    <th className="px-6 py-3 text-left text-[10px] uppercase font-black tracking-widest text-slate-500 w-12">#</th>
                    <th className="px-6 py-3 text-left text-[10px] uppercase font-black tracking-widest text-slate-500">Brand</th>
                    <th className="px-6 py-3 text-right text-[10px] uppercase font-black tracking-widest text-slate-500">Reviews</th>
                    <th className="px-6 py-3 text-right text-[10px] uppercase font-black tracking-widest text-slate-500">Avg Rating</th>
                    <th className="px-6 py-3 text-right text-[10px] uppercase font-black tracking-widest text-slate-500">Sentiment</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {topBrands.map((b, idx) => {
                    const sentColor = b.avg_sentiment != null
                      ? b.avg_sentiment > 0.2 ? "text-emerald-400"
                      : b.avg_sentiment < -0.1 ? "text-red-400"
                      : "text-amber-400"
                      : "text-slate-500";
                    return (
                      <tr key={b.id} className="hover:bg-slate-800/30 transition-colors">
                        <td className="px-6 py-4 text-slate-500 font-black tabular-nums">{idx + 1}</td>
                        <td className="px-6 py-4 font-bold text-slate-200">
                          {b.name}
                          <span className="block text-[10px] uppercase tracking-widest text-slate-600 font-medium mt-1">{b.country_of_origin ?? "Unknown Origin"}</span>
                        </td>
                        <td className="px-6 py-4 text-right tabular-nums text-slate-400 font-mono">{b.review_count.toLocaleString()}</td>
                        <td className="px-6 py-4 text-right tabular-nums">
                          {b.avg_rating != null ? (
                            <span className="flex items-center justify-end gap-1.5">
                              <Star className="h-3 w-3 text-amber-400" />
                              <span className="font-bold text-slate-300">{b.avg_rating.toFixed(1)}</span>
                            </span>
                          ) : <span className="text-slate-600">—</span>}
                        </td>
                        <td className={clsx("px-6 py-4 text-right tabular-nums font-mono font-bold", sentColor)}>
                          {b.avg_sentiment != null
                            ? (b.avg_sentiment >= 0 ? "+" : "") + b.avg_sentiment.toFixed(3)
                            : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Review Sources chart */}
        <div>
          <h2 className="text-base font-bold uppercase tracking-widest text-slate-500 mb-6">Ingestion Sources Distribution</h2>
          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 h-[calc(100%-3rem)] flex flex-col backdrop-blur-md">
            {isLoading ? (
              <div className="flex-1 animate-pulse bg-slate-800/50 rounded-lg" />
            ) : reviewSources.length === 0 ? (
              <div className="flex-1 flex items-center justify-center text-sm text-slate-500 font-bold uppercase tracking-widest">No source metrics</div>
            ) : (
              <>
                <ResponsiveContainer width="100%" height={260} className="flex-1">
                  <BarChart data={reviewSources} layout="vertical"
                    margin={{ top: 0, right: 20, left: 10, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#1e293b" />
                    <XAxis type="number" tick={{ fontSize: 11, fill: "#64748b" }} axisLine={false} tickLine={false} />
                    <YAxis type="category" dataKey="source" tick={{ fontSize: 11, fill: "#94a3b8", fontWeight: "bold" }}
                      axisLine={false} tickLine={false} width={100} />
                    <Tooltip
                      contentStyle={{ backgroundColor: "#0f172a", fontSize: 12, borderRadius: 8, border: "1px solid #1e293b", color: "#f8fafc" }}
                      formatter={(v: number) => [v.toLocaleString(), "Reviews"]}
                      itemStyle={{ color: "#f8fafc", fontWeight: "bold" }}
                    />
                    <Bar dataKey="count" radius={[0, 4, 4, 0]} name="Reviews">
                      {reviewSources.map((_, i) => (
                        <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
                <div className="mt-6 flex flex-wrap gap-4 px-4">
                  {reviewSources.map((s, i) => (
                    <span key={s.source} className="flex items-center gap-2 text-xs font-bold tracking-wider text-slate-400 uppercase">
                      <span className="h-2 w-2 rounded-full flex-shrink-0 animate-pulse" style={{ backgroundColor: PALETTE[i % PALETTE.length] }} />
                      {s.source}
                    </span>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-8 pt-4">

        {/* Pipeline Steps */}
        <div>
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-base font-bold uppercase tracking-widest text-slate-500">ETL Pipeline Status</h2>
            <button onClick={() => refetch()} className="flex items-center gap-2 text-[10px] font-black uppercase tracking-widest text-brand-400 hover:text-brand-300 transition-colors">
              <RefreshCw className="h-3 w-3" /> Execute Refresh
            </button>
          </div>
          <div className="bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden backdrop-blur-md">
            {isLoading ? (
              <div className="divide-y divide-slate-800">
                {[...Array(5)].map((_, i) => (
                  <div key={i} className="flex items-center gap-3 px-6 py-4 animate-pulse">
                    <div className="h-3 w-24 bg-slate-800 rounded" />
                    <div className="flex-1 h-3 bg-slate-800 rounded" />
                    <div className="h-5 w-16 bg-slate-800 rounded-full" />
                  </div>
                ))}
              </div>
            ) : stepEntries.length === 0 ? (
              <div className="py-12 text-center">
                <Activity className="h-8 w-8 text-slate-700 mx-auto mb-3" />
                <p className="text-sm font-bold tracking-widest uppercase text-slate-600">No telemetry recorded</p>
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-800/80 bg-slate-900">
                    <th className="px-6 py-3 text-left text-[10px] uppercase font-black tracking-widest text-slate-500">Subsystem</th>
                    <th className="px-6 py-3 text-left text-[10px] uppercase font-black tracking-widest text-slate-500">Status</th>
                    <th className="px-6 py-3 text-right text-[10px] uppercase font-black tracking-widest text-slate-500">Throughput</th>
                    <th className="px-6 py-3 text-right text-[10px] uppercase font-black tracking-widest text-slate-500">Latency</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {stepEntries.map(([name, step]) => (
                    <tr key={name} className="hover:bg-slate-800/30 transition-colors">
                      <td className="px-6 py-4 font-bold text-slate-300 uppercase tracking-wider text-[11px]">{name.replace(/_/g, " ")}</td>
                      <td className="px-6 py-4">
                        <span className={clsx(
                          "inline-flex items-center px-2 py-0.5 rounded text-[9px] font-black uppercase tracking-widest border",
                          step.status === "running" ? "bg-blue-500/10 text-blue-400 border-blue-500/30" :
                          step.status === "completed" ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30" :
                          step.status === "failed" ? "bg-red-500/10 text-red-400 border-red-500/30" :
                          "bg-slate-800 text-slate-500 border-slate-700"
                        )}>
                          {step.status}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right font-mono font-medium text-slate-400">{step.records_processed.toLocaleString()}</td>
                      <td className="px-6 py-4 text-right font-mono font-medium text-slate-500">
                        {step.duration_ms != null
                          ? step.duration_ms >= 1000 ? `${(step.duration_ms / 1000).toFixed(1)}s` : `${step.duration_ms}ms`
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Source Health */}
        <div>
          <h2 className="text-base font-bold uppercase tracking-widest text-slate-500 mb-6">Service Health</h2>
          <div className="bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden backdrop-blur-md">
            {isLoading ? (
              <div className="divide-y divide-slate-800">
                {[...Array(5)].map((_, i) => (
                  <div key={i} className="flex items-center gap-3 px-6 py-4 animate-pulse">
                    <div className="h-3 w-28 bg-slate-800 rounded" />
                    <div className="flex-1 h-3 bg-slate-800 rounded" />
                    <div className="h-5 w-12 bg-slate-800 rounded-full" />
                  </div>
                ))}
              </div>
            ) : sources.length === 0 ? (
              <div className="py-12 text-center">
                <Activity className="h-8 w-8 text-slate-700 mx-auto mb-3" />
                <p className="text-sm font-bold tracking-widest uppercase text-slate-600">Awaiting Service Pings</p>
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-800/80 bg-slate-900">
                    <th className="px-6 py-3 text-left text-[10px] uppercase font-black tracking-widest text-slate-500">Module</th>
                    <th className="px-6 py-3 text-right text-[10px] uppercase font-black tracking-widest text-slate-500">Cycles</th>
                    <th className="px-6 py-3 text-right text-[10px] uppercase font-black tracking-widest text-slate-500">Uptime</th>
                    <th className="px-6 py-3 text-right text-[10px] uppercase font-black tracking-widest text-slate-500">Last Sync</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {sources.map((src) => {
                    const rate = src.success_rate != null ? src.success_rate
                      : src.total_runs > 0 ? (src.successful_runs / src.total_runs) * 100 : null;
                    return (
                      <tr key={src.scraper_name} className="hover:bg-slate-800/30 transition-colors">
                        <td className="px-6 py-4 font-bold text-slate-300 max-w-[140px] truncate uppercase tracking-widest text-[11px]">
                          {src.scraper_name.replace(/_/g, " ")}
                        </td>
                        <td className="px-6 py-4 text-right font-mono font-medium text-slate-500">{src.total_runs}</td>
                        <td className="px-6 py-4 text-right font-mono">
                          {rate != null ? (
                            <span className={clsx("font-bold",
                              rate >= 80 ? "text-emerald-400" : rate >= 50 ? "text-amber-400" : "text-red-400")}>
                              {rate.toFixed(0)}%
                            </span>
                          ) : <span className="text-slate-600">—</span>}
                        </td>
                        <td className="px-6 py-4 text-right font-mono text-slate-500 text-xs">
                          {src.last_run_at
                            ? formatDistanceToNow(new Date(src.last_run_at), { addSuffix: true })
                            : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>

      {/* Recent Failures */}
      <div className="pt-4 pb-8">
        <h2 className="text-base font-bold uppercase tracking-widest text-slate-500 mb-6">Service Interruptions & Exceptions</h2>
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden backdrop-blur-md">
          {isLoading ? (
            <div className="divide-y divide-slate-800">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="flex items-start gap-3 px-6 py-5 animate-pulse">
                  <div className="h-4 w-4 bg-slate-800 rounded-full mt-0.5" />
                  <div className="flex-1 space-y-2">
                    <div className="h-3 w-48 bg-slate-800 rounded" />
                    <div className="h-3 w-full bg-slate-800 rounded" />
                  </div>
                </div>
              ))}
            </div>
          ) : failures.length === 0 ? (
            <div className="py-12 flex flex-col items-center justify-center gap-3">
              <div className="h-12 w-12 rounded-full border border-emerald-500/20 bg-emerald-500/10 flex items-center justify-center">
                <AlertTriangle className="h-6 w-6 text-emerald-500" />
              </div>
              <p className="text-sm font-black tracking-widest uppercase text-emerald-500/80">Zero Critical Exceptions</p>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-800/80 bg-slate-900">
                  <th className="px-6 py-3 text-left text-[10px] uppercase font-black tracking-widest text-slate-500">Vector</th>
                  <th className="px-6 py-3 text-left text-[10px] uppercase font-black tracking-widest text-slate-500">Namespace</th>
                  <th className="px-6 py-3 text-left text-[10px] uppercase font-black tracking-widest text-slate-500">Error Payload</th>
                  <th className="px-6 py-3 text-left text-[10px] uppercase font-black tracking-widest text-slate-500">URI</th>
                  <th className="px-6 py-3 text-right text-[10px] uppercase font-black tracking-widest text-slate-500">T-Minus</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {failures.map((f, i) => (
                  <tr key={i} className="hover:bg-slate-800/30 transition-colors">
                    <td className="px-6 py-4">
                      <span className={clsx("inline-flex items-center px-2 py-0.5 rounded text-[9px] font-black uppercase tracking-widest border",
                        f.source === "scraping" ? "bg-amber-500/10 text-amber-500 border-amber-500/30" : "bg-red-500/10 text-red-400 border-red-500/30")}>
                        {f.source}
                      </span>
                    </td>
                    <td className="px-6 py-4 font-bold text-slate-300 uppercase tracking-widest text-[10px]">{f.category ?? f.entity_type ?? "N/A"}</td>
                    <td className="px-6 py-4 text-slate-400 font-mono text-xs max-w-xs truncate" title={f.message}>{f.message}</td>
                    <td className="px-6 py-4">
                      {f.source_url ? (
                        <a href={f.source_url} target="_blank" rel="noreferrer"
                          className="flex items-center gap-1.5 text-[10px] font-black uppercase tracking-widest text-brand-400 hover:text-brand-300">
                          <ExternalLink className="h-3 w-3" />
                          {(() => { try { return new URL(f.source_url).hostname; } catch { return "LINK"; } })()}
                        </a>
                      ) : <span className="text-slate-600">—</span>}
                    </td>
                    <td className="px-6 py-4 text-right text-slate-500 font-mono text-xs whitespace-nowrap">
                      {formatDistanceToNow(new Date(f.occurred_at), { addSuffix: true })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

// ------------------------------------
// UI Helpers
// ------------------------------------

function CinKpi({ label, value, icon, color }: { label: string; value: React.ReactNode; icon: React.ReactNode; color: "brand"|"blue"|"emerald"|"amber"|"red" }) {
  const accentMap = {
    brand: "text-brand-400 bg-brand-500/10 border-brand-500/20 border-l-brand-500 group-hover:shadow-[0_0_20px_rgba(99,102,241,0.15)]",
    blue: "text-blue-400 bg-blue-500/10 border-blue-500/20 border-l-blue-500 group-hover:shadow-[0_0_20px_rgba(59,130,246,0.15)]",
    emerald: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20 border-l-emerald-500 group-hover:shadow-[0_0_20px_rgba(16,185,129,0.15)]",
    amber: "text-amber-400 bg-amber-500/10 border-amber-500/20 border-l-amber-500 group-hover:shadow-[0_0_20px_rgba(245,158,11,0.15)]",
    red: "text-red-400 bg-red-500/10 border-red-500/20 border-l-red-500 group-hover:shadow-[0_0_20px_rgba(239,68,68,0.15)]",
  };
  
  return (
    <div className={clsx("bg-slate-900/60 border-y border-r border-l-4 rounded-xl p-5 transition-all duration-500 hover:-translate-y-1 group relative overflow-hidden", accentMap[color])}>
      <div className="absolute right-0 top-0 opacity-[0.03] scale-[4] translate-x-4 -translate-y-4 group-hover:scale-[4.5] group-hover:opacity-10 transition-all duration-700 text-white">
        {icon}
      </div>
      <div className="flex flex-col h-full relative z-10">
        <div className="mb-4 text-white/50">
          {icon}
        </div>
        <div className="text-3xl font-black text-white font-mono tracking-tighter mb-1">
          {typeof value === 'number' ? value.toLocaleString() : value}
        </div>
        <div className="text-[10px] font-bold uppercase tracking-widest text-slate-400">
          {label}
        </div>
      </div>
    </div>
  );
}

function ProvenancePill({ label, value, color }: { label: string; value: number; color: "emerald" | "slate" | "indigo" | "amber" }) {
  const colors = {
    emerald: "bg-emerald-500/10 border-emerald-500/30 text-emerald-400",
    slate:   "bg-slate-800/50 border-slate-700 text-slate-400",
    indigo:  "bg-indigo-500/10 border-indigo-500/30 text-indigo-400",
    amber:   "bg-amber-500/10 border-amber-500/30 text-amber-400",
  };
  return (
    <span className={clsx("inline-flex items-center gap-2 rounded-lg border px-3 py-1.5", colors[color])}>
      <span className="tabular-nums font-mono font-bold">{value.toLocaleString()}</span>
      <span className="text-[10px] uppercase font-bold tracking-widest opacity-80">{label}</span>
    </span>
  );
}

function NlpCoverageCard({ label, loading, total, processed, pct, color }: {
  label: string; loading: boolean; total: number;
  processed: number; pct: number; color: "brand" | "blue";
}) {
  if (loading) return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 animate-pulse">
      <div className="h-3 w-32 bg-slate-800 rounded mb-5" />
      <div className="h-2 w-full bg-slate-800 rounded-full mb-4" />
      <div className="flex justify-between">
        <div className="h-3 w-20 bg-slate-800 rounded" />
        <div className="h-3 w-12 bg-slate-800 rounded" />
      </div>
    </div>
  );
  
  const trackColor = color === "brand" ? "bg-brand-500 shadow-[0_0_10px_rgba(99,102,241,0.8)]" : "bg-blue-500 shadow-[0_0_10px_rgba(59,130,246,0.8)]";
  const textColor = color === "brand" ? "text-brand-400" : "text-blue-400";
  const glowBorder = color === "brand" ? "border-brand-500/20 hover:border-brand-500/50" : "border-blue-500/20 hover:border-blue-500/50";
  
  return (
    <div className={clsx("bg-slate-900/60 border rounded-xl p-6 transition-colors backdrop-blur-md", glowBorder)}>
      <div className="flex items-center justify-between mb-4">
        <span className="text-[10px] font-black uppercase tracking-widest text-slate-400">{label}</span>
        <span className={clsx("text-xl font-black font-mono tabular-nums", textColor)}>{pct.toFixed(1)}%</span>
      </div>
      <div className="h-2 w-full bg-slate-800/80 rounded-full overflow-hidden shadow-inner relative">
        <div className={clsx("h-full rounded-full transition-all duration-1000 ease-out", trackColor)}
          style={{ width: `${Math.min(100, pct)}%` }} />
      </div>
      <div className="flex items-center justify-between mt-3">
        <span className="text-[10px] font-bold uppercase tracking-widest text-slate-500"><span className="text-slate-300">{processed.toLocaleString()}</span> / {total.toLocaleString()} PROCESSED</span>
        {total > 0 && total !== processed && (
          <span className="text-[10px] font-bold uppercase tracking-widest text-amber-500/80 animate-pulse">{(total - processed).toLocaleString()} PENDING</span>
        )}
      </div>
    </div>
  );
}
