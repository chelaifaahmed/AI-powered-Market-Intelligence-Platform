import { type LucideIcon } from "lucide-react";
import clsx from "clsx";

interface KpiCardProps {
  label: string;
  value: string | number;
  sub?: string;
  icon?: LucideIcon;
  iconColor?: string;
  trend?: "up" | "down" | "neutral";
  trendLabel?: string;
  loading?: boolean;
}

export default function KpiCard({
  label,
  value,
  sub,
  icon: Icon,
  iconColor = "text-brand-500",
  trend,
  trendLabel,
  loading = false,
}: KpiCardProps) {
  if (loading) {
    return (
      <div className="card p-5 animate-pulse">
        <div className="h-3 w-20 bg-slate-100 rounded mb-4" />
        <div className="h-8 w-24 bg-slate-100 rounded mb-2" />
        <div className="h-3 w-16 bg-slate-100 rounded" />
      </div>
    );
  }

  return (
    <div className="card p-5 flex flex-col gap-3">
      <div className="flex items-start justify-between">
        <span className="kpi-label">{label}</span>
        {Icon && (
          <div
            className={clsx(
              "flex h-8 w-8 items-center justify-center rounded-lg",
              iconColor === "text-brand-500" && "bg-brand-50",
              iconColor === "text-emerald-500" && "bg-emerald-50",
              iconColor === "text-amber-500" && "bg-amber-50",
              iconColor === "text-red-500" && "bg-red-50",
              iconColor === "text-blue-500" && "bg-blue-50",
            )}
          >
            <Icon className={clsx("h-4 w-4", iconColor)} strokeWidth={2} />
          </div>
        )}
      </div>

      <div>
        <div className="kpi-value">{typeof value === "number" ? value.toLocaleString() : value}</div>
        {sub && <div className="text-xs text-slate-500 mt-0.5">{sub}</div>}
      </div>

      {trendLabel && trend && (
        <div
          className={clsx(
            "flex items-center gap-1 text-xs font-medium",
            trend === "up" && "text-emerald-600",
            trend === "down" && "text-red-500",
            trend === "neutral" && "text-slate-500",
          )}
        >
          {trend === "up" && "↑"}
          {trend === "down" && "↓"}
          {trend === "neutral" && "→"}
          <span>{trendLabel}</span>
        </div>
      )}
    </div>
  );
}
