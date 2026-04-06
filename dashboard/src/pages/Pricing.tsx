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
  Cell,
} from "recharts";
import { ShieldCheck, DollarSign, TrendingUp, Filter } from "lucide-react";
import { api, type CompetitorPricing } from "../api/client";
import KpiCard from "../components/KpiCard";
import EmptyState from "../components/EmptyState";
import ErrorState from "../components/ErrorState";
import Pagination from "../components/Pagination";
import { SkeletonTable } from "../components/Skeleton";
import { format, parseISO } from "date-fns";

const PAGE_SIZE = 20;

const PALETTE = [
  "#6366f1", "#3b82f6", "#10b981", "#f59e0b",
  "#ef4444", "#8b5cf6", "#06b6d4", "#84cc16",
];

function fmtDate(d: string | null) {
  if (!d) return "—";
  try { return format(parseISO(d), "MMM d, yyyy"); } catch { return d; }
}

export default function Pricing() {
  const [offset, setOffset] = useState(0);
  const [coverageFilter, setCoverageFilter] = useState("");
  const [regionFilter, setRegionFilter] = useState("");

  const { data, isLoading, isFetching, isError, error, refetch } = useQuery({
    queryKey: ["competitors", offset, coverageFilter, regionFilter],
    queryFn: () =>
      api.competitors({
        limit: PAGE_SIZE,
        offset,
        coverage_type: coverageFilter || undefined,
        region: regionFilter || undefined,
      }),
    placeholderData: (prev) => prev,
    staleTime: 30_000,
  });

  const { data: summary } = useQuery({
    queryKey: ["competitors-summary"],
    queryFn: () => api.competitorsSummary(),
    staleTime: 60_000,
  });

  if (isError) {
    return (
      <div className="card">
        <ErrorState error={error} onRetry={refetch} />
      </div>
    );
  }

  const allItems: CompetitorPricing[] = data?.items ?? [];
  const total = data?.total ?? 0;
  const page = allItems;

  // Derive filter options from summary breakdown
  const coverageTypes = (summary?.by_coverage ?? []).map((c) => c.source).sort();
  const regions = (summary?.by_region ?? []).map((r) => r.source).sort();

  // KPI stats from summary
  const avgPrice = summary?.avg_price ?? null;
  const prices = allItems.map((c) => c.price).filter((p) => p > 0);
  const minPrice = prices.length > 0 ? Math.min(...prices) : null;
  const maxPrice = prices.length > 0 ? Math.max(...prices) : null;

  // Chart: from summary by_coverage
  const chartData = (summary?.by_coverage ?? [])
    .map((item) => ({ type: item.source, count: item.count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 8);

  const currency = allItems[0]?.currency ?? "GBP";

  return (
    <div className="space-y-6">
      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard
          label="Total Quotes"
          value={total}
          icon={ShieldCheck}
          iconColor="text-brand-500"
          loading={isLoading}
        />
        <KpiCard
          label={`Avg Price (${currency})`}
          value={avgPrice != null ? avgPrice.toLocaleString("en-US", { maximumFractionDigits: 0 }) : "—"}
          icon={DollarSign}
          iconColor="text-emerald-500"
          loading={isLoading}
        />
        <KpiCard
          label="Min Price"
          value={minPrice != null ? minPrice.toLocaleString("en-US", { maximumFractionDigits: 0 }) : "—"}
          icon={TrendingUp}
          iconColor="text-blue-500"
          loading={isLoading}
        />
        <KpiCard
          label="Max Price"
          value={maxPrice != null ? maxPrice.toLocaleString("en-US", { maximumFractionDigits: 0 }) : "—"}
          icon={TrendingUp}
          iconColor="text-amber-500"
          loading={isLoading}
        />
      </div>

      {/* Chart */}
      {!isLoading && chartData.length > 0 && (
        <div className="card p-5">
          <div className="mb-5">
            <h3 className="text-sm font-semibold text-slate-800">Average Price by Coverage Type</h3>
            <p className="text-xs text-slate-500 mt-0.5">Comparing pricing across insurance product categories</p>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={chartData} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
              <XAxis
                dataKey="type"
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
                contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e2e8f0" }}
                formatter={(v: number) => [`${currency} ${v.toLocaleString()}`, "Avg Price"]}
              />
              <Bar dataKey="avg" radius={[4, 4, 0, 0]} name="Avg Price">
                {chartData.map((_, idx) => (
                  <Cell key={idx} fill={PALETTE[idx % PALETTE.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Filters */}
      <div className="card p-4 flex flex-wrap items-center gap-3">
        <Filter className="h-4 w-4 text-slate-400 flex-shrink-0" />
        <select
          value={coverageFilter}
          onChange={(e) => { setCoverageFilter(e.target.value); setOffset(0); }}
          className="select-input"
        >
          <option value="">All Coverage Types</option>
          {coverageTypes.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <select
          value={regionFilter}
          onChange={(e) => { setRegionFilter(e.target.value); setOffset(0); }}
          className="select-input"
        >
          <option value="">All Regions</option>
          {regions.map((r) => (
            <option key={r} value={r}>{r}</option>
          ))}
        </select>
        {(coverageFilter || regionFilter) && (
          <button
            onClick={() => { setCoverageFilter(""); setRegionFilter(""); setOffset(0); }}
            className="btn-ghost text-xs"
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Table */}
      <div className={`card overflow-hidden transition-opacity ${isFetching && !isLoading ? "opacity-60" : ""}`}>
        {isLoading ? (
          <SkeletonTable rows={PAGE_SIZE} cols={5} />
        ) : page.length === 0 ? (
          <EmptyState
            icon={ShieldCheck}
            title="No pricing data"
            message={
              coverageFilter || regionFilter
                ? "No pricing data for this filter combination."
                : "No competitor pricing snapshots have been collected yet."
            }
          />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr>
                    <th className="table-th">Coverage Type</th>
                    <th className="table-th">Region</th>
                    <th className="table-th text-right">Price</th>
                    <th className="table-th">Currency</th>
                    <th className="table-th">Snapshot Date</th>
                    <th className="table-th">Scraped</th>
                  </tr>
                </thead>
                <tbody>
                  {page.map((item) => (
                    <tr key={item.id} className="table-tr">
                      <td className="table-td font-medium text-slate-800">
                        {item.coverage_type ?? <span className="text-slate-400">—</span>}
                      </td>
                      <td className="table-td text-slate-600">
                        {item.region ?? <span className="text-slate-400">—</span>}
                      </td>
                      <td className="table-td text-right tabular-nums font-semibold text-slate-800">
                        {item.price.toLocaleString("en-US", { maximumFractionDigits: 2 })}
                      </td>
                      <td className="table-td">
                        <span className="badge badge-neutral">{item.currency}</span>
                      </td>
                      <td className="table-td text-slate-500 whitespace-nowrap">
                        {fmtDate(item.snapshot_date)}
                      </td>
                      <td className="table-td text-slate-400 whitespace-nowrap text-xs">
                        {fmtDate(item.scraped_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination
              total={total}
              limit={PAGE_SIZE}
              offset={offset}
              onOffsetChange={setOffset}
            />
          </>
        )}
      </div>
    </div>
  );
}
