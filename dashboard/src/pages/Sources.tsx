import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Database,
  Plus,
  X,
  Check,
  Pencil,
  Trash2,
  Globe,
  Tag,
  ExternalLink,
  RefreshCw,
  Search,
} from "lucide-react";
import clsx from "clsx";
import { api } from "../api/client";
import type { Source, SourceCreatePayload, SourcePatchPayload, KeywordSearchResult } from "../api/client";
import KpiCard from "../components/KpiCard";
import EmptyState from "../components/EmptyState";
import ErrorState from "../components/ErrorState";
import { SkeletonTable } from "../components/Skeleton";
import { format, parseISO } from "date-fns";

const SOURCE_TYPE_LABELS: Record<string, string> = {
  automotive_review: "Auto Review",
  news_blog: "News / Blog",
  marketplace: "Marketplace",
  insurance_review: "Insurance",
  forum: "Forum",
  pricing_page: "Pricing",
  trend_article: "Trend Article",
};

const SOURCE_TYPES = Object.keys(SOURCE_TYPE_LABELS);

const REGIONS = ["EU", "US", "TN", "Global"];

function fmtDate(d: string | null) {
  if (!d) return "—";
  try {
    return format(parseISO(d), "MMM d, yyyy HH:mm");
  } catch {
    return d;
  }
}

function reliabilityColor(score: number): string {
  if (score >= 0.85) return "text-emerald-600 bg-emerald-50";
  if (score >= 0.7) return "text-amber-600 bg-amber-50";
  return "text-red-600 bg-red-50";
}

export default function Sources() {
  const queryClient = useQueryClient();
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editKeywordsId, setEditKeywordsId] = useState<string | null>(null);
  const [keywordsInput, setKeywordsInput] = useState("");

  // Form state for new source
  const [form, setForm] = useState<SourceCreatePayload>({
    name: "",
    base_url: "",
    source_type: undefined,
    reliability_score: 0.8,
    is_active: true,
    region: undefined,
    keywords: [],
  });

  const {
    data: sources,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["sources"],
    queryFn: () => api.sources(),
    staleTime: 30000,
  });

  const createMut = useMutation({
    mutationFn: (payload: SourceCreatePayload) => api.createSource(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sources"] });
      setShowAddForm(false);
      resetForm();
    },
  });

  const updateMut = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: SourcePatchPayload }) =>
      api.updateSource(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sources"] });
      setEditingId(null);
      setEditKeywordsId(null);
    },
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => api.deleteSource(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sources"] });
    },
  });

  // --- Keyword Monitoring state & mutations ---
  const [kwInput, setKwInput] = useState("");
  const [kwRegion, setKwRegion] = useState("");
  const [searchResult, setSearchResult] = useState<KeywordSearchResult | null>(null);

  const {
    data: keywords,
    isLoading: kwLoading,
  } = useQuery({
    queryKey: ["keywords"],
    queryFn: () => api.keywords(),
    staleTime: 30000,
  });

  const addKwMut = useMutation({
    mutationFn: ({ keyword, region }: { keyword: string; region?: string }) =>
      api.createKeyword(keyword, region || undefined),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["keywords"] });
      setKwInput("");
      setKwRegion("");
    },
  });

  const delKwMut = useMutation({
    mutationFn: (id: string) => api.deleteKeyword(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["keywords"] });
    },
  });

  const searchNowMut = useMutation({
    mutationFn: () => api.keywordSearchNow(),
    onSuccess: (result) => {
      setSearchResult(result);
      queryClient.invalidateQueries({ queryKey: ["keywords"] });
    },
  });

  function resetForm() {
    setForm({
      name: "",
      base_url: "",
      source_type: undefined,
      reliability_score: 0.8,
      is_active: true,
      region: undefined,
      keywords: [],
    });
  }

  function handleCreate() {
    if (!form.name.trim() || !form.base_url.trim()) return;
    createMut.mutate(form);
  }

  function handleToggleActive(src: Source) {
    updateMut.mutate({ id: src.id, payload: { is_active: !src.is_active } });
  }

  function handleSaveKeywords(src: Source) {
    const kw = keywordsInput
      .split(",")
      .map((k) => k.trim())
      .filter(Boolean);
    updateMut.mutate({ id: src.id, payload: { keywords: kw } });
  }

  function handleDelete(src: Source) {
    if (!confirm(`Soft-delete source "${src.name}"?`)) return;
    deleteMut.mutate(src.id);
  }

  function startEditKeywords(src: Source) {
    setEditKeywordsId(src.id);
    setKeywordsInput((src.keywords ?? []).join(", "));
  }

  if (isError) {
    return (
      <div className="card">
        <ErrorState error={error} onRetry={refetch} />
      </div>
    );
  }

  const items = sources ?? [];
  const activeCount = items.filter((s) => s.is_active).length;
  const avgReliability =
    items.length > 0
      ? items.reduce((a, s) => a + s.reliability_score, 0) / items.length
      : 0;
  const totalRecords = items.reduce((a, s) => a + s.total_records_scraped, 0);
  const regions = new Set(items.map((s) => s.region).filter(Boolean));

  return (
    <div className="space-y-6">
      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard
          label="Total Sources"
          value={items.length}
          icon={Database}
          iconColor="text-brand-500"
          loading={isLoading}
        />
        <KpiCard
          label="Active"
          value={activeCount}
          sub={`of ${items.length} sources`}
          icon={Check}
          iconColor="text-emerald-500"
          loading={isLoading}
        />
        <KpiCard
          label="Avg Reliability"
          value={avgReliability > 0 ? `${(avgReliability * 100).toFixed(0)}%` : "—"}
          icon={RefreshCw}
          iconColor="text-amber-500"
          loading={isLoading}
        />
        <KpiCard
          label="Regions"
          value={regions.size}
          sub={[...regions].join(", ") || "—"}
          icon={Globe}
          iconColor="text-blue-500"
          loading={isLoading}
        />
      </div>

      {/* Actions bar */}
      <div className="card p-4 flex items-center justify-between">
        <p className="text-sm text-slate-600">
          Manage scraping sources — add new data feeds, toggle active status, and edit keywords.
        </p>
        <button
          onClick={() => setShowAddForm(!showAddForm)}
          className={clsx(
            "flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium transition-colors",
            showAddForm
              ? "bg-slate-200 text-slate-700"
              : "bg-brand-500 text-white hover:bg-brand-600"
          )}
        >
          {showAddForm ? <X className="h-3.5 w-3.5" /> : <Plus className="h-3.5 w-3.5" />}
          {showAddForm ? "Cancel" : "Add Source"}
        </button>
      </div>

      {/* Add form */}
      {showAddForm && (
        <div className="card p-5 space-y-4 border-l-4 border-brand-500">
          <h3 className="text-sm font-semibold text-slate-800">New Source</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Name *</label>
              <input
                type="text"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="e.g. Trustpilot"
                className="text-input w-full"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Base URL *</label>
              <input
                type="text"
                value={form.base_url}
                onChange={(e) => setForm({ ...form, base_url: e.target.value })}
                placeholder="https://example.com"
                className="text-input w-full"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Source Type</label>
              <select
                value={form.source_type ?? ""}
                onChange={(e) => setForm({ ...form, source_type: e.target.value || undefined })}
                className="select-input w-full"
              >
                <option value="">Select type…</option>
                {SOURCE_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {SOURCE_TYPE_LABELS[t]}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Region</label>
              <select
                value={form.region ?? ""}
                onChange={(e) => setForm({ ...form, region: e.target.value || undefined })}
                className="select-input w-full"
              >
                <option value="">Select region…</option>
                {REGIONS.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">
                Reliability (0–1)
              </label>
              <input
                type="number"
                min={0}
                max={1}
                step={0.05}
                value={form.reliability_score}
                onChange={(e) =>
                  setForm({ ...form, reliability_score: parseFloat(e.target.value) || 0.8 })
                }
                className="text-input w-full"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">
                Keywords (comma-separated)
              </label>
              <input
                type="text"
                value={(form.keywords ?? []).join(", ")}
                onChange={(e) =>
                  setForm({
                    ...form,
                    keywords: e.target.value
                      .split(",")
                      .map((k) => k.trim())
                      .filter(Boolean),
                  })
                }
                placeholder="car, review, dealer"
                className="text-input w-full"
              />
            </div>
          </div>
          <div className="flex items-center gap-3 pt-2">
            <button
              onClick={handleCreate}
              disabled={!form.name.trim() || !form.base_url.trim() || createMut.isPending}
              className="btn-primary disabled:opacity-50"
            >
              {createMut.isPending ? "Creating…" : "Create Source"}
            </button>
            {createMut.isError && (
              <span className="text-xs text-red-500">
                {(createMut.error as Error).message}
              </span>
            )}
          </div>
        </div>
      )}

      {/* Table */}
      <div className="card overflow-hidden">
        {isLoading ? (
          <SkeletonTable rows={6} cols={7} />
        ) : items.length === 0 ? (
          <EmptyState
            icon={Database}
            title="No sources yet"
            message="Add your first scraping source to get started."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50/60">
                  <th className="px-4 py-3 text-xs font-semibold text-slate-600 uppercase tracking-wider">
                    Source
                  </th>
                  <th className="px-4 py-3 text-xs font-semibold text-slate-600 uppercase tracking-wider">
                    Type
                  </th>
                  <th className="px-4 py-3 text-xs font-semibold text-slate-600 uppercase tracking-wider">
                    Region
                  </th>
                  <th className="px-4 py-3 text-xs font-semibold text-slate-600 uppercase tracking-wider">
                    Reliability
                  </th>
                  <th className="px-4 py-3 text-xs font-semibold text-slate-600 uppercase tracking-wider">
                    Keywords
                  </th>
                  <th className="px-4 py-3 text-xs font-semibold text-slate-600 uppercase tracking-wider">
                    Records
                  </th>
                  <th className="px-4 py-3 text-xs font-semibold text-slate-600 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-4 py-3 text-xs font-semibold text-slate-600 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {items.map((src) => (
                  <tr
                    key={src.id}
                    className="hover:bg-slate-50/50 transition-colors"
                  >
                    {/* Name + URL */}
                    <td className="px-4 py-3">
                      <div className="text-sm font-medium text-slate-800">
                        {src.name}
                      </div>
                      <a
                        href={src.base_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-[11px] text-slate-400 hover:text-brand-500 flex items-center gap-0.5 mt-0.5"
                      >
                        {src.base_url.replace(/^https?:\/\//, "").slice(0, 40)}
                        <ExternalLink className="h-2.5 w-2.5" />
                      </a>
                    </td>

                    {/* Type */}
                    <td className="px-4 py-3">
                      <span className="text-xs text-slate-600">
                        {src.source_type
                          ? SOURCE_TYPE_LABELS[src.source_type] ?? src.source_type
                          : "—"}
                      </span>
                    </td>

                    {/* Region */}
                    <td className="px-4 py-3">
                      {src.region ? (
                        <span className="inline-flex items-center gap-1 text-xs text-slate-600">
                          <Globe className="h-3 w-3" />
                          {src.region}
                        </span>
                      ) : (
                        <span className="text-xs text-slate-400">—</span>
                      )}
                    </td>

                    {/* Reliability */}
                    <td className="px-4 py-3">
                      <span
                        className={clsx(
                          "inline-block px-2 py-0.5 rounded-full text-xs font-medium",
                          reliabilityColor(src.reliability_score)
                        )}
                      >
                        {(src.reliability_score * 100).toFixed(0)}%
                      </span>
                    </td>

                    {/* Keywords */}
                    <td className="px-4 py-3 max-w-[200px]">
                      {editKeywordsId === src.id ? (
                        <div className="flex items-center gap-1">
                          <input
                            type="text"
                            value={keywordsInput}
                            onChange={(e) => setKeywordsInput(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") handleSaveKeywords(src);
                              if (e.key === "Escape") setEditKeywordsId(null);
                            }}
                            className="text-input text-xs py-1 flex-1 min-w-0"
                            autoFocus
                          />
                          <button
                            onClick={() => handleSaveKeywords(src)}
                            className="p-1 rounded text-emerald-600 hover:bg-emerald-50"
                          >
                            <Check className="h-3.5 w-3.5" />
                          </button>
                          <button
                            onClick={() => setEditKeywordsId(null)}
                            className="p-1 rounded text-slate-400 hover:bg-slate-100"
                          >
                            <X className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      ) : (
                        <div
                          className="flex flex-wrap gap-1 cursor-pointer group"
                          onClick={() => startEditKeywords(src)}
                        >
                          {(src.keywords ?? []).length > 0 ? (
                            <>
                              {(src.keywords ?? []).slice(0, 3).map((kw) => (
                                <span
                                  key={kw}
                                  className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-slate-100 text-[10px] text-slate-600"
                                >
                                  <Tag className="h-2.5 w-2.5" />
                                  {kw}
                                </span>
                              ))}
                              {(src.keywords ?? []).length > 3 && (
                                <span className="text-[10px] text-slate-400">
                                  +{(src.keywords ?? []).length - 3}
                                </span>
                              )}
                              <Pencil className="h-3 w-3 text-slate-300 opacity-0 group-hover:opacity-100 transition-opacity ml-1" />
                            </>
                          ) : (
                            <span className="text-[10px] text-slate-400 group-hover:text-brand-500">
                              + Add keywords
                            </span>
                          )}
                        </div>
                      )}
                    </td>

                    {/* Records */}
                    <td className="px-4 py-3">
                      <span className="text-xs text-slate-600">
                        {src.total_records_scraped.toLocaleString()}
                      </span>
                      {src.last_scraped_at && (
                        <div className="text-[10px] text-slate-400 mt-0.5">
                          Last: {fmtDate(src.last_scraped_at)}
                        </div>
                      )}
                    </td>

                    {/* Status toggle */}
                    <td className="px-4 py-3">
                      <button
                        onClick={() => handleToggleActive(src)}
                        className={clsx(
                          "relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full transition-colors duration-200 ease-in-out",
                          src.is_active ? "bg-emerald-500" : "bg-slate-300"
                        )}
                      >
                        <span
                          className={clsx(
                            "inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform duration-200 ease-in-out mt-0.5",
                            src.is_active ? "translate-x-4 ml-0.5" : "translate-x-0.5"
                          )}
                        />
                      </button>
                    </td>

                    {/* Actions */}
                    <td className="px-4 py-3">
                      <button
                        onClick={() => handleDelete(src)}
                        className="p-1.5 rounded-md text-slate-400 hover:text-red-500 hover:bg-red-50 transition-colors"
                        title="Delete source"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Footer summary */}
        {items.length > 0 && (
          <div className="px-4 py-3 border-t border-slate-100 bg-slate-50/40 flex items-center justify-between">
            <span className="text-xs text-slate-500">
              {items.length} source{items.length !== 1 ? "s" : ""} · {totalRecords.toLocaleString()} total records scraped
            </span>
          </div>
        )}
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Keyword Monitoring                                                 */}
      {/* ------------------------------------------------------------------ */}
      <div className="card p-5 space-y-4 border-l-4 border-violet-500">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-slate-800 flex items-center gap-2">
              <Search className="h-4 w-4 text-violet-500" />
              Keyword Monitoring
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Add keywords and the platform will automatically discover matching articles from Google News &amp; Bing News RSS.
            </p>
          </div>
          <button
            onClick={() => {
              setSearchResult(null);
              searchNowMut.mutate();
            }}
            disabled={searchNowMut.isPending || !keywords?.length}
            className={clsx(
              "flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all",
              searchNowMut.isPending
                ? "bg-violet-100 text-violet-400 cursor-wait"
                : keywords?.length
                ? "bg-violet-600 text-white hover:bg-violet-700 shadow-sm"
                : "bg-slate-100 text-slate-400 cursor-not-allowed"
            )}
          >
            {searchNowMut.isPending ? (
              <RefreshCw className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Search className="h-3.5 w-3.5" />
            )}
            {searchNowMut.isPending ? "Searching…" : "Search Now"}
          </button>
        </div>

        {/* Search result feedback */}
        {searchResult && (
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-emerald-50 border border-emerald-200 text-xs text-emerald-700">
            <Check className="h-3.5 w-3.5 text-emerald-500 flex-shrink-0" />
            <span>
              Search complete — found <strong>{searchResult.articles_found}</strong> articles,{" "}
              <strong>{searchResult.articles_inserted}</strong> new
              {searchResult.articles_inserted > 0 && " (now visible in the Articles page)"}.
              {searchResult.articles_duplicate > 0 && ` ${searchResult.articles_duplicate} duplicates skipped.`}
            </span>
            <button onClick={() => setSearchResult(null)} className="ml-auto text-emerald-400 hover:text-emerald-600">
              <X className="h-3 w-3" />
            </button>
          </div>
        )}

        {searchNowMut.isError && (
          <div className="px-3 py-2 rounded-lg bg-red-50 border border-red-200 text-xs text-red-600">
            Search failed: {(searchNowMut.error as Error).message}
          </div>
        )}

        {/* Active keyword chips */}
        <div className="min-h-[40px]">
          {kwLoading ? (
            <div className="flex gap-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-7 w-28 rounded-full bg-slate-100 animate-pulse" />
              ))}
            </div>
          ) : (keywords ?? []).length === 0 ? (
            <p className="text-xs text-slate-400 italic">No keywords yet. Add one below to start monitoring.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {(keywords ?? []).map((kw) => (
                <span
                  key={kw.id}
                  className={clsx(
                    "inline-flex items-center gap-1.5 pl-3 pr-1.5 py-1 rounded-full text-xs font-medium transition-all",
                    kw.is_active
                      ? "bg-violet-100 text-violet-800 border border-violet-200"
                      : "bg-slate-100 text-slate-500 border border-slate-200"
                  )}
                >
                  <Tag className="h-3 w-3 flex-shrink-0" />
                  <span>{kw.keyword}</span>
                  {kw.region && (
                    <span className="text-[10px] text-violet-500 bg-violet-50 px-1 rounded">
                      {kw.region}
                    </span>
                  )}
                  {kw.results_count > 0 && (
                    <span className="text-[10px] text-slate-400">{kw.results_count} articles</span>
                  )}
                  <button
                    onClick={() => delKwMut.mutate(kw.id)}
                    disabled={delKwMut.isPending}
                    className="ml-0.5 p-0.5 rounded-full text-violet-400 hover:text-red-500 hover:bg-red-50 transition-colors"
                    title={`Remove "${kw.keyword}"`}
                  >
                    <X className="h-3 w-3" />
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Add keyword form */}
        <div className="flex items-center gap-2 pt-1 border-t border-slate-100">
          <input
            id="kw-input"
            type="text"
            value={kwInput}
            onChange={(e) => setKwInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && kwInput.trim()) {
                addKwMut.mutate({ keyword: kwInput.trim(), region: kwRegion || undefined });
              }
            }}
            placeholder="e.g. Tunisia insurance market"
            className="text-input text-xs flex-1 min-w-0"
          />
          <select
            value={kwRegion}
            onChange={(e) => setKwRegion(e.target.value)}
            className="select-input text-xs w-28"
          >
            <option value="">Any region</option>
            {REGIONS.map((r) => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>
          <button
            onClick={() => {
              if (kwInput.trim()) {
                addKwMut.mutate({ keyword: kwInput.trim(), region: kwRegion || undefined });
              }
            }}
            disabled={!kwInput.trim() || addKwMut.isPending}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-violet-600 text-white text-xs font-semibold hover:bg-violet-700 disabled:opacity-50 transition-colors flex-shrink-0"
          >
            <Plus className="h-3.5 w-3.5" />
            {addKwMut.isPending ? "Adding…" : "Add keyword"}
          </button>
        </div>
        {addKwMut.isError && (
          <p className="text-xs text-red-500 mt-1">{(addKwMut.error as Error).message}</p>
        )}
      </div>
    </div>
  );
}
