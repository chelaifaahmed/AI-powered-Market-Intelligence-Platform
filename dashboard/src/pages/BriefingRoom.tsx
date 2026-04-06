import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Star, Zap, Newspaper, Building2, ChevronDown, Activity, ArrowRight,
} from "lucide-react";
import {
  AreaChart, Area, XAxis, Tooltip, ResponsiveContainer,
} from "recharts";
import { api, BrandSummary, OpportunitySignal, OpportunitySummary, DashboardSummary } from "../api/client";
import { format } from "date-fns";
import clsx from "clsx";

/* ─── Constants ─── */

const LABELS: [string, string, string] = [
  "ERP OPPORTUNITY",
  "SENTIMENT SIGNAL",
  "MARKET INTELLIGENCE",
];

const SIGNAL_LABELS: [string, string, string] = [
  "ERP SIGNAL DETECTED",
  "SENTIMENT ALERT",
  "MARKET INTELLIGENCE",
];

const SIGNAL_COLORS: [string, string, string] = [
  "text-amber-500",
  "text-rose-500",
  "text-blue-500",
];

const STATIC_PARAGRAPHS: [string, string] = [
  "Opportunity scoring engine has flagged elevated complaint signals in this sector. ERP modernisation gap identified.",
  "Sentiment analysis across real customer reviews reveals a declining trust trend. Early signal for service quality intervention.",
];

/* ─── Component ─── */

export default function BriefingRoom() {
  /* --- Rotating state --- */
  const [state, setState] = useState(0);
  const [visible, setVisible] = useState(true);

  const advance = useCallback((next: number) => {
    setVisible(false);
    setTimeout(() => {
      setState(next);
      setVisible(true);
    }, 400); // slightly longer for dramatic fade
  }, []);

  useEffect(() => {
    const id = setInterval(() => {
      setVisible(false);
      setTimeout(() => {
        setState((p) => (p + 1) % 3);
        setVisible(true);
      }, 400);
    }, 6000); // 6 seconds for better reading time
    return () => clearInterval(id);
  }, []);

  /* --- Queries --- */
  const { data: summary } = useQuery<DashboardSummary>({
    queryKey: ["briefing-summary"],
    queryFn: api.dashboardSummary,
    staleTime: 5 * 60 * 1000,
  });

  const { data: opportunities } = useQuery<OpportunitySignal[]>({
    queryKey: ["briefing-opportunities"],
    queryFn: () => api.opportunities(),
    staleTime: 5 * 60 * 1000,
  });

  const { data: brands } = useQuery<BrandSummary[]>({
    queryKey: ["briefing-brands"],
    queryFn: () => api.brandsSummary(),
    staleTime: 5 * 60 * 1000,
  });

  const { data: oppSummary } = useQuery<OpportunitySummary>({
    queryKey: ["briefing-opp-summary"],
    queryFn: api.opportunitySummary,
    staleTime: 5 * 60 * 1000,
  });

  /* --- Derived data --- */
  const topOpp = opportunities && opportunities.length > 0
    ? opportunities.reduce((a, b) => (a.overall_score > b.overall_score ? a : b))
    : null;

  const worstBrand = brands && brands.length > 0
    ? brands.reduce((a, b) => {
        const as = a.avg_sentiment ?? 999;
        const bs = b.avg_sentiment ?? 999;
        return as < bs ? a : b;
      })
    : null;

  const top5 = (opportunities ?? [])
    .slice()
    .sort((a, b) => b.overall_score - a.overall_score)
    .slice(0, 5);
  const top2 = top5.slice(0, 2);

  const totalReviews = (summary?.total_car_reviews ?? 0) + (summary?.total_insurance_reviews ?? 0);
  const brandCount = summary?.total_brands ?? 0;
  const articleCount = summary?.total_articles ?? 0;
  const strongCount = oppSummary?.strong_signals ?? 0;

  /* --- Headlines per state --- */
  const headlines: [string, string, string] = [
    topOpp
      ? `${topOpp.entity_name} shows critical ERP modernisation signals`
      : "Market leader shows critical ERP modernisation signals",
    worstBrand
      ? `${worstBrand.name} customer satisfaction is declining`
      : "Leading brand customer satisfaction is declining",
    strongCount > 0
      ? `The market shows ${strongCount} urgent ERP opportunities this week`
      : totalReviews > 0
        ? `${totalReviews.toLocaleString()} customer reviews reveal structural gaps across ${brandCount} monitored brands`
        : "Market intelligence aggregating...",
  ];

  const attributions: [string, string, string] = [
    topOpp
      ? `Opportunity score: ${topOpp.overall_score}/100 • Sector: ${topOpp.entity_type} • Powered by scoring engine`
      : "Loading...",
    worstBrand
      ? `Based on ${worstBrand.review_count.toLocaleString()} real reviews • ${worstBrand.avg_sentiment != null ? (Math.abs(worstBrand.avg_sentiment) * 100).toFixed(0) : "?"}% negative sentiment detected`
      : "Loading...",
    `Across Tunisia and European markets • Updated ${format(new Date(), "dd MMM yyyy")}`,
  ];

  /* --- Dynamic context paragraphs --- */
  const paragraphs: [string, string, string] = [
    STATIC_PARAGRAPHS[0],
    STATIC_PARAGRAPHS[1],
    totalReviews > 0
      ? `Aggregated intelligence from ${totalReviews.toLocaleString()} customer reviews, ${articleCount.toLocaleString()} market articles, and real-time opportunity scoring across ${brandCount} monitored companies.`
      : "Aggregated intelligence from customer reviews, market articles, and real-time opportunity scoring across monitored companies.",
  ];

  /* --- Chart data --- */
  const sentimentData = (brands ?? [])
    .filter((b) => b.avg_sentiment != null && b.review_count > 0)
    .slice(0, 12)
    .map((b) => ({
      name: b.name.length > 6 ? b.name.slice(0, 6) : b.name,
      avg_sentiment_score: b.avg_sentiment != null ? Math.round((b.avg_sentiment + 1) * 50) : 50,
    }));

  const today = format(new Date(), "EEEE, dd MMMM yyyy");

  return (
    <div className="bg-slate-950 min-h-full text-slate-200 font-sans rounded-xl overflow-hidden relative">

      {/* ═══════════ SECTION 1 — HERO ═══════════ */}
      <section className="relative min-h-[calc(100vh-8rem)] flex flex-col px-8 lg:px-16 overflow-hidden">
        {/* Subtle Background Effects */}
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-slate-900 via-slate-950 to-slate-950 pointer-events-none" />
        <div className="absolute -top-32 -right-32 w-96 h-96 bg-brand-500/10 blur-[120px] rounded-full pointer-events-none" />
        <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[800px] h-[300px] bg-indigo-500/5 blur-[150px] rounded-full pointer-events-none" />



        {/* CENTERPIECE */}
        <div className="flex-1 flex flex-col justify-center items-center text-center relative z-10 max-w-5xl mx-auto w-full mb-12">
          
          <div className="flex flex-col items-center min-h-[400px] justify-center">
            {/* Animated Signal Badge */}
            <div 
              className={clsx(
                "inline-flex items-center gap-2 px-3 py-1 rounded-full border mb-8 transition-all duration-700",
                visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4",
                state === 0 && "border-amber-500/30 bg-amber-500/10",
                state === 1 && "border-rose-500/30 bg-rose-500/10",
                state === 2 && "border-blue-500/30 bg-blue-500/10"
              )}
            >
              <Activity className={clsx("w-3 h-3", SIGNAL_COLORS[state])} />
              <span className={clsx("text-[10px] font-bold tracking-widest uppercase", SIGNAL_COLORS[state])}>
                {SIGNAL_LABELS[state]}
              </span>
            </div>

            {/* The Big Headline */}
            <h1 
              className={clsx(
                "text-5xl md:text-6xl lg:text-7xl font-black text-white tracking-tight leading-[1.05] mb-6 transition-all duration-700 max-w-4xl",
                visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
              )}
            >
              {headlines[state]}
            </h1>
            
            {/* Paragraph / Context */}
            <p 
              className={clsx(
                "text-slate-400 text-lg md:text-xl max-w-2xl leading-relaxed mb-6 transition-all duration-700 delay-100",
                visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"
              )}
            >
              {paragraphs[state]}
            </p>

            {/* Attribution */}
            <p 
              className={clsx(
                "text-xs font-mono text-slate-500 tracking-wide transition-all duration-700 delay-200",
                visible ? "opacity-100" : "opacity-0"
              )}
            >
              {attributions[state]}
            </p>
          </div>

          {/* Controls */}
          <div className="flex gap-4 mt-12">
            {[0, 1, 2].map((i) => (
              <button
                key={i}
                onClick={() => advance(i)}
                aria-label={`Slide ${i + 1}`}
                className={clsx(
                  "w-12 h-1.5 rounded-full transition-all duration-300",
                  state === i ? "bg-white" : "bg-slate-800 hover:bg-slate-700"
                )}
              />
            ))}
          </div>

          {/* Scroll Prompt */}
          <div className="absolute bottom-12 left-1/2 -translate-x-1/2 flex flex-col items-center animate-bounce">
            <span className="text-[10px] tracking-widest uppercase text-slate-500 mb-2">Explore Intelligence</span>
            <ChevronDown className="w-4 h-4 text-slate-600" />
          </div>

        </div>
      </section>


      {/* ═══════════ SECTION 2 — DASHBOARD ═══════════ */}
      <section className="relative z-20 bg-slate-950 border-t border-white/5 pt-20 pb-32 px-8 lg:px-16 shadow-[0_-20px_40px_rgba(0,0,0,0.5)]">
        
        {/* Header */}
        <div className="flex items-end justify-between mb-12">
          <div>
            <h2 className="text-3xl font-black text-white tracking-tight">
              Live Market Pulse
            </h2>
            <p className="text-sm tracking-wide text-slate-400 mt-2">
              Key operational and reputational signals aggregated in real-time.
            </p>
          </div>
          <div className="hidden md:block w-24 h-1 bg-brand-500 rounded" />
        </div>

        {/* KPI CARDS */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6 mb-16">
          <KpiCardDark
            icon={<Star className="w-5 h-5 text-amber-500" />}
            value={totalReviews}
            label="Reviews Analyzed"
          />
          <KpiCardDark
            icon={<Zap className="w-5 h-5 text-emerald-500" />}
            value={strongCount}
            label="Active Opportunities"
          />
          <KpiCardDark
            icon={<Newspaper className="w-5 h-5 text-indigo-500" />}
            value={articleCount}
            label="Monitored Articles"
          />
          <KpiCardDark
            icon={<Building2 className="w-5 h-5 text-blue-500" />}
            value={brandCount}
            label="Tracked Entities"
          />
        </div>

        {/* CONTENT GRID */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-8">
          
          {/* LEFT — Top ERP Signals */}
          <div className="lg:col-span-2 flex flex-col">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h3 className="text-xl font-bold text-white">Top ERP Signals</h3>
                <p className="text-xs text-slate-400 mt-1 uppercase tracking-wider">Ranked by opportunity score</p>
              </div>
            </div>
            
            <div className="flex flex-col gap-3 flex-1">
              {top5.map((opp, i) => (
                <div
                  key={opp.entity_id}
                  className="bg-slate-900 border border-slate-800 rounded-lg p-4 transition-transform hover:-translate-y-1 hover:border-slate-700"
                >
                  <div className="flex justify-between items-start mb-3">
                    <div className="flex items-center gap-3">
                      <div className="w-6 h-6 rounded bg-slate-800 flex justify-center items-center text-xs font-bold text-slate-400">
                        {i + 1}
                      </div>
                      <span className="font-bold text-slate-200">
                        {opp.entity_name}
                      </span>
                    </div>
                    <span
                      className={clsx(
                        "text-[9px] font-bold uppercase tracking-wider px-2 py-1 rounded",
                        opp.entity_type === "insurance" 
                          ? "bg-blue-500/10 text-blue-400" 
                          : "bg-emerald-500/10 text-emerald-400"
                      )}
                    >
                      {opp.entity_type}
                    </span>
                  </div>
                  
                  <div className="flex items-center gap-4">
                    <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
                      <div
                        className={clsx(
                          "h-full rounded-full transition-all duration-1000",
                          opp.overall_score > 75 ? "bg-emerald-500" :
                          opp.overall_score > 65 ? "bg-amber-500" : "bg-slate-500"
                        )}
                        style={{ width: `${opp.overall_score}%` }}
                      />
                    </div>
                    <span className="text-sm font-mono font-bold text-white">
                      {opp.overall_score}
                    </span>
                  </div>
                </div>
              ))}
            </div>

            <Link
              to="/opportunities"
              className="mt-6 flex items-center justify-center gap-2 w-full py-4 rounded-lg bg-slate-900 border border-slate-800 text-sm font-semibold text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
            >
              Analyze All Opportunities <ArrowRight className="w-4 h-4" />
            </Link>
          </div>

          {/* RIGHT — Market Sentiment */}
          <div className="lg:col-span-3 bg-slate-900/50 border border-slate-800/50 rounded-xl p-6 flex flex-col justify-between">
            <div>
              <h3 className="text-xl font-bold text-white">Market Sentiment Trust Index</h3>
              <p className="text-xs text-slate-400 mt-1 uppercase tracking-wider mb-8">
                Average sentiment by leading brands
              </p>
            </div>
            
            <div className="flex-1 min-h-[300px]">
              {sentimentData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={sentimentData} margin={{ top: 10, right: 0, left: -20, bottom: 0 }}>
                    <defs>
                      <linearGradient id="sentimentGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#10b981" stopOpacity={0.2} />
                        <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <XAxis
                      dataKey="name"
                      tick={{ fontSize: 10, fill: "#64748b" }}
                      axisLine={false}
                      tickLine={false}
                      dy={10}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#0f172a",
                        border: "1px solid #1e293b",
                        borderRadius: "8px",
                        fontSize: "12px",
                        color: "#fff",
                      }}
                      itemStyle={{ color: "#10b981", fontWeight: "bold" }}
                      labelStyle={{ color: "#94a3b8", marginBottom: "4px" }}
                    />
                    <Area
                      type="monotone"
                      dataKey="avg_sentiment_score"
                      stroke="#10b981"
                      strokeWidth={3}
                      fill="url(#sentimentGrad)"
                      activeDot={{ r: 6, fill: "#10b981", stroke: "#0f172a", strokeWidth: 2 }}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-full flex items-center justify-center">
                  <div className="flex flex-col items-center gap-2">
                    <Activity className="w-8 h-8 text-slate-700 animate-pulse" />
                    <span className="text-slate-500 text-xs font-mono">Aggregating sentiment data...</span>
                  </div>
                </div>
              )}
            </div>

            <div className="mt-8 pt-6 border-t border-slate-800 flex items-center justify-between">
              <span className="text-xs font-mono text-slate-500">
                Dataset: {totalReviews.toLocaleString()} verified customer reviews
              </span>
              <Link
                to="/brands"
                className="text-xs font-bold uppercase tracking-wider text-emerald-500 hover:text-emerald-400 flex items-center gap-1 transition-colors"
              >
                Deep Dive <ArrowRight className="w-3 h-3" />
              </Link>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

/* ─── Sub-components ─── */

function KpiCardDark({ icon, value, label }: { icon: React.ReactNode; value: number; label: string }) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 relative overflow-hidden group">
      <div className="absolute top-0 right-0 p-6 opacity-10 transform translate-x-4 -translate-y-4 group-hover:scale-110 transition-transform duration-500">
        {icon}
      </div>
      <div className="w-10 h-10 rounded-lg bg-slate-950 border border-slate-800 flex items-center justify-center mb-6 shadow-inner">
        {icon}
      </div>
      <div className="text-3xl font-black text-white tracking-tight mb-2">
        {value > 0 ? value.toLocaleString() : "..."}
      </div>
      <div className="text-xs font-bold uppercase tracking-widest text-slate-500">
        {label}
      </div>
    </div>
  );
}
