import clsx from "clsx";

type Status = "success" | "failed" | "running" | "partial" | "warning" | "unknown" | string;

function normalise(s: string): Status {
  const v = s?.toLowerCase();
  if (v === "success") return "success";
  if (v === "failed") return "failed";
  if (v === "running") return "running";
  if (v === "partial") return "partial";
  if (v === "warning") return "warning";
  return "unknown";
}

interface Props {
  status: string;
  size?: "sm" | "md";
}

export default function StatusBadge({ status, size = "md" }: Props) {
  const norm = normalise(status);

  const classes = clsx("badge", {
    "badge-success": norm === "success",
    "badge-error": norm === "failed",
    "badge-running": norm === "running",
    "badge-warning": norm === "partial" || norm === "warning",
    "badge-neutral": norm === "unknown",
    "text-[10px] px-1.5 py-0.5": size === "sm",
  });

  const dotColor = clsx("h-1.5 w-1.5 rounded-full flex-shrink-0", {
    "bg-emerald-500": norm === "success",
    "bg-red-500": norm === "failed",
    "bg-indigo-500 animate-pulse": norm === "running",
    "bg-amber-500": norm === "partial" || norm === "warning",
    "bg-slate-400": norm === "unknown",
  });

  const label =
    norm === "success"
      ? "Success"
      : norm === "failed"
      ? "Failed"
      : norm === "running"
      ? "Running"
      : norm === "partial"
      ? "Partial"
      : norm === "warning"
      ? "Warning"
      : status || "Unknown";

  return (
    <span className={classes}>
      <span className={dotColor} />
      {label}
    </span>
  );
}
