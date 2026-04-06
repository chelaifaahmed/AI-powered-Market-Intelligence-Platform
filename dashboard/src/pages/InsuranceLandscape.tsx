import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  PieChart,
  Pie,
  Cell,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
} from "recharts";
import {
  Shield,
  AlertTriangle,
  Star,
  MessageSquare,
  Building2,
  TrendingDown,
  Tag,
} from "lucide-react";
import clsx from "clsx";
import { api } from "../api/client";
import type { InsuranceCompanyOut, InsuranceSentimentOut } from "../api/client";
import KpiCard from "../components/KpiCard";
import EmptyState from "../components/EmptyState";
import ErrorState from "../components/ErrorState";
import { SkeletonChart } from "../components/Skeleton";
import AiInsightCard from "../components/AiInsightCard";

const COLORS = {
  positive: "#10b981",
  neutral: "#94a3b8",
  negative: "#f43f5e",
  critical: "#ef4444",
  warning: "#f97316",
  emerging: "#eab308",
  stable: "#22c55e",
};

const CLUSTER_COLORS: Record<string, string> = {
  "Critical Service Failures": COLORS.critical,
  "Multi-Domain Operational Gaps": COLORS.warning,
  "Emerging Market Entrants": COLORS.emerging,
  "Stable Market Leaders": COLORS.stable,
};

export default function InsuranceLandscape() {
  const [selectedCompanyId, setSelectedCompanyId] = useState<string>("");

  const {
    data: landscape,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["insurance-landscape"],
    queryFn: () => api.insuranceLandscape(),
    staleTime: 30000,
  });

  if (isError) {
    return (
      <div className="card">
        <ErrorState title="Failed to load insurance landscape" />
      </div>
    );
  }

  if (isLoading || !landscape) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <KpiCard key={i} label="" value="" loading />
          ))}
        </div>
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <div className="card p-5"><SkeletonChart height={280} /></div>
          <div className="card p-5"><SkeletonChart height={280} /></div>
        </div>
      </div>
    );
  }

  const { companies, sentiment_breakdown } = landscape;
  const companiesWithReviews = companies.filter((c) => c.review_count > 0);

  // Cluster distribution for pie chart
  const clusterCounts: Record<string, number> = {};
  for (const c of companiesWithReviews) {
    const label = c.cluster_label || "Unassigned";
    clusterCounts[label] = (clusterCounts[label] || 0) + 1;
  }
  const clusterPieData = Object.entries(clusterCounts).map(([name, value]) => ({
    name,
    value,
    color: CLUSTER_COLORS[name] || "#64748b",
  }));

  // Top 10 companies by review count for bar chart
  const top10 = sentiment_breakdown.slice(0, 10);
  const sentimentBarData = top10.map((s) => ({
    name: s.company_name.length > 14 ? s.company_name.slice(0, 12) + "..." : s.company_name,
    fullName: s.company_name,
    Positive: s.positive,
    Neutral: s.neutral,
    Negative: s.negative,
  }));

  // Rating comparison for radar
  const radarData = companiesWithReviews
    .filter((c) => c.avg_rating !== null)
    .slice(0, 8)
    .map((c) => ({
      company: c.name.length > 10 ? c.name.slice(0, 8) + ".." : c.name,
      rating: c.avg_rating ?? 0,
      negative: c.negative_pct ?? 0,
    }));

  // Selected company detail
  const selectedSentiment = sentiment_breakdown.find((s) => s.company_id === selectedCompanyId);
  const selectedCompany = companies.find((c) => c.id === selectedCompanyId);

  return (
    <div className="space-y-6">
      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard
          label="Insurance Companies"
          value={landscape.total_companies}
          sub={`${companiesWithReviews.length} with reviews`}
          icon={Building2}
          iconColor="text-brand-500"
        />
        <KpiCard
          label="Total Reviews"
          value={landscape.total_reviews}
          sub="All scraped from Trustpilot"
          icon={MessageSquare}
          iconColor="text-blue-500"
        />
        <KpiCard
          label="Avg Rating"
          value={landscape.avg_rating?.toFixed(2) ?? "---"}
          sub="Across all companies"
          icon={Star}
          iconColor="text-amber-500"
        />
        <KpiCard
          label="Negative Sentiment"
          value={`${landscape.overall_negative_pct}%`}
          sub="ERP opportunity signal"
          icon={TrendingDown}
          iconColor="text-red-500"
          trend={landscape.overall_negative_pct > 50 ? "down" : "up"}
          trendLabel={landscape.overall_negative_pct > 50 ? "High complaint rate" : "Moderate complaints"}
        />
      </div>

      {/* AI Insight */}
      <AiInsightCard
        type="insurance"
        context={`${landscape.total_companies} insurance companies, ${landscape.total_reviews} reviews, avg rating ${landscape.avg_rating}, ${landscape.overall_negative_pct}% negative sentiment`}
        variant="inline"
      />

      {/* Charts Row */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* Sentiment by Company */}
        <div className="card p-5">
          <div className="mb-5">
            <h3 className="text-sm font-semibold text-slate-800">Sentiment by Company</h3>
            <p className="text-xs text-slate-500 mt-0.5">Top 10 by review volume — stacked sentiment</p>
          </div>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={sentimentBarData} margin={{ top: 5, right: 10, left: -20, bottom: 40 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
              <XAxis
                dataKey="name"
                tick={{ fontSize: 10, fill: "#94a3b8" }}
                axisLine={false}
                tickLine={false}
                angle={-35}
                textAnchor="end"
                height={60}
              />
              <YAxis tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{
                  fontSize: 12,
                  borderRadius: 8,
                  border: "1px solid #e2e8f0",
                  boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.07)",
                }}
                labelFormatter={(_, payload) => {
                  const item = payload?.[0]?.payload as { fullName?: string } | undefined;
                  return item?.fullName ?? "";
                }}
              />
              <Legend wrapperStyle={{ fontSize: 11, paddingTop: 8 }} iconType="circle" iconSize={8} />
              <Bar dataKey="Positive" stackId="a" fill={COLORS.positive} />
              <Bar dataKey="Neutral" stackId="a" fill={COLORS.neutral} />
              <Bar dataKey="Negative" stackId="a" fill={COLORS.negative} radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Cluster Distribution */}
        <div className="card p-5">
          <div className="mb-5">
            <h3 className="text-sm font-semibold text-slate-800">ML Cluster Distribution</h3>
            <p className="text-xs text-slate-500 mt-0.5">KMeans grouping by complaint profile</p>
          </div>
          <div className="flex items-center gap-4">
            <ResponsiveContainer width="50%" height={260}>
              <PieChart>
                <Pie
                  data={clusterPieData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={100}
                  innerRadius={50}
                  paddingAngle={2}
                  strokeWidth={0}
                >
                  {clusterPieData.map((entry, i) => (
                    <Cell key={i} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e2e8f0" }}
                />
              </PieChart>
            </ResponsiveContainer>
            <div className="flex-1 space-y-2.5">
              {clusterPieData.map((entry) => (
                <div key={entry.name} className="flex items-center gap-2.5">
                  <span
                    className="h-3 w-3 rounded-full flex-shrink-0"
                    style={{ backgroundColor: entry.color }}
                  />
                  <span className="text-xs text-slate-700 leading-tight">
                    {entry.name}
                    <span className="text-slate-400 ml-1">({entry.value})</span>
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Rating Radar */}
      {radarData.length > 3 && (
        <div className="card p-5">
          <div className="mb-5">
            <h3 className="text-sm font-semibold text-slate-800">Rating vs Negative Sentiment</h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Higher rating is better. Higher negative % indicates ERP opportunity.
            </p>
          </div>
          <ResponsiveContainer width="100%" height={300}>
            <RadarChart data={radarData}>
              <PolarGrid stroke="#e2e8f0" />
              <PolarAngleAxis
                dataKey="company"
                tick={{ fontSize: 10, fill: "#64748b" }}
              />
              <PolarRadiusAxis angle={30} domain={[0, 5]} tick={{ fontSize: 9 }} />
              <Radar
                name="Rating"
                dataKey="rating"
                stroke="#6366f1"
                fill="#6366f1"
                fillOpacity={0.15}
                strokeWidth={2}
              />
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e2e8f0" }} />
              <Legend wrapperStyle={{ fontSize: 11 }} iconType="circle" iconSize={8} />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Company Selector + Detail */}
      <div className="card p-5">
        <div className="flex flex-wrap items-center gap-4 mb-5">
          <h3 className="text-sm font-semibold text-slate-800">Company Detail</h3>
          <select
            value={selectedCompanyId}
            onChange={(e) => setSelectedCompanyId(e.target.value)}
            className="select-input max-w-xs appearance-none"
          >
            <option value="">Select a company...</option>
            {companiesWithReviews.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.review_count} reviews)
              </option>
            ))}
          </select>
        </div>

        {!selectedCompanyId ? (
          <EmptyState
            icon={Shield}
            title="Select a company"
            message="Choose an insurance company above to see detailed sentiment breakdown and ERP recommendations."
          />
        ) : selectedCompany && selectedSentiment ? (
          <CompanyDetail company={selectedCompany} sentiment={selectedSentiment} />
        ) : (
          <EmptyState icon={Shield} title="No data" message="No review data for this company." />
        )}
      </div>

      {/* Company Table */}
      <div className="card overflow-hidden">
        <div className="p-5 border-b border-slate-100">
          <h3 className="text-sm font-semibold text-slate-800">All Insurance Companies</h3>
          <p className="text-xs text-slate-500 mt-0.5">Sorted by review count. Click a row for details.</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50/50">
                <th className="text-left px-4 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">Company</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">Reviews</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">Rating</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">Neg %</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">Cluster</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-slate-500 uppercase tracking-wider">ERP Module</th>
              </tr>
            </thead>
            <tbody>
              {companies.map((c) => (
                <tr
                  key={c.id}
                  onClick={() => {
                    if (c.review_count > 0) setSelectedCompanyId(c.id);
                  }}
                  className={clsx(
                    "border-b border-slate-50 transition-colors",
                    c.review_count > 0 ? "cursor-pointer hover:bg-slate-50" : "opacity-50",
                    selectedCompanyId === c.id && "bg-brand-50/50",
                  )}
                >
                  <td className="px-4 py-3 font-medium text-slate-800">{c.name}</td>
                  <td className="px-4 py-3 text-right tabular-nums text-slate-600">{c.review_count}</td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {c.avg_rating !== null ? (
                      <span className={clsx(
                        "font-medium",
                        c.avg_rating >= 4 ? "text-emerald-600" :
                        c.avg_rating >= 3 ? "text-amber-600" : "text-red-600"
                      )}>
                        {c.avg_rating.toFixed(1)}
                      </span>
                    ) : (
                      <span className="text-slate-300">---</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {c.negative_pct !== null ? (
                      <span className={clsx(
                        "font-medium",
                        c.negative_pct > 70 ? "text-red-600" :
                        c.negative_pct > 50 ? "text-orange-500" : "text-slate-600"
                      )}>
                        {c.negative_pct}%
                      </span>
                    ) : (
                      <span className="text-slate-300">---</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {c.cluster_label ? (
                      <span
                        className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium text-white"
                        style={{ backgroundColor: CLUSTER_COLORS[c.cluster_label] || "#64748b" }}
                      >
                        {c.cluster_label}
                      </span>
                    ) : (
                      <span className="text-slate-300 text-xs">---</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-500">{c.erp_module || "---"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function CompanyDetail({
  company,
  sentiment,
}: {
  company: InsuranceCompanyOut;
  sentiment: InsuranceSentimentOut;
}) {
  const total = sentiment.positive + sentiment.neutral + sentiment.negative;
  const posPct = total > 0 ? ((sentiment.positive / total) * 100).toFixed(1) : "0";
  const neuPct = total > 0 ? ((sentiment.neutral / total) * 100).toFixed(1) : "0";
  const negPct = total > 0 ? ((sentiment.negative / total) * 100).toFixed(1) : "0";

  const sentPieData = [
    { name: "Positive", value: sentiment.positive, color: COLORS.positive },
    { name: "Neutral", value: sentiment.neutral, color: COLORS.neutral },
    { name: "Negative", value: sentiment.negative, color: COLORS.negative },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      {/* Company Info */}
      <div className="space-y-3">
        <h4 className="text-base font-semibold text-slate-800">{company.name}</h4>
        <div className="space-y-1.5 text-xs text-slate-600">
          {company.country && (
            <p><span className="text-slate-400">Country:</span> {company.country}</p>
          )}
          {company.founded_year && (
            <p><span className="text-slate-400">Founded:</span> {company.founded_year}</p>
          )}
          {company.region && (
            <p><span className="text-slate-400">Region:</span> {company.region}</p>
          )}
        </div>

        <div className="pt-2 space-y-2">
          <div className="flex items-center gap-2">
            <MessageSquare className="h-4 w-4 text-blue-500" />
            <span className="text-sm font-medium">{company.review_count} reviews</span>
          </div>
          <div className="flex items-center gap-2">
            <Star className="h-4 w-4 text-amber-500" />
            <span className="text-sm font-medium">{company.avg_rating?.toFixed(2) ?? "---"} avg</span>
          </div>
          {company.cluster_label && (
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-orange-500" />
              <span
                className="text-xs px-2 py-0.5 rounded-full text-white font-medium"
                style={{ backgroundColor: CLUSTER_COLORS[company.cluster_label] || "#64748b" }}
              >
                {company.cluster_label}
              </span>
            </div>
          )}
          {company.erp_module && (
            <div className="flex items-center gap-2">
              <Tag className="h-4 w-4 text-brand-500" />
              <span className="text-xs text-slate-700">{company.erp_module}</span>
            </div>
          )}
        </div>
      </div>

      {/* Sentiment Pie */}
      <div className="flex flex-col items-center">
        <h4 className="text-xs font-medium text-slate-500 mb-2">Sentiment Split</h4>
        <ResponsiveContainer width="100%" height={180}>
          <PieChart>
            <Pie
              data={sentPieData}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="50%"
              outerRadius={70}
              innerRadius={40}
              strokeWidth={0}
            >
              {sentPieData.map((entry, i) => (
                <Cell key={i} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e2e8f0" }} />
          </PieChart>
        </ResponsiveContainer>
        <div className="flex gap-4 text-xs">
          <span className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-emerald-500" /> {posPct}%
          </span>
          <span className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-slate-400" /> {neuPct}%
          </span>
          <span className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-red-400" /> {negPct}%
          </span>
        </div>
      </div>

      {/* Topics */}
      <div>
        <h4 className="text-xs font-medium text-slate-500 mb-3">Top Complaint Topics</h4>
        {sentiment.top_topics.length > 0 ? (
          <div className="space-y-2">
            {sentiment.top_topics.map((topic) => (
              <div
                key={topic}
                className="flex items-center gap-2 px-3 py-2 bg-slate-50 rounded-lg"
              >
                <AlertTriangle className="h-3.5 w-3.5 text-orange-400 flex-shrink-0" />
                <span className="text-sm text-slate-700 capitalize">{topic}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-slate-400">No topic data available</p>
        )}

        {company.negative_pct !== null && company.negative_pct > 60 && (
          <div className="mt-4 p-3 bg-red-50 border border-red-100 rounded-lg">
            <p className="text-xs text-red-700 font-medium">
              High complaint rate ({company.negative_pct}%)
            </p>
            <p className="text-[11px] text-red-600 mt-1">
              Strong ERP opportunity signal. Recommended module: {company.erp_module || "Integrated ERP Suite"}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
