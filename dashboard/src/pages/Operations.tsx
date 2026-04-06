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
import {
  Activity,
  AlertTriangle,
  CheckCircle,
  ChevronDown,
  ChevronRight,
  Database,
  RefreshCw,
  XCircle,
} from "lucide-react";
import { api, type PipelineRun, type PipelineRunDetail } from "../api/client";
import ErrorState from "../components/ErrorState";
import Pagination from "../components/Pagination";
import { SkeletonTable } from "../components/Skeleton";
import RefreshDataPanel from "../components/RefreshDataPanel";
import { format, parseISO, formatDistanceToNow } from "date-fns";
import clsx from "clsx";

const PAGE_SIZE = 10;

function durationLabel(ms: number | null | undefined) {
  if (ms == null) return "—";
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}m`;
}

// Expandable pipeline run row
function RunRow({ run }: { run: PipelineRun }) {
  const [expanded, setExpanded] = useState(false);

  const { data: detail, isLoading: detailLoading } = useQuery({
    queryKey: ["pipeline-run-detail", run.id],
    queryFn: () => api.pipelineRunDetail(run.id),
    enabled: expanded,
  });

  const dur =
    run.started_at && run.finished_at
      ? new Date(run.finished_at).getTime() - new Date(run.started_at).getTime()
      : null;

  return (
    <>
      <tr
        className={clsx("hover:bg-slate-800/30 cursor-pointer select-none transition-colors border-b border-slate-800/50", expanded && "bg-slate-800/40 relative z-10 box-shadow-[0_0_20px_rgba(0,0,0,0.5)]")}
        onClick={() => setExpanded((v) => !v)}
      >
        <td className="px-4 py-4 w-10">
          {expanded ? (
            <ChevronDown className="h-4 w-4 text-brand-400" />
          ) : (
            <ChevronRight className="h-4 w-4 text-slate-600 group-hover:text-brand-400 transition-colors" />
          )}
        </td>
        <td className="px-4 py-4 font-bold text-slate-200 tracking-wide text-sm uppercase">
          {run.task_name.replace(/_/g, " ")}
        </td>
        <td className="px-4 py-4">
          <span className={clsx(
            "inline-flex items-center px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-widest border",
            run.status === "running" ? "bg-blue-500/10 text-blue-400 border-blue-500/30 shadow-[0_0_10px_rgba(59,130,246,0.3)] animate-pulse" :
            run.status === "completed" ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30" :
            run.status === "failed" ? "bg-red-500/10 text-red-400 border-red-500/30 shadow-[0_0_10px_rgba(239,68,68,0.3)]" :
            run.status === "pending" ? "bg-amber-500/10 text-amber-500 border-amber-500/30" :
            "bg-slate-800 text-slate-500 border-slate-700"
          )}>
            {run.status}
          </span>
        </td>
        <td className="px-4 py-4 text-right tabular-nums text-slate-400 font-mono">
          {run.records_scraped.toLocaleString()}
        </td>
        <td className="px-4 py-4 text-right tabular-nums text-emerald-400/80 font-mono">
          {run.records_stored.toLocaleString()}
        </td>
        <td className="px-4 py-4 text-right tabular-nums text-slate-500 font-mono">
          {durationLabel(dur)}
        </td>
        <td className="px-4 py-4 text-slate-500 font-mono text-xs whitespace-nowrap">
          {run.started_at
            ? formatDistanceToNow(new Date(run.started_at), { addSuffix: true })
            : "—"}
        </td>
      </tr>

      {expanded && (
        <tr className="bg-slate-900 border-b border-slate-800 shadow-inner">
          <td colSpan={7} className="p-0">
            <div className="overflow-hidden bg-slate-950/50 backdrop-blur-sm p-4 border-l-2 border-brand-500">
              {detailLoading ? (
                <div className="py-8 text-center text-xs font-black tracking-widest uppercase text-brand-500/70 animate-pulse">
                  Decrypting Execution Trace...
                </div>
              ) : !detail || (detail as PipelineRunDetail).steps.length === 0 ? (
                <div className="py-6 text-center text-xs font-black tracking-widest uppercase text-slate-600">No telemetry nodes found</div>
              ) : (
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-slate-800">
                      <th className="px-4 py-3 text-left font-black tracking-widest text-slate-500 uppercase">Operation Phase</th>
                      <th className="px-4 py-3 text-left font-black tracking-widest text-slate-500 uppercase">Status</th>
                      <th className="px-4 py-3 text-right font-black tracking-widest text-slate-500 uppercase">Input</th>
                      <th className="px-4 py-3 text-right font-black tracking-widest text-slate-500 uppercase">Output</th>
                      <th className="px-4 py-3 text-right font-black tracking-widest text-slate-500 uppercase">Dropped</th>
                      <th className="px-4 py-3 text-right font-black tracking-widest text-slate-500 uppercase">Lat</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(detail as PipelineRunDetail).steps.map((step) => (
                      <tr key={step.id} className="border-b border-slate-800/50 hover:bg-slate-900/50 transition-colors">
                        <td className="px-4 py-3 font-bold text-slate-300 uppercase text-[10px] tracking-wider">
                          {step.step_name.replace(/_/g, " ")}
                        </td>
                        <td className="px-4 py-3">
                          <span className={clsx(
                            "inline-flex items-center px-1.5 py-0.5 rounded text-[8px] font-black uppercase tracking-widest border",
                            step.status === "completed" ? "text-emerald-500 border-emerald-500/20 bg-emerald-500/5" :
                            step.status === "failed" ? "text-red-500 border-red-500/20 bg-red-500/5" :
                            "text-slate-500 border-slate-700 bg-slate-800"
                          )}>
                            {step.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right tabular-nums text-slate-400 font-mono">
                          {step.records_seen.toLocaleString()}
                        </td>
                        <td className="px-4 py-3 text-right tabular-nums text-emerald-400/80 font-mono">
                          {step.records_processed.toLocaleString()}
                        </td>
                        <td className={clsx("px-4 py-3 text-right tabular-nums font-mono font-bold", step.records_failed > 0 ? "text-red-500" : "text-slate-600")}>
                          {step.records_failed > 0 ? step.records_failed.toLocaleString() : "—"}
                        </td>
                        <td className="px-4 py-3 text-right tabular-nums text-slate-500 font-mono">
                          {durationLabel(step.duration_ms)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              {run.error_message && (
                <div className="mt-3 rounded border border-red-500/20 bg-red-500/10 px-4 py-3 text-xs text-red-400 font-mono flex items-start gap-3">
                  <AlertTriangle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
                  <div className="overflow-x-auto">{run.error_message}</div>
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

export default function Operations() {
  const [failureSource, setFailureSource] = useState("");
  const [failureOffset, setFailureOffset] = useState(0);

  const {
    data: quality,
    isLoading: qualLoading,
    refetch: refetchQuality,
  } = useQuery({
    queryKey: ["pipeline-quality"],
    queryFn: api.pipelineQuality,
  });

  const {
    data: runs,
    isLoading: runsLoading,
    isError: runsError,
    refetch: refetchRuns,
  } = useQuery({
    queryKey: ["pipeline-runs"],
    queryFn: () => api.pipelineRuns(50),
  });

  const {
    data: failures,
    isLoading: failLoading,
    refetch: refetchFail,
  } = useQuery({
    queryKey: ["pipeline-failures", failureSource, failureOffset],
    queryFn: () =>
      api.pipelineFailures({
        limit: 20,
        offset: failureOffset,
        source: failureSource || undefined,
      }),
    placeholderData: (prev) => prev,
  });

  const allRefetch = () => {
    refetchQuality();
    refetchRuns();
    refetchFail();
  };

  // Chart data for rejections by entity type
  const rejectionChart = (quality?.by_entity_type ?? []).slice(0, 6).map((e) => ({
    name: e.entity_type.replace(/_/g, " "),
    count: e.rejection_count,
  }));

  return (
    <div className="space-y-10 relative z-10 text-slate-200">
      
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-end gap-6 border-b border-slate-800/60 pb-6">
        <div>
          <h1 className="text-3xl lg:text-5xl font-black text-white tracking-tighter mb-2">
            Operations Center
          </h1>
          <p className="text-sm font-semibold tracking-wide text-slate-500 uppercase">
            System Reliability & Data Integrity Pipeline
          </p>
        </div>
        <div className="flex items-center gap-4">
          <button onClick={allRefetch} className="flex items-center gap-2 text-[10px] font-black tracking-widest uppercase text-brand-400 hover:text-brand-300 transition-colors px-4 py-2 border border-brand-500/30 bg-brand-500/10 rounded-lg hover:shadow-[0_0_15px_rgba(99,102,241,0.2)]">
            <RefreshCw className="h-3 w-3" /> Execute System sync
          </button>
        </div>
      </div>

      <RefreshDataPanel variant="compact" />

      {/* Quality KPIs */}
      <div>
        <h2 className="text-base font-bold uppercase tracking-widest text-slate-500 mb-6">Integrity Telemetry</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          <OpKpi
            label="Total Corruptions"
            value={quality?.total_rejections ?? 0}
            icon={<XCircle className="w-5 h-5 text-red-500" />}
            color="red"
            loading={qualLoading}
          />
          <OpKpi
            label="Stranded Pages"
            value={quality?.raw_pages_unparsed ?? 0}
            icon={<Database className="w-5 h-5 text-amber-500" />}
            color="amber"
            loading={qualLoading}
          />
          <OpKpi
            label="Auto NLP Scan"
            value={quality ? `${quality.car_review_nlp_coverage_pct.toFixed(1)}%` : "—"}
            icon={<CheckCircle className="w-5 h-5 text-brand-500" />}
            color="brand"
            loading={qualLoading}
          />
          <OpKpi
            label="Insure NLP Scan"
            value={quality ? `${quality.insurance_review_nlp_coverage_pct.toFixed(1)}%` : "—"}
            icon={<CheckCircle className="w-5 h-5 text-blue-500" />}
            color="blue"
            loading={qualLoading}
          />
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">
        {/* Rejections chart */}
        <div>
          <h2 className="text-base font-bold uppercase tracking-widest text-slate-500 mb-6">Entity Anomalies</h2>
          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 h-[calc(100%-3rem)] flex flex-col backdrop-blur-md">
            {qualLoading ? (
              <div className="flex-1 animate-pulse bg-slate-800/50 rounded-lg" />
            ) : rejectionChart.length === 0 ? (
              <div className="flex-1 flex flex-col items-center justify-center text-emerald-500/80 gap-3">
                <CheckCircle className="w-10 h-10" />
                <span className="text-sm font-black uppercase tracking-widest">No Integrity Anomalies</span>
              </div>
            ) : (
              <>
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={rejectionChart} layout="vertical" margin={{ top: 0, right: 20, left: 10, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#1e293b" />
                    <XAxis type="number" tick={{ fontSize: 11, fill: "#64748b" }} axisLine={false} tickLine={false} />
                    <YAxis
                      type="category"
                      dataKey="name"
                      tick={{ fontSize: 11, fill: "#94a3b8", fontWeight: "bold" }}
                      axisLine={false}
                      tickLine={false}
                      width={100}
                    />
                    <Tooltip
                      contentStyle={{ backgroundColor: "#0f172a", fontSize: 12, borderRadius: 8, border: "1px solid #1e293b", color: "#f8fafc" }}
                      itemStyle={{ color: "#ef4444", fontWeight: "bold" }}
                    />
                    <Bar dataKey="count" radius={[0, 4, 4, 0]} name="Rejections">
                      {rejectionChart.map((_, i) => (
                        <Cell key={i} fill={i === 0 ? "#ef4444" : i === 1 ? "#f97316" : "#f59e0b"} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>

                {/* Entity top errors */}
                {quality && quality.by_entity_type.length > 0 && (
                  <div className="mt-6 space-y-4 pt-4 border-t border-slate-800/60">
                    {quality.by_entity_type.slice(0, 3).map((e) => (
                      <div key={e.entity_type}>
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-[10px] font-black uppercase tracking-widest text-slate-300">
                            {e.entity_type.replace(/_/g, " ")}
                          </span>
                          <span className="text-[9px] font-black tracking-widest uppercase bg-red-500/10 text-red-500 border border-red-500/30 px-2 py-0.5 rounded shadow-[0_0_10px_rgba(239,68,68,0.2)]">
                            {e.rejection_count.toLocaleString()} Errors
                          </span>
                        </div>
                        {e.top_errors.length > 0 && (
                          <div className="space-y-1 bg-slate-950/50 p-2 rounded border border-slate-800/50">
                            {e.top_errors.slice(0, 2).map((err, i) => (
                              <p key={i} className="text-xs text-slate-500 truncate font-mono" title={err}>
                                <span className="text-red-500/50 mr-1">&gt;</span> {err}
                              </p>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        {/* Pipeline Runs Table */}
        <div>
          <h2 className="text-base font-bold uppercase tracking-widest text-slate-500 mb-6">Execution Registry</h2>
          {runsError ? (
            <div className="bg-slate-900 border border-red-500/20 rounded-xl p-6">
              <ErrorState onRetry={refetchRuns} title="Registry synchronization failed" />
            </div>
          ) : (
            <div className="bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden backdrop-blur-md">
              {runsLoading ? (
                <SkeletonTable rows={8} cols={5} />
              ) : (runs ?? []).length === 0 ? (
                <div className="py-12 flex flex-col items-center justify-center gap-3">
                  <Activity className="h-8 w-8 text-slate-600" />
                  <p className="text-sm font-black tracking-widest uppercase text-slate-500">No execution signatures</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-slate-950/80 border-b border-slate-800/80">
                        <th className="px-4 py-3 w-10"></th>
                        <th className="px-4 py-3 text-left text-[10px] font-black tracking-widest uppercase text-slate-500">Protocol</th>
                        <th className="px-4 py-3 text-left text-[10px] font-black tracking-widest uppercase text-slate-500">Status</th>
                        <th className="px-4 py-3 text-right text-[10px] font-black tracking-widest uppercase text-slate-500">Received</th>
                        <th className="px-4 py-3 text-right text-[10px] font-black tracking-widest uppercase text-slate-500">Committed</th>
                        <th className="px-4 py-3 text-right text-[10px] font-black tracking-widest uppercase text-slate-500">Lat</th>
                        <th className="px-4 py-3 text-left text-[10px] font-black tracking-widest uppercase text-slate-500">T-Minus</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(runs ?? []).map((run) => (
                        <RunRow key={run.id} run={run} />
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Failures Grid */}
      <div className="pt-4 pb-12">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-base font-bold uppercase tracking-widest text-slate-500">Critical Incident Log</h2>
          <select
            value={failureSource}
            onChange={(e) => { setFailureSource(e.target.value); setFailureOffset(0); }}
            className="bg-slate-900 border border-slate-700 text-slate-300 text-xs font-black uppercase tracking-widest py-2 px-3 rounded-md outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
          >
            <option value="">Global Source Feed</option>
            <option value="validation">Validation Vectors</option>
            <option value="scraping">Scraper Protocols</option>
          </select>
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden backdrop-blur-md">
          {failLoading ? (
            <SkeletonTable rows={8} cols={5} />
          ) : (failures?.items ?? []).length === 0 ? (
            <div className="py-16 flex flex-col items-center justify-center gap-4">
              <div className="relative">
                <div className="absolute inset-0 bg-emerald-500/20 rounded-full blur-xl" />
                <CheckCircle className="h-10 w-10 text-emerald-500 relative z-10" />
              </div>
              <div className="text-center">
                <p className="text-sm font-black tracking-widest uppercase text-slate-300 mb-1">Zero Critical Incidents</p>
                <p className="text-[10px] uppercase tracking-widest font-bold text-slate-500">
                  {failureSource ? `${failureSource} diagnostic stream is clean` : "Global diagnostic stream is clean"}
                </p>
              </div>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-slate-950/80 border-b border-slate-800/80">
                      <th className="px-6 py-4 text-left text-[10px] font-black tracking-widest uppercase text-slate-500">Source</th>
                      <th className="px-6 py-4 text-left text-[10px] font-black tracking-widest uppercase text-slate-500">Class</th>
                      <th className="px-6 py-4 text-left text-[10px] font-black tracking-widest uppercase text-slate-500">Entity</th>
                      <th className="px-6 py-4 text-left text-[10px] font-black tracking-widest uppercase text-slate-500">Exception Stack</th>
                      <th className="px-6 py-4 text-left text-[10px] font-black tracking-widest uppercase text-slate-500">Trace</th>
                      <th className="px-6 py-4 text-right text-[10px] font-black tracking-widest uppercase text-slate-500">T-Minus</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {(failures?.items ?? []).map((f, i) => (
                      <tr key={i} className="hover:bg-slate-800/30 transition-colors">
                        <td className="px-6 py-4">
                          <span className={clsx("inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-black uppercase tracking-widest border",
                            f.source === "scraping" ? "text-amber-500 border-amber-500/30 bg-amber-500/10" : "text-amber-300 border-amber-300/30 bg-amber-300/10")}>
                            {f.source}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          <span className={clsx("inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-black uppercase tracking-widest border",
                            f.severity === "error" ? "text-red-500 border-red-500/30 bg-red-500/10 shadow-[0_0_10px_rgba(239,68,68,0.2)]" : "text-amber-500 border-amber-500/30 bg-amber-500/10")}>
                            {f.severity}
                          </span>
                        </td>
                        <td className="px-6 py-4 font-bold text-slate-300 uppercase text-[10px] tracking-wider">
                          {f.category ?? f.entity_type ?? "—"}
                        </td>
                        <td className="px-6 py-4 max-w-sm">
                          <span className="truncate block text-xs font-mono text-slate-400" title={f.message}>
                            {f.message}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          {f.source_url ? (
                            <a
                              href={f.source_url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-[10px] font-black uppercase tracking-widest text-brand-400 hover:text-brand-300 transition-colors truncate block max-w-[150px]"
                              title={f.source_url}
                            >
                              {(() => {
                                try { return new URL(f.source_url).hostname; } catch { return "URI LINK"; }
                              })()}
                            </a>
                          ) : <span className="text-slate-600 font-mono">—</span>}
                        </td>
                        <td className="px-6 py-4 text-right text-slate-500 font-mono text-xs whitespace-nowrap">
                          {formatDistanceToNow(new Date(f.occurred_at), { addSuffix: true })}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="border-t border-slate-800/80 p-4">
                <Pagination
                  total={failures?.total ?? 0}
                  limit={20}
                  offset={failureOffset}
                  onOffsetChange={setFailureOffset}
                />
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ------------------------------------
// UI Helpers
// ------------------------------------

function OpKpi({ label, value, icon, color, loading }: { label: string; value: React.ReactNode; icon: React.ReactNode; color: "brand"|"blue"|"emerald"|"amber"|"red", loading?: boolean }) {
  if (loading) {
    return (
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 animate-pulse">
        <div className="w-8 h-8 rounded bg-slate-800 mb-4" />
        <div className="h-6 w-20 bg-slate-800 rounded mb-2" />
        <div className="h-3 w-16 bg-slate-800 rounded" />
      </div>
    );
  }

  const accentMap = {
    brand: "border-brand-500/20 group-hover:border-brand-500/50 group-hover:shadow-[0_0_20px_rgba(99,102,241,0.1)]",
    blue: "border-blue-500/20 group-hover:border-blue-500/50 group-hover:shadow-[0_0_20px_rgba(59,130,246,0.1)]",
    emerald: "border-emerald-500/20 group-hover:border-emerald-500/50 group-hover:shadow-[0_0_20px_rgba(16,185,129,0.1)]",
    amber: "border-amber-500/20 group-hover:border-amber-500/50 group-hover:shadow-[0_0_20px_rgba(245,158,11,0.1)]",
    red: "border-red-500/20 group-hover:border-red-500/50 group-hover:shadow-[0_0_20px_rgba(239,68,68,0.1)]",
  };
  
  return (
    <div className={clsx("bg-slate-900/60 border rounded-xl p-5 transition-all duration-300 hover:-translate-y-1 group relative overflow-hidden backdrop-blur-md", accentMap[color])}>
      <div className="mb-4">
        {icon}
      </div>
      <div className="text-3xl font-black text-white font-mono tracking-tighter mb-1">
        {typeof value === 'number' ? value.toLocaleString() : value}
      </div>
      <div className="text-[10px] font-bold uppercase tracking-widest text-slate-500">
        {label}
      </div>
    </div>
  );
}
