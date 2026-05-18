import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { ChevronDown, Star, TrendingUp, MessageSquare, Globe } from "lucide-react";
import clsx from "clsx";
import { api } from "../api/client";
import KpiCard from "../components/KpiCard";
import EmptyState from "../components/EmptyState";
import ErrorState from "../components/ErrorState";
import { SkeletonChart } from "../components/Skeleton";
import { format, parseISO } from "date-fns";
import AiInsightCard from "../components/AiInsightCard";

const CHART_COLORS = {
  positive: "#10b981",
  neutral: "#94a3b8",
  negative: "#f43f5e",
  rating: "#6366f1",
  sentiment: "#3b82f6",
};

function formatPeriod(d: string) {
  try {
    return format(parseISO(d), "MMM yy");
  } catch {
    return d;
  }
}

type OriginFilter = "scraped" | "all" | "reference";

export default function Brands() {
  const [selectedBrandId, setSelectedBrandId] = useState<string>("");
  const [originFilter, setOriginFilter] = useState<OriginFilter>("scraped");

  const {
    data: brands,
    isLoading: brandsLoading,
    isError: brandsError,
  } = useQuery({
    queryKey: ["brands"],
    queryFn: () => api.brands(),
  });

  const selectedBrand = brands?.find((b) => b.id === selectedBrandId);

  const {
    data: reputation,
    isLoading: repLoading,
  } = useQuery({
    queryKey: ["brand-reputation", selectedBrandId, originFilter],
    queryFn: () => api.brandReputation(selectedBrandId, originFilter),
    enabled: !!selectedBrandId,
  });

  const {
    data: sentiment,
    isLoading: sentLoading,
  } = useQuery({
    queryKey: ["brand-sentiment", selectedBrandId, originFilter],
    queryFn: () => api.brandSentiment(selectedBrandId, originFilter),
    enabled: !!selectedBrandId,
  });

  if (brandsError) {
    return (
      <div className="card">
        <ErrorState title="Failed to load brands" />
      </div>
    );
  }

  const repChartData = (reputation ?? [])
    .slice()
    .reverse()
    .map((r) => ({
      period: formatPeriod(r.period_date),
      rating: r.avg_rating != null ? +r.avg_rating.toFixed(2) : null,
      sentiment: r.avg_sentiment_score != null ? +r.avg_sentiment_score.toFixed(3) : null,
      reviews: r.review_count,
    }));

  const sentChartData = (sentiment ?? [])
    .slice()
    .reverse()
    .map((s) => ({
      period: formatPeriod(s.period_date),
      Positive: s.positive_count,
      Neutral: s.neutral_count,
      Negative: s.negative_count,
    }));

  const totalReviews = (reputation ?? []).reduce((acc, r) => acc + r.review_count, 0);
  const latestRep = reputation?.[0];
  const latestSent = sentiment?.[0];
  const totalPositive = (sentiment ?? []).reduce((a, s) => a + s.positive_count, 0);
  const totalNegative = (sentiment ?? []).reduce((a, s) => a + s.negative_count, 0);
  const totalNeutral = (sentiment ?? []).reduce((a, s) => a + s.neutral_count, 0);
  const totalSentiment = totalPositive + totalNegative + totalNeutral;

  return (
    <div className="space-y-6">
      {/* Brand Selector + Origin Toggle */}
      <div className="card p-4 flex flex-wrap items-center gap-4">
        {/* Origin filter */}
        <div className="flex items-center gap-1.5 bg-slate-50 border border-slate-200 rounded-lg p-1">
          {(["scraped", "all", "reference"] as OriginFilter[]).map((o) => (
            <button
              key={o}
              onClick={() => setOriginFilter(o)}
              className={clsx(
                "px-3 py-1.5 text-xs font-medium rounded-md transition-colors",
                originFilter === o
                  ? o === "scraped" ? "bg-emerald-500 text-white shadow-sm"
                    : o === "reference" ? "bg-slate-400 text-white shadow-sm"
                    : "bg-brand-500 text-white shadow-sm"
                  : "text-slate-500 hover:text-slate-700"
              )}
            >
              {o === "scraped" ? "Live" : o === "reference" ? "Reference" : "All"}
            </button>
          ))}
        </div>
        <label className="text-sm font-medium text-slate-700 flex-shrink-0">
          Select Brand
        </label>
        <div className="relative flex-1 max-w-xs">
          {brandsLoading ? (
            <div className="select-input animate-pulse bg-slate-50 text-slate-300">
              Loading brands…
            </div>
          ) : (
            <select
              value={selectedBrandId}
              onChange={(e) => setSelectedBrandId(e.target.value)}
              className="select-input w-full appearance-none pr-8"
            >
              <option value="">Choose a brand to analyse…</option>
              {(brands ?? []).map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name} {b.country_of_origin ? `(${b.country_of_origin})` : ""}
                </option>
              ))}
            </select>
          )}
          <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 pointer-events-none" />
        </div>

        {selectedBrand && (
          <div className="flex items-center gap-3 ml-2">
            {selectedBrand.country_of_origin && (
              <span className="flex items-center gap-1 text-xs text-slate-500">
                <Globe className="h-3.5 w-3.5" />
                {selectedBrand.country_of_origin}
              </span>
            )}
            {selectedBrand.founded_year && (
              <span className="text-xs text-slate-500">
                Est. {selectedBrand.founded_year}
              </span>
            )}
            <span
              className={`badge text-[10px] ${
                selectedBrand.is_active ? "badge-success" : "badge-neutral"
              }`}
            >
              {selectedBrand.is_active ? "Active" : "Inactive"}
            </span>
          </div>
        )}
      </div>

      {/* AI Brand Insight — shown only when a brand is selected */}
      {selectedBrand && (
        <AiInsightCard
          type="brand"
          context={`Brand: ${selectedBrand.name}, Country: ${selectedBrand.country_of_origin ?? "unknown"}`}
          variant="inline"
        />
      )}

      {!selectedBrandId ? (
        <div className="card">
          <EmptyState
            icon={TrendingUp}
            title="Select a brand to begin"
            message="Choose a brand from the dropdown above to view its reputation trend, sentiment distribution, and review analytics."
          />
        </div>
      ) : (
        <>
          {/* KPIs */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <KpiCard
              label="Total Reviews"
              value={totalReviews}
              icon={MessageSquare}
              iconColor="text-brand-500"
              loading={repLoading}
            />
            <KpiCard
              label="Avg Rating"
              value={
                latestRep?.avg_rating != null
                  ? latestRep.avg_rating.toFixed(1)
                  : "—"
              }
              sub="Latest period"
              icon={Star}
              iconColor="text-amber-500"
              loading={repLoading}
            />
            <KpiCard
              label="Sentiment Score"
              value={
                latestSent?.avg_sentiment_score != null
                  ? latestSent.avg_sentiment_score.toFixed(3)
                  : "—"
              }
              sub="Latest period"
              icon={TrendingUp}
              iconColor="text-emerald-500"
              loading={sentLoading}
            />
            <KpiCard
              label="Positive Rate"
              value={
                totalSentiment > 0
                  ? `${((totalPositive / totalSentiment) * 100).toFixed(1)}%`
                  : "—"
              }
              sub={`${totalPositive.toLocaleString()} of ${totalSentiment.toLocaleString()} reviews`}
              icon={TrendingUp}
              iconColor="text-emerald-500"
              loading={sentLoading}
            />
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            {/* Reputation Trend */}
            <div className="card p-5">
              <div className="flex items-center justify-between mb-5">
                <div>
                  <h3 className="text-sm font-semibold text-slate-800">Reputation Trend</h3>
                  <p className="text-xs text-slate-500 mt-0.5">Average rating over time</p>
                </div>
              </div>
              {repLoading ? (
                <SkeletonChart height={200} />
              ) : repChartData.length === 0 ? (
                <EmptyState title="No reputation data" message="Run the analytics pipeline to compute brand scores." />
              ) : (
                <ResponsiveContainer width="100%" height={220}>
                  <AreaChart data={repChartData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                    <defs>
                      <linearGradient id="ratingGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={CHART_COLORS.rating} stopOpacity={0.15} />
                        <stop offset="95%" stopColor={CHART_COLORS.rating} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                    <XAxis
                      dataKey="period"
                      tick={{ fontSize: 11, fill: "#94a3b8" }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      tick={{ fontSize: 11, fill: "#94a3b8" }}
                      axisLine={false}
                      tickLine={false}
                      domain={[0, 5]}
                    />
                    <Tooltip
                      contentStyle={{
                        fontSize: 12,
                        borderRadius: 8,
                        border: "1px solid #e2e8f0",
                        boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.07)",
                      }}
                    />
                    <Area
                      type="monotone"
                      dataKey="rating"
                      stroke={CHART_COLORS.rating}
                      strokeWidth={2}
                      fill="url(#ratingGrad)"
                      dot={false}
                      activeDot={{ r: 4, strokeWidth: 0 }}
                      name="Avg Rating"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </div>

            {/* Sentiment Distribution */}
            <div className="card p-5">
              <div className="flex items-center justify-between mb-5">
                <div>
                  <h3 className="text-sm font-semibold text-slate-800">Sentiment Distribution</h3>
                  <p className="text-xs text-slate-500 mt-0.5">Positive / Neutral / Negative per period</p>
                </div>
                {totalSentiment > 0 && (
                  <div className="flex items-center gap-3 text-xs">
                    <span className="flex items-center gap-1">
                      <span className="h-2 w-2 rounded-full bg-emerald-500" />
                      <span className="text-slate-500">{((totalPositive / totalSentiment) * 100).toFixed(0)}%</span>
                    </span>
                    <span className="flex items-center gap-1">
                      <span className="h-2 w-2 rounded-full bg-slate-400" />
                      <span className="text-slate-500">{((totalNeutral / totalSentiment) * 100).toFixed(0)}%</span>
                    </span>
                    <span className="flex items-center gap-1">
                      <span className="h-2 w-2 rounded-full bg-red-400" />
                      <span className="text-slate-500">{((totalNegative / totalSentiment) * 100).toFixed(0)}%</span>
                    </span>
                  </div>
                )}
              </div>
              {sentLoading ? (
                <SkeletonChart height={200} />
              ) : sentChartData.length === 0 ? (
                <EmptyState title="No sentiment data" message="Run the NLP pipeline to compute sentiment trends." />
              ) : (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={sentChartData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                    <XAxis
                      dataKey="period"
                      tick={{ fontSize: 11, fill: "#94a3b8" }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      tick={{ fontSize: 11, fill: "#94a3b8" }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip
                      contentStyle={{
                        fontSize: 12,
                        borderRadius: 8,
                        border: "1px solid #e2e8f0",
                        boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.07)",
                      }}
                    />
                    <Legend
                      wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
                      iconType="circle"
                      iconSize={8}
                    />
                    <Bar
                      dataKey="Positive"
                      stackId="a"
                      fill={CHART_COLORS.positive}
                      radius={[0, 0, 0, 0]}
                    />
                    <Bar
                      dataKey="Neutral"
                      stackId="a"
                      fill={CHART_COLORS.neutral}
                    />
                    <Bar
                      dataKey="Negative"
                      stackId="a"
                      fill={CHART_COLORS.negative}
                      radius={[2, 2, 0, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          {/* Sentiment Score Trend */}
          {(sentLoading || sentChartData.length > 0) && (
            <div className="card p-5">
              <div className="mb-5">
                <h3 className="text-sm font-semibold text-slate-800">Sentiment Score Trend</h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Average NLP sentiment score over time (−1 negative → +1 positive)
                </p>
              </div>
              {sentLoading ? (
                <SkeletonChart height={160} />
              ) : (
                <ResponsiveContainer width="100%" height={180}>
                  <AreaChart
                    data={(sentiment ?? [])
                      .slice()
                      .reverse()
                      .map((s) => ({
                        period: formatPeriod(s.period_date),
                        score: s.avg_sentiment_score != null ? +s.avg_sentiment_score.toFixed(3) : null,
                      }))}
                    margin={{ top: 5, right: 10, left: -20, bottom: 0 }}
                  >
                    <defs>
                      <linearGradient id="sentGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={CHART_COLORS.sentiment} stopOpacity={0.15} />
                        <stop offset="95%" stopColor={CHART_COLORS.sentiment} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                    <XAxis
                      dataKey="period"
                      tick={{ fontSize: 11, fill: "#94a3b8" }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      tick={{ fontSize: 11, fill: "#94a3b8" }}
                      axisLine={false}
                      tickLine={false}
                      domain={[-1, 1]}
                    />
                    <Tooltip
                      contentStyle={{
                        fontSize: 12,
                        borderRadius: 8,
                        border: "1px solid #e2e8f0",
                      }}
                    />
                    <Area
                      type="monotone"
                      dataKey="score"
                      stroke={CHART_COLORS.sentiment}
                      strokeWidth={2}
                      fill="url(#sentGrad)"
                      dot={false}
                      activeDot={{ r: 4, strokeWidth: 0 }}
                      name="Sentiment Score"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
