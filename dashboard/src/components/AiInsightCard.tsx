import { useState, useEffect, useCallback } from "react";
import { Sparkles, RefreshCw, Loader2 } from "lucide-react";
import clsx from "clsx";
import { api } from "../api/client";

interface AiInsightCardProps {
  type: "overview" | "opportunity" | "brand" | "market_news" | "insurance";
  context?: string;
  variant?: "hero" | "inline";
  autoRefreshMs?: number;
}

export default function AiInsightCard({
  type,
  context = "",
  variant = "hero",
  autoRefreshMs,
}: AiInsightCardProps) {
  const [summary, setSummary] = useState("");
  const [generatedAt, setGeneratedAt] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  const fetchSummary = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const res = await api.analystSummarize(type, context);
      setSummary(res.summary);
      setGeneratedAt(res.generated_at);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [type, context]);

  useEffect(() => {
    fetchSummary();
  }, [fetchSummary]);

  useEffect(() => {
    if (!autoRefreshMs) return;
    const id = setInterval(fetchSummary, autoRefreshMs);
    return () => clearInterval(id);
  }, [autoRefreshMs, fetchSummary]);

  const timeLabel = generatedAt
    ? `Generated ${new Date(generatedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`
    : "";

  if (variant === "hero") {
    return (
      <div className="relative overflow-hidden rounded-xl bg-[#0f172a]">
        {/* Animated grid */}
        <div
          className="absolute inset-0"
          style={{
            backgroundImage:
              "linear-gradient(rgba(255,255,255,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.04) 1px, transparent 1px)",
            backgroundSize: "40px 40px",
          }}
        />
        <div className="relative z-10 px-6 py-5">
          {/* Header row */}
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2.5">
              <div className="flex h-6 w-6 items-center justify-center rounded-md bg-gradient-to-br from-violet-500 to-brand-500">
                <Sparkles className="h-3 w-3 text-white" strokeWidth={2.5} />
              </div>
              <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
                Market Pulse
              </span>
            </div>
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                <span className="text-[9px] font-semibold uppercase tracking-wider text-emerald-400/80">
                  AI
                </span>
              </div>
              <button
                onClick={fetchSummary}
                disabled={loading}
                className="p-1 rounded-md text-slate-500 hover:text-white hover:bg-white/10 transition-colors disabled:opacity-50"
              >
                <RefreshCw className={clsx("h-3 w-3", loading && "animate-spin")} />
              </button>
            </div>
          </div>

          {/* Body */}
          {loading && !summary ? (
            <div className="space-y-2">
              <div className="h-3 w-4/5 rounded bg-white/10 animate-pulse" />
              <div className="h-3 w-3/5 rounded bg-white/10 animate-pulse" />
            </div>
          ) : error ? (
            <p className="text-sm text-red-400">
              Could not generate summary. Check API key configuration.
            </p>
          ) : (
            <p className="text-[14px] font-light leading-relaxed text-slate-300">
              {summary}
            </p>
          )}

          {/* Timestamp */}
          {timeLabel && !loading && (
            <p className="text-[10px] text-slate-600 mt-3 text-right">{timeLabel}</p>
          )}
        </div>
      </div>
    );
  }

  // Inline variant
  return (
    <div className="rounded-xl border border-slate-200/80 bg-white p-4">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <div className="flex h-5 w-5 items-center justify-center rounded bg-gradient-to-br from-violet-500 to-brand-500">
            <Sparkles className="h-2.5 w-2.5 text-white" strokeWidth={2.5} />
          </div>
          <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
            AI Insight
          </span>
        </div>
        {loading ? (
          <Loader2 className="h-3 w-3 text-slate-400 animate-spin" />
        ) : (
          <button
            onClick={fetchSummary}
            className="p-0.5 rounded text-slate-400 hover:text-slate-600 transition-colors"
          >
            <RefreshCw className="h-3 w-3" />
          </button>
        )}
      </div>
      {loading && !summary ? (
        <div className="space-y-1.5">
          <div className="h-2.5 w-4/5 rounded bg-slate-100 animate-pulse" />
          <div className="h-2.5 w-3/5 rounded bg-slate-100 animate-pulse" />
        </div>
      ) : error ? (
        <p className="text-xs text-red-500">Summary unavailable</p>
      ) : (
        <p className="text-sm text-slate-600 leading-relaxed">{summary}</p>
      )}
    </div>
  );
}
