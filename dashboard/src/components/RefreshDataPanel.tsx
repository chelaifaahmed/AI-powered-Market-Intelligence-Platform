import { useState, useEffect, useCallback, useRef } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, Check, X, Loader2, MessageSquare, MapPin, Newspaper } from "lucide-react";
import clsx from "clsx";
import { api } from "../api/client";
import type { ScraperType, PipelineRunStatus } from "../api/client";

interface ScraperButton {
  key: ScraperType;
  label: string;
  icon: typeof MessageSquare;
}

const SCRAPERS: ScraperButton[] = [
  { key: "reviews", label: "Reviews", icon: MessageSquare },
  { key: "listings", label: "Listings", icon: MapPin },
  { key: "articles", label: "News", icon: Newspaper },
];

type RunState = {
  runId: string;
  status: "running" | "success" | "failed" | "partial";
  scraper: ScraperType;
  duration: number | null;
  records: number;
  error: string | null;
};

function ScraperRefreshButton({
  scraper,
  label,
  Icon,
  runState,
  onTrigger,
  disabled,
}: {
  scraper: ScraperType;
  label: string;
  Icon: typeof MessageSquare;
  runState: RunState | null;
  onTrigger: (s: ScraperType) => void;
  disabled: boolean;
}) {
  const isRunning = runState?.status === "running";
  const isDone = runState?.status === "success" || runState?.status === "partial";
  const isFailed = runState?.status === "failed";

  return (
    <div className="flex flex-col items-center gap-2">
      <button
        onClick={() => onTrigger(scraper)}
        disabled={disabled || isRunning}
        className={clsx(
          "flex items-center gap-2 px-4 py-2.5 rounded-lg text-xs font-medium transition-all duration-200",
          isRunning
            ? "bg-brand-50 text-brand-600 border border-brand-200 cursor-wait"
            : isDone
              ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
              : isFailed
                ? "bg-red-50 text-red-600 border border-red-200"
                : "bg-white text-slate-700 border border-slate-200 hover:border-brand-300 hover:bg-brand-50 hover:text-brand-600"
        )}
      >
        {isRunning ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : isDone ? (
          <Check className="h-3.5 w-3.5" />
        ) : isFailed ? (
          <X className="h-3.5 w-3.5" />
        ) : (
          <Icon className="h-3.5 w-3.5" />
        )}
        <RefreshCw className={clsx("h-3 w-3", isRunning && "animate-spin")} />
        {label}
      </button>

      {/* Status text */}
      <div className="h-4 text-center">
        {isRunning && (
          <span className="text-[10px] text-brand-500 animate-pulse">
            Running… {runState.duration != null ? `${runState.duration}s` : ""}
          </span>
        )}
        {isDone && (
          <span className="text-[10px] text-emerald-600">
            Done {runState.records > 0 ? `— ${runState.records} records` : ""}
          </span>
        )}
        {isFailed && (
          <span className="text-[10px] text-red-500 max-w-[140px] truncate block" title={runState.error ?? ""}>
            Failed {runState.error ? `— ${runState.error.slice(0, 40)}` : ""}
          </span>
        )}
      </div>
    </div>
  );
}

interface RefreshDataPanelProps {
  variant?: "compact" | "full";
}

export default function RefreshDataPanel({ variant = "compact" }: RefreshDataPanelProps) {
  const queryClient = useQueryClient();
  const [runs, setRuns] = useState<Record<string, RunState>>({});
  const pollTimers = useRef<Record<string, ReturnType<typeof setInterval>>>({});

  const triggerMut = useMutation({
    mutationFn: (scraper: ScraperType) => api.triggerPipeline(scraper),
  });

  const stopPolling = useCallback((scraper: string) => {
    if (pollTimers.current[scraper]) {
      clearInterval(pollTimers.current[scraper]);
      delete pollTimers.current[scraper];
    }
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      Object.values(pollTimers.current).forEach(clearInterval);
    };
  }, []);

  const pollStatus = useCallback(
    (runId: string, scraper: ScraperType) => {
      const timer = setInterval(async () => {
        try {
          const st: PipelineRunStatus = await api.pipelineRunStatus(runId);
          const status = st.status as RunState["status"];

          setRuns((prev) => ({
            ...prev,
            [scraper]: {
              runId,
              status,
              scraper,
              duration: st.duration_seconds,
              records: st.records_scraped + st.records_stored,
              error: st.error_message,
            },
          }));

          if (status !== "running") {
            stopPolling(scraper);
            // Invalidate all queries to refresh page data
            queryClient.invalidateQueries();
          }
        } catch {
          // Ignore poll errors
        }
      }, 3000);

      pollTimers.current[scraper] = timer;
    },
    [queryClient, stopPolling]
  );

  const handleTrigger = useCallback(
    async (scraper: ScraperType) => {
      try {
        setRuns((prev) => ({
          ...prev,
          [scraper]: {
            runId: "",
            status: "running",
            scraper,
            duration: null,
            records: 0,
            error: null,
          },
        }));

        const res = await triggerMut.mutateAsync(scraper);

        setRuns((prev) => ({
          ...prev,
          [scraper]: { ...prev[scraper], runId: res.run_id },
        }));

        pollStatus(res.run_id, scraper);
      } catch (err) {
        setRuns((prev) => ({
          ...prev,
          [scraper]: {
            runId: "",
            status: "failed",
            scraper,
            duration: null,
            records: 0,
            error: err instanceof Error ? err.message : "Trigger failed",
          },
        }));
      }
    },
    [triggerMut, pollStatus]
  );

  const anyRunning = Object.values(runs).some((r) => r.status === "running");

  if (variant === "full") {
    return (
      <div className="card p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold text-slate-800">Run Pipeline</h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Trigger scraping pipelines to fetch fresh data
            </p>
          </div>
          <button
            onClick={() => handleTrigger("all")}
            disabled={anyRunning}
            className={clsx(
              "flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-colors",
              anyRunning
                ? "bg-slate-100 text-slate-400 cursor-not-allowed"
                : "bg-brand-500 text-white hover:bg-brand-600"
            )}
          >
            <RefreshCw className={clsx("h-3.5 w-3.5", runs["all"]?.status === "running" && "animate-spin")} />
            Run All Scrapers
          </button>
        </div>

        <div className="flex flex-wrap gap-4">
          {SCRAPERS.map(({ key, label, icon }) => (
            <ScraperRefreshButton
              key={key}
              scraper={key}
              label={label}
              Icon={icon}
              runState={runs[key] ?? null}
              onTrigger={handleTrigger}
              disabled={anyRunning}
            />
          ))}
        </div>

        {/* All status */}
        {runs["all"] && (
          <div className="mt-4 px-3 py-2 rounded-lg bg-slate-50 border border-slate-100">
            <div className="flex items-center gap-2 text-xs">
              {runs["all"].status === "running" ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 text-brand-500 animate-spin" />
                  <span className="text-brand-600">Running all scrapers sequentially…</span>
                  {runs["all"].duration != null && (
                    <span className="text-slate-400 ml-auto">{runs["all"].duration}s elapsed</span>
                  )}
                </>
              ) : runs["all"].status === "success" || runs["all"].status === "partial" ? (
                <>
                  <Check className="h-3.5 w-3.5 text-emerald-500" />
                  <span className="text-emerald-600">All scrapers complete</span>
                </>
              ) : runs["all"].status === "failed" ? (
                <>
                  <X className="h-3.5 w-3.5 text-red-500" />
                  <span className="text-red-600">Pipeline failed</span>
                </>
              ) : null}
            </div>
          </div>
        )}
      </div>
    );
  }

  // Compact variant (for Overview)
  return (
    <div className="card p-4">
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2 mr-2">
          <RefreshCw className="h-4 w-4 text-slate-400" />
          <span className="text-xs font-medium text-slate-600">Refresh data</span>
        </div>

        {SCRAPERS.map(({ key, label, icon }) => (
          <ScraperRefreshButton
            key={key}
            scraper={key}
            label={label}
            Icon={icon}
            runState={runs[key] ?? null}
            onTrigger={handleTrigger}
            disabled={anyRunning}
          />
        ))}

        <div className="ml-auto">
          <button
            onClick={() => handleTrigger("all")}
            disabled={anyRunning}
            className={clsx(
              "flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium transition-colors",
              anyRunning
                ? "bg-slate-100 text-slate-400"
                : "bg-slate-800 text-white hover:bg-slate-700"
            )}
          >
            <RefreshCw className={clsx("h-3 w-3", runs["all"]?.status === "running" && "animate-spin")} />
            Refresh All
          </button>
          {runs["all"]?.status === "running" && (
            <span className="block text-[10px] text-brand-500 text-center mt-1 animate-pulse">
              Running… {runs["all"].duration != null ? `${runs["all"].duration}s` : ""}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
