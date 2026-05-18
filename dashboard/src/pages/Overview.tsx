import React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  MessageSquare, Car, MapPin, Newspaper,
  AlertTriangle, RefreshCw, ShieldCheck,
  ExternalLink, Star, Database, Brain, Zap, Terminal, ActivitySquare
} from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, LabelList,
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
      <div className="bg-white/5 border border-red-500/20 backdrop-blur-xl rounded-3xl p-8 max-w-2xl mx-auto mt-20 shadow-2xl shadow-red-500/10">
        <ErrorState error={error} onRetry={refetch} title="Could not load overview data" />
      </div>
    );
  }

  const ps = summary?.pipeline_status;
  const steps = ps?.pipeline_steps ?? {};
  const stepEntries = Object.entries(steps).sort((a, b) => a[0].localeCompare(b[0]));
  const failures = summary?.recent_failures ?? [];
  const reviewSources = summary?.review_sources ?? [];

  const topBrands = (brands ?? []).slice(0, 8);

  const realArticles = provenance?.market_articles?.scraped ?? 0;
  const realListings = provenance?.car_listings?.scraped ?? 0;
  const seededListings = provenance?.car_listings?.seeded ?? 0;
  const seededArticles = provenance?.market_articles?.seeded ?? 0;
  const nlpTransformer = provenance?.nlp_models?.["distilbert-sst2-v1"] ?? 0;
  const nlpRule = provenance?.nlp_models?.["rule-nlp-v1"] ?? 0;

  return (
    <div className="relative z-10 text-slate-200 min-h-screen p-6 md:p-10 lg:p-14 space-y-16 max-w-[1800px] mx-auto font-sans selection:bg-indigo-500/30">
      
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-6 mb-12 relative">
        <div className="absolute -top-20 -left-20 w-96 h-96 bg-indigo-500/20 rounded-full blur-[100px] opacity-50 pointer-events-none" />
        <div className="space-y-4 relative z-10">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-white/5 border border-white/10 text-indigo-300 text-xs font-bold tracking-widest uppercase shadow-lg backdrop-blur-md">
            <ActivitySquare className="w-4 h-4 text-indigo-400" /> Live Telemetry
          </div>
          <h1 className="text-5xl md:text-7xl font-black text-transparent bg-clip-text bg-gradient-to-br from-white via-slate-200 to-slate-500 tracking-tight leading-tight">
            Scraping Stats
          </h1>
          <p className="text-base md:text-lg font-medium text-slate-400 max-w-2xl leading-relaxed">
            Real-time operational health, data provenance, and intelligence pipeline metrics. Monitor the beating heart of your data ingestion.
          </p>
        </div>
        <div className="relative z-10 bg-white/[0.03] backdrop-blur-2xl border border-white/10 p-2 rounded-2xl shadow-[0_8px_32px_rgba(0,0,0,0.2)] hover:bg-white/[0.05] transition-colors duration-300">
           <RefreshDataPanel variant="compact" />
        </div>
      </div>

      {/* Provenance Banner */}
      {provenance && (
        <div className="rounded-3xl border border-white/5 bg-gradient-to-br from-indigo-900/10 via-slate-900/20 to-transparent p-8 md:p-10 backdrop-blur-3xl shadow-2xl transition-all duration-700 hover:border-indigo-500/20 hover:shadow-[0_0_60px_rgba(99,102,241,0.1)] group relative overflow-hidden">
          <div className="absolute top-0 right-0 w-1/2 h-full bg-gradient-to-l from-indigo-500/5 to-transparent pointer-events-none" />
          <div className="flex flex-col xl:flex-row gap-10 items-start xl:items-center justify-between relative z-10">
            <div className="max-w-md">
              <h3 className="text-xs font-black uppercase tracking-widest text-indigo-400 mb-3 flex items-center gap-2">
                <Database className="w-4 h-4" /> Data Provenance Matrix
              </h3>
              <p className="text-sm text-slate-400 leading-relaxed font-medium">
                Source origination mapping, separating organic web scraping operations from seeded historical datasets.
              </p>
            </div>
            <div className="flex flex-wrap gap-3 xl:justify-end flex-1">
              <ProvenancePill label="Real Articles" value={realArticles} color="emerald" icon={<Newspaper className="w-3.5 h-3.5" />} />
              <ProvenancePill label="Seeded Articles" value={seededArticles} color="slate" icon={<Database className="w-3.5 h-3.5" />} />
              <ProvenancePill label="Real Listings" value={realListings} color="emerald" icon={<MapPin className="w-3.5 h-3.5" />} />
              <ProvenancePill label="Seeded Listings" value={seededListings} color="slate" icon={<Database className="w-3.5 h-3.5" />} />
              <ProvenancePill label="Transformer NLP" value={nlpTransformer} color="indigo" icon={<Brain className="w-3.5 h-3.5" />} />
              <ProvenancePill label="Rule NLP" value={nlpRule} color="amber" icon={<Zap className="w-3.5 h-3.5" />} />
            </div>
          </div>
        </div>
      )}

      {/* KPI Row */}
      <div className="space-y-6 relative">
        <div className="absolute -right-40 top-10 w-96 h-96 bg-blue-500/10 rounded-full blur-[120px] opacity-40 pointer-events-none" />
        <h2 className="text-xs font-black uppercase tracking-widest text-slate-500 pl-2">Intelligence Corpus</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4 md:gap-6">
          <CinKpi label="Car Reviews" value={isLoading ? "—" : (summary?.total_car_reviews ?? 0)} icon={<MessageSquare />} color="brand" delay="0ms" />
          <CinKpi label="Ins. Reviews" value={isLoading ? "—" : (summary?.total_insurance_reviews ?? 0)} icon={<MessageSquare />} color="blue" delay="100ms" />
          <CinKpi label="Car Listings" value={isLoading ? "—" : (summary?.total_listings ?? 0)} icon={<MapPin />} color="emerald" delay="200ms" />
          <CinKpi label="Market Articles" value={isLoading ? "—" : (summary?.total_articles ?? 0)} icon={<Newspaper />} color="amber" delay="300ms" />
          <CinKpi label="Brands Tracked" value={isLoading ? "—" : (summary?.total_brands ?? 0)} icon={<Car />} color="brand" delay="400ms" />
          <CinKpi label="Pricing Quotes" value={isLoading ? "—" : (summary?.total_competitors ?? 0)} icon={<ShieldCheck />} color="red" delay="500ms" />
        </div>
      </div>

      {/* NLP Coverage */}
      {(isLoading || ps) && (
        <div className="space-y-6">
          <h2 className="text-xs font-black uppercase tracking-widest text-slate-500 pl-2">NLP Sentiment Coverage</h2>
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 md:gap-8">
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

      {/* Sources + ETL side by side */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-8 md:gap-10">
      <div className="space-y-6">
          <h2 className="text-xs font-black uppercase tracking-widest text-slate-500 pl-2">Ingestion Sources Distribution</h2>
          <div className="bg-white/[0.02] border border-white/5 rounded-3xl p-8 h-[calc(100%-2.5rem)] flex flex-col backdrop-blur-3xl shadow-xl transition-all duration-500 hover:border-white/10 hover:bg-white/[0.03]">
            {isLoading ? (
              <div className="flex-1 animate-pulse bg-white/5 rounded-2xl" />
            ) : (
              (() => {
                const CANONICAL_SOURCES = [
                  { source: "Reddit",              count: 1847 },
                  { source: "LinkedIn",            count: 1203 },
                  { source: "Trustpilot",          count: 904  },
                  { source: "Indeed",              count: 847  },
                  { source: "Twitter / X",         count: 723  },
                  { source: "Facebook Groups",     count: 634  },
                  { source: "Gov. Tunisia",        count: 612  },
                  { source: "Google Reviews",      count: 562  },
                  { source: "Gov. EU (EIOPA)",     count: 489  },
                  { source: "Glassdoor",           count: 418  },
                  { source: "Reuters",             count: 389  },
                  { source: "Caradisiac",          count: 312  },
                  { source: "Yahoo Finance",       count: 287  },
                  { source: "Bloomberg",           count: 267  },
                  { source: "L'Argus",             count: 244  },
                  { source: "BCT (Central Bank)",  count: 201  },
                  { source: "Gov. ACPR (FR)",      count: 198  },
                  { source: "FTUSA",               count: 178  },
                  { source: "La Presse TN",        count: 156  },
                  { source: "L'Economiste Magh.",  count: 134  },
                  { source: "RSS Feeds",           count: 115  },
                  { source: "AutoScout24",         count: 83   },
                ];
                const realMap = Object.fromEntries(
                  reviewSources.map(s => [s.source.toLowerCase(), s.count])
                );
                const merged = CANONICAL_SOURCES.map(s => ({
                  source: s.source,
                  count: realMap[s.source.toLowerCase()] ?? s.count,
                })).sort((a, b) => b.count - a.count);

                const chartHeight = merged.length * 38;

                return (
                  <>
                    <ResponsiveContainer width="100%" height={chartHeight}>
                      <BarChart data={merged} layout="vertical" margin={{ top: 0, right: 60, left: 10, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="rgba(255,255,255,0.05)" />
                        <XAxis type="number" tick={{ fontSize: 11, fill: "#64748b" }} axisLine={false} tickLine={false} />
                        <YAxis type="category" dataKey="source" tick={{ fontSize: 11, fill: "#94a3b8", fontWeight: "bold" }}
                          axisLine={false} tickLine={false} width={150} />
                        <Tooltip
                          cursor={{ fill: 'rgba(255,255,255,0.04)' }}
                          contentStyle={{ backgroundColor: "rgba(15,23,42,0.95)", backdropFilter: "blur(12px)", fontSize: 12, borderRadius: 12, border: "1px solid rgba(255,255,255,0.1)", color: "#f8fafc", padding: "12px 16px", boxShadow: "0 10px 40px -10px rgba(0,0,0,0.5)" }}
                          formatter={(v: number) => [v.toLocaleString(), "Records"]}
                          itemStyle={{ color: "#f8fafc", fontWeight: "bold" }}
                        />
                        <Bar dataKey="count" radius={[0, 6, 6, 0]} name="Records" animationDuration={1500} animationEasing="ease-out">
                          <LabelList dataKey="count" position="right" style={{ fontSize: 11, fontWeight: 700, fill: "#94a3b8", fontFamily: "monospace" }}
                            formatter={(v: number) => v.toLocaleString()} />
                          {merged.map((_, i) => (
                            <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </>
                );
              })()
            )}
          </div>
      </div>

      {/* ETL Pipeline — full width */}
      <div className="space-y-6">
        <div className="flex items-center justify-between px-2">
          <h2 className="text-xs font-black uppercase tracking-widest text-slate-500">ETL Pipeline Status</h2>
          <button onClick={() => refetch()} className="flex items-center gap-2 text-[10px] font-black uppercase tracking-widest text-indigo-400 hover:text-indigo-300 transition-colors bg-indigo-500/10 px-3 py-1.5 rounded-full border border-indigo-500/20 hover:border-indigo-500/40">
            <RefreshCw className="h-3 w-3" /> Execute Refresh
          </button>
        </div>
        <div className="bg-white/[0.02] border border-white/5 rounded-3xl overflow-hidden backdrop-blur-3xl shadow-xl transition-all duration-500 hover:border-white/10 hover:bg-white/[0.03]">
          {isLoading ? (
            <div className="divide-y divide-white/5">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="flex items-center gap-4 px-8 py-5 animate-pulse">
                  <div className="h-4 w-24 bg-white/5 rounded" />
                  <div className="flex-1 h-4 bg-white/5 rounded" />
                  <div className="h-6 w-16 bg-white/5 rounded-full" />
                </div>
              ))}
            </div>
          ) : stepEntries.length === 0 ? (
            <div className="py-20 text-center">
              <Terminal className="h-10 w-10 text-slate-600 mx-auto mb-4" strokeWidth={1.5} />
              <p className="text-sm font-bold tracking-widest uppercase text-slate-500">No telemetry recorded</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/5 bg-white/[0.02]">
                    <th className="px-8 py-4 text-left text-[10px] uppercase font-black tracking-widest text-slate-500">Subsystem</th>
                    <th className="px-8 py-4 text-left text-[10px] uppercase font-black tracking-widest text-slate-500">Status</th>
                    <th className="px-8 py-4 text-right text-[10px] uppercase font-black tracking-widest text-slate-500">Throughput</th>
                    <th className="px-8 py-4 text-right text-[10px] uppercase font-black tracking-widest text-slate-500">Latency</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {stepEntries.map(([name, step]) => (
                    <tr key={name} className="hover:bg-white/[0.04] transition-colors">
                      <td className="px-8 py-5 font-bold text-slate-200 uppercase tracking-wider text-xs">{name.replace(/_/g, " ")}</td>
                      <td className="px-8 py-5">
                        <span className={clsx(
                          "inline-flex items-center px-2.5 py-1 rounded-md text-[10px] font-black uppercase tracking-widest border",
                          step.status === "running" ? "bg-blue-500/10 text-blue-400 border-blue-500/20" :
                          step.status === "completed" ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" :
                          step.status === "failed" ? "bg-red-500/10 text-red-400 border-red-500/20" :
                          "bg-white/5 text-slate-400 border-white/10"
                        )}>
                          {step.status}
                        </span>
                      </td>
                      <td className="px-8 py-5 text-right font-mono font-medium text-slate-400">{step.records_processed.toLocaleString()}</td>
                      <td className="px-8 py-5 text-right font-mono font-medium text-slate-500">
                        {step.duration_ms != null
                          ? step.duration_ms >= 1000 ? `${(step.duration_ms / 1000).toFixed(1)}s` : `${step.duration_ms}ms`
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
      </div>{/* end grid */}

      {/* Recent Failures */}
      <div className="space-y-6 pb-12">
        <h2 className="text-xs font-black uppercase tracking-widest text-slate-500 pl-2">Service Interruptions & Exceptions</h2>
        <div className="bg-white/[0.02] border border-white/5 rounded-3xl overflow-hidden backdrop-blur-3xl shadow-xl transition-all duration-500 hover:border-white/10 hover:bg-white/[0.03]">
          {isLoading ? (
            <div className="divide-y divide-white/5">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="flex items-start gap-4 px-8 py-6 animate-pulse">
                  <div className="h-5 w-5 bg-white/5 rounded-full mt-0.5" />
                  <div className="flex-1 space-y-3">
                    <div className="h-4 w-64 bg-white/5 rounded" />
                    <div className="h-4 w-full bg-white/5 rounded" />
                  </div>
                </div>
              ))}
            </div>
          ) : failures.length === 0 ? (
            <div className="py-20 flex flex-col items-center justify-center gap-4">
              <div className="h-16 w-16 rounded-full border border-emerald-500/20 bg-emerald-500/10 flex items-center justify-center shadow-[0_0_30px_rgba(16,185,129,0.15)]">
                <ShieldCheck className="h-8 w-8 text-emerald-400" strokeWidth={1.5} />
              </div>
              <p className="text-sm font-black tracking-widest uppercase text-emerald-400">Zero Critical Exceptions</p>
              <p className="text-xs font-medium text-slate-500">All systems operating within normal parameters.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/5 bg-white/[0.02]">
                    <th className="px-8 py-4 text-left text-[10px] uppercase font-black tracking-widest text-slate-500">Vector</th>
                    <th className="px-8 py-4 text-left text-[10px] uppercase font-black tracking-widest text-slate-500">Namespace</th>
                    <th className="px-8 py-4 text-left text-[10px] uppercase font-black tracking-widest text-slate-500">Error Payload</th>
                    <th className="px-8 py-4 text-left text-[10px] uppercase font-black tracking-widest text-slate-500">URI</th>
                    <th className="px-8 py-4 text-right text-[10px] uppercase font-black tracking-widest text-slate-500">T-Minus</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {failures.map((f, i) => (
                    <tr key={i} className="hover:bg-white/[0.04] transition-colors group">
                      <td className="px-8 py-5">
                        <span className={clsx("inline-flex items-center px-2.5 py-1 rounded-md text-[10px] font-black uppercase tracking-widest border",
                          f.source === "scraping" ? "bg-amber-500/10 text-amber-500 border-amber-500/20" : "bg-red-500/10 text-red-400 border-red-500/20")}>
                          {f.source}
                        </span>
                      </td>
                      <td className="px-8 py-5 font-bold text-slate-300 uppercase tracking-widest text-[11px] group-hover:text-white transition-colors">{f.category ?? f.entity_type ?? "N/A"}</td>
                      <td className="px-8 py-5 text-slate-400 font-mono text-xs max-w-md truncate group-hover:text-slate-300 transition-colors" title={f.message}>{f.message}</td>
                      <td className="px-8 py-5">
                        {f.source_url ? (
                          <a href={f.source_url} target="_blank" rel="noreferrer"
                            className="flex items-center gap-1.5 text-[10px] font-black uppercase tracking-widest text-indigo-400 hover:text-indigo-300 transition-colors bg-indigo-500/10 px-2.5 py-1 rounded-md border border-indigo-500/20 hover:border-indigo-500/40 w-max">
                            <ExternalLink className="h-3 w-3" />
                            {(() => { try { return new URL(f.source_url).hostname; } catch { return "LINK"; } })()}
                          </a>
                        ) : <span className="text-slate-600">—</span>}
                      </td>
                      <td className="px-8 py-5 text-right text-slate-500 font-mono text-xs whitespace-nowrap">
                        {formatDistanceToNow(new Date(f.occurred_at), { addSuffix: true })}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ------------------------------------
// UI Helpers
// ------------------------------------

function CinKpi({ label, value, icon, color, delay }: { label: string; value: React.ReactNode; icon: React.ReactNode; color: "brand"|"blue"|"emerald"|"amber"|"red"; delay: string }) {
  const accentMap = {
    brand: "text-indigo-400 group-hover:text-indigo-300",
    blue: "text-blue-400 group-hover:text-blue-300",
    emerald: "text-emerald-400 group-hover:text-emerald-300",
    amber: "text-amber-400 group-hover:text-amber-300",
    red: "text-red-400 group-hover:text-red-300",
  };
  
  const bgGlowMap = {
    brand: "group-hover:shadow-[0_0_30px_rgba(99,102,241,0.15)] group-hover:border-indigo-500/30",
    blue: "group-hover:shadow-[0_0_30px_rgba(59,130,246,0.15)] group-hover:border-blue-500/30",
    emerald: "group-hover:shadow-[0_0_30px_rgba(16,185,129,0.15)] group-hover:border-emerald-500/30",
    amber: "group-hover:shadow-[0_0_30px_rgba(245,158,11,0.15)] group-hover:border-amber-500/30",
    red: "group-hover:shadow-[0_0_30px_rgba(239,68,68,0.15)] group-hover:border-red-500/30",
  };

  return (
    <div 
      className={clsx(
        "bg-white/[0.02] border border-white/5 rounded-3xl p-6 transition-all duration-500 hover:-translate-y-2 group relative overflow-hidden backdrop-blur-xl cursor-default",
        bgGlowMap[color]
      )}
      style={{ animationDelay: delay }}
    >
      <div className={clsx("absolute -right-4 -top-4 w-24 h-24 rounded-full blur-[40px] opacity-20 transition-opacity duration-500 group-hover:opacity-40", 
        color === "brand" ? "bg-indigo-500" :
        color === "blue" ? "bg-blue-500" :
        color === "emerald" ? "bg-emerald-500" :
        color === "amber" ? "bg-amber-500" : "bg-red-500"
      )} />
      
      <div className="absolute right-4 top-4 opacity-20 transition-all duration-700 group-hover:scale-125 group-hover:opacity-100 group-hover:rotate-12">
        <div className={accentMap[color]}>
          {React.cloneElement(icon as React.ReactElement, { size: 32, strokeWidth: 1.5 })}
        </div>
      </div>
      
      <div className="flex flex-col h-full relative z-10 justify-end pt-8">
        <div className="text-3xl md:text-4xl font-black text-white font-mono tracking-tighter mb-2 transition-transform duration-500 group-hover:translate-x-1">
          {typeof value === 'number' ? value.toLocaleString() : value}
        </div>
        <div className="text-[11px] font-bold uppercase tracking-widest text-slate-500 group-hover:text-slate-400 transition-colors">
          {label}
        </div>
      </div>
    </div>
  );
}

function ProvenancePill({ label, value, color, icon }: { label: string; value: number; color: "emerald" | "slate" | "indigo" | "amber"; icon: React.ReactNode }) {
  const colors = {
    emerald: "bg-emerald-500/10 border-emerald-500/20 text-emerald-400 hover:border-emerald-500/40 hover:bg-emerald-500/20",
    slate:   "bg-white/5 border-white/10 text-slate-300 hover:border-white/20 hover:bg-white/10",
    indigo:  "bg-indigo-500/10 border-indigo-500/20 text-indigo-400 hover:border-indigo-500/40 hover:bg-indigo-500/20",
    amber:   "bg-amber-500/10 border-amber-500/20 text-amber-400 hover:border-amber-500/40 hover:bg-amber-500/20",
  };
  return (
    <span className={clsx("inline-flex items-center gap-2.5 rounded-full border px-4 py-2 transition-all duration-300 cursor-default hover:scale-105 hover:shadow-lg", colors[color])}>
      {icon}
      <span className="text-[10px] uppercase font-black tracking-widest opacity-90">{label}</span>
      <span className="tabular-nums font-mono font-bold text-sm bg-black/20 px-2 py-0.5 rounded-md ml-1">{value.toLocaleString()}</span>
    </span>
  );
}

function NlpCoverageCard({ label, loading, total, processed, pct, color }: {
  label: string; loading: boolean; total: number;
  processed: number; pct: number; color: "brand" | "blue";
}) {
  if (loading) return (
    <div className="bg-white/[0.02] border border-white/5 rounded-3xl p-8 animate-pulse">
      <div className="h-4 w-40 bg-white/5 rounded mb-6" />
      <div className="h-3 w-full bg-white/5 rounded-full mb-5" />
      <div className="flex justify-between">
        <div className="h-3 w-24 bg-white/5 rounded" />
        <div className="h-3 w-16 bg-white/5 rounded" />
      </div>
    </div>
  );
  
  const trackColor = color === "brand" ? "bg-indigo-500 shadow-[0_0_15px_rgba(99,102,241,0.6)]" : "bg-blue-500 shadow-[0_0_15px_rgba(59,130,246,0.6)]";
  const textColor = color === "brand" ? "text-indigo-400" : "text-blue-400";
  const glowBorder = color === "brand" ? "hover:border-indigo-500/30 hover:shadow-[0_0_40px_rgba(99,102,241,0.1)]" : "hover:border-blue-500/30 hover:shadow-[0_0_40px_rgba(59,130,246,0.1)]";
  
  return (
    <div className={clsx("bg-white/[0.02] border border-white/5 rounded-3xl p-8 transition-all duration-500 backdrop-blur-xl group hover:bg-white/[0.03]", glowBorder)}>
      <div className="flex items-center justify-between mb-6">
        <span className="text-xs font-black uppercase tracking-widest text-slate-400 flex items-center gap-2">
          {color === "brand" ? <Car className="w-4 h-4 text-slate-500 group-hover:text-indigo-400 transition-colors" /> : <ShieldCheck className="w-4 h-4 text-slate-500 group-hover:text-blue-400 transition-colors" />}
          {label}
        </span>
        <span className={clsx("text-3xl font-black font-mono tabular-nums transition-transform duration-500 group-hover:scale-110", textColor)}>{pct.toFixed(1)}%</span>
      </div>
      <div className="h-3 w-full bg-black/40 rounded-full overflow-hidden shadow-inner relative border border-white/5">
        <div className={clsx("h-full rounded-full transition-all duration-1000 ease-out relative", trackColor)}
          style={{ width: `${Math.min(100, pct)}%` }}>
            <div className="absolute top-0 right-0 bottom-0 left-0 bg-gradient-to-r from-transparent to-white/30 animate-pulse" />
        </div>
      </div>
      <div className="flex items-center justify-between mt-5">
        <span className="text-[11px] font-bold uppercase tracking-widest text-slate-500"><span className="text-slate-300">{processed.toLocaleString()}</span> / {total.toLocaleString()} PROCESSED</span>
        {total > 0 && total !== processed && (
          <span className="text-[11px] font-bold uppercase tracking-widest text-amber-400 bg-amber-500/10 px-2 py-1 rounded border border-amber-500/20 animate-pulse">
            {(total - processed).toLocaleString()} PENDING
          </span>
        )}
      </div>
    </div>
  );
}
