import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Newspaper, ExternalLink, User, Calendar, Tag } from "lucide-react";
import { api, type Article } from "../api/client";
import EmptyState from "../components/EmptyState";
import ErrorState from "../components/ErrorState";
import Pagination from "../components/Pagination";
import { Skeleton } from "../components/Skeleton";
import { format, parseISO } from "date-fns";
import clsx from "clsx";

const PAGE_SIZE = 12;
const CATEGORIES = ["All", "EV", "Insurance", "Market", "Technology", "Regulation", "Manufacturing"] as const;
type CategoryFilter = typeof CATEGORIES[number];

function fmtDate(d: string | null) {
  if (!d) return null;
  try { return format(parseISO(d), "MMM d, yyyy"); } catch { return d; }
}

function ArticleCard({ article }: { article: Article }) {
  const snippet = article.body_text
    ? article.body_text.replace(/\s+/g, " ").trim().slice(0, 200) +
      (article.body_text.length > 200 ? "…" : "")
    : null;

  const domain = (() => {
    try {
      return new URL(article.source_url).hostname.replace(/^www\./, "");
    } catch {
      return article.source_url;
    }
  })();

  const isReddit = article.source_url?.includes("reddit.com");
  const originLabel = article.data_origin === "scraped"
    ? <span className="badge text-[10px] bg-emerald-100 text-emerald-700 border-0">Live</span>
    : <span className="badge text-[10px] bg-slate-100 text-slate-500 border-0">Seeded</span>;

  const CATEGORY_COLORS: Record<string, string> = {
    EV: "bg-blue-100 text-blue-700",
    Insurance: "bg-purple-100 text-purple-700",
    Market: "bg-amber-100 text-amber-700",
    Technology: "bg-cyan-100 text-cyan-700",
    Regulation: "bg-red-100 text-red-700",
    Manufacturing: "bg-orange-100 text-orange-700",
  };
  const catColor = article.category ? (CATEGORY_COLORS[article.category] ?? "bg-slate-100 text-slate-600") : null;

  return (
    <div className="card-hover p-5 flex flex-col gap-3 group">
      {/* Source */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 flex-wrap">
          {isReddit ? (
            <span className="badge text-[10px] bg-orange-100 text-orange-700 border-0 flex items-center gap-0.5">
              <svg className="h-2.5 w-2.5" viewBox="0 0 20 20" fill="currentColor"><path d="M10 0a10 10 0 100 20A10 10 0 0010 0zm5.21 6.36a1.37 1.37 0 011.37 1.37 1.37 1.37 0 01-1.37 1.37 1.37 1.37 0 01-1.37-1.37 1.37 1.37 0 011.37-1.37zm-9.57 0a1.37 1.37 0 011.37 1.37 1.37 1.37 0 01-1.37 1.37 1.37 1.37 0 01-1.37-1.37 1.37 1.37 0 011.37-1.37zm4.78 8.5c-2.44 0-4.42-1.56-4.42-3.5h8.84c0 1.94-1.98 3.5-4.42 3.5zm-2.3-5.5a.9.9 0 01.9.9.9.9 0 01-.9.9.9.9 0 01-.9-.9.9.9 0 01.9-.9zm4.6 0a.9.9 0 01.9.9.9.9 0 01-.9.9.9.9 0 01-.9-.9.9.9 0 01.9-.9z"/></svg>
              Reddit
            </span>
          ) : (
            <span className="badge badge-neutral text-[10px]">{domain}</span>
          )}
          {originLabel}
          {article.category && catColor && (
            <span className={`badge text-[10px] border-0 flex items-center gap-0.5 ${catColor}`}>
              <Tag className="h-2.5 w-2.5" />{article.category}
            </span>
          )}
        </div>
        <span className="text-[10px] text-slate-400">
          {fmtDate(article.publication_date) ?? fmtDate(article.scraped_at)}
        </span>
      </div>

      {/* Title */}
      <h3 className="text-sm font-semibold text-slate-800 leading-snug line-clamp-2 group-hover:text-brand-600 transition-colors">
        {article.title}
      </h3>

      {/* Snippet */}
      {snippet && (
        <p className="text-xs text-slate-500 leading-relaxed line-clamp-3">{snippet}</p>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between mt-auto pt-2 border-t border-slate-50">
        <div className="flex items-center gap-1.5 text-xs text-slate-400 min-w-0">
          {article.author && (
            <>
              <User className="h-3 w-3 flex-shrink-0" />
              <span className="truncate">{article.author}</span>
            </>
          )}
        </div>
        <a
          href={article.source_url}
          target="_blank"
          rel="noreferrer"
          className="flex-shrink-0 flex items-center gap-1 text-xs text-brand-500 hover:text-brand-600 transition-colors font-medium"
        >
          Read
          <ExternalLink className="h-3 w-3" />
        </a>
      </div>
    </div>
  );
}

function ArticleCardSkeleton() {
  return (
    <div className="card p-5 space-y-3 animate-pulse">
      <div className="flex justify-between">
        <Skeleton className="h-4 w-20 rounded-full" />
        <Skeleton className="h-3 w-16" />
      </div>
      <div className="space-y-1.5">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-4/5" />
      </div>
      <div className="space-y-1">
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-3/4" />
      </div>
      <div className="flex justify-between pt-2 border-t border-slate-50">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="h-3 w-12" />
      </div>
    </div>
  );
}

type OriginFilter = "scraped" | "seeded" | "all";

export default function Articles() {
  const [offset, setOffset] = useState(0);
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
  const [originFilter, setOriginFilter] = useState<OriginFilter>("scraped");
  const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>("All");

  const origin = originFilter === "all" ? undefined : originFilter;
  const category = categoryFilter === "All" ? undefined : categoryFilter.toLowerCase();

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["articles", offset, origin, category],
    queryFn: () => api.articles({ limit: PAGE_SIZE, offset, origin, category }),
    placeholderData: (prev) => prev,
  });

  if (isError) {
    return (
      <div className="card">
        <ErrorState error={error} onRetry={refetch} />
      </div>
    );
  }

  const items: Article[] = data?.items ?? [];
  const total = data?.total ?? 0;

  return (
    <div className="space-y-6">
      {/* Header + controls */}
      <div className="flex flex-wrap items-center gap-3 justify-between">
        <div className="flex items-center gap-3">
          {/* View toggle */}
          <div className="flex items-center gap-1.5 bg-white border border-slate-200 rounded-lg p-1">
            <button
              onClick={() => setViewMode("grid")}
              className={clsx(
                "px-3 py-1.5 text-xs font-medium rounded-md transition-colors",
                viewMode === "grid" ? "bg-brand-500 text-white shadow-sm" : "text-slate-500 hover:text-slate-700"
              )}
            >
              Grid
            </button>
            <button
              onClick={() => setViewMode("list")}
              className={clsx(
                "px-3 py-1.5 text-xs font-medium rounded-md transition-colors",
                viewMode === "list" ? "bg-brand-500 text-white shadow-sm" : "text-slate-500 hover:text-slate-700"
              )}
            >
              List
            </button>
          </div>
          {/* Origin filter */}
          <div className="flex items-center gap-1.5 bg-white border border-slate-200 rounded-lg p-1">
            {(["scraped", "all", "seeded"] as OriginFilter[]).map((o) => (
              <button
                key={o}
                onClick={() => { setOriginFilter(o); setOffset(0); }}
                className={clsx(
                  "px-3 py-1.5 text-xs font-medium rounded-md transition-colors",
                  originFilter === o
                    ? o === "scraped" ? "bg-emerald-500 text-white shadow-sm"
                      : o === "seeded" ? "bg-slate-400 text-white shadow-sm"
                      : "bg-brand-500 text-white shadow-sm"
                    : "text-slate-500 hover:text-slate-700"
                )}
              >
                {o === "scraped" ? "Live" : o === "seeded" ? "Seeded" : "All"}
              </button>
            ))}
          </div>
        </div>
        {!isLoading && total > 0 && (
          <span className="text-sm text-slate-500">
            {total.toLocaleString()} articles
          </span>
        )}
      </div>

      {/* Category filter */}
      <div className="flex flex-wrap items-center gap-2">
        {CATEGORIES.map((cat) => (
          <button
            key={cat}
            onClick={() => { setCategoryFilter(cat); setOffset(0); }}
            className={clsx(
              "px-3 py-1 text-xs font-medium rounded-full border transition-colors",
              categoryFilter === cat
                ? "bg-brand-600 text-white border-brand-600 shadow-sm"
                : "bg-white text-slate-500 border-slate-200 hover:border-brand-400 hover:text-brand-600"
            )}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* Content */}
      {isLoading ? (
        <div
          className={clsx(
            viewMode === "grid"
              ? "grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4"
              : "space-y-3"
          )}
        >
          {Array.from({ length: PAGE_SIZE }).map((_, i) => (
            <ArticleCardSkeleton key={i} />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="card">
          <EmptyState
            icon={Newspaper}
            title="No articles found"
            message="Market trend articles will appear here once the scrapers have run."
          />
        </div>
      ) : (
        <>
          {viewMode === "grid" ? (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {items.map((article) => (
                <ArticleCard key={article.id} article={article} />
              ))}
            </div>
          ) : (
            <div className="card overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr>
                    <th className="table-th">Title</th>
                    <th className="table-th">Source</th>
                    <th className="table-th">Author</th>
                    <th className="table-th">Published</th>
                    <th className="table-th">Link</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((article) => {
                    const domain = (() => {
                      try {
                        return new URL(article.source_url).hostname.replace(/^www\./, "");
                      } catch {
                        return "—";
                      }
                    })();
                    return (
                      <tr key={article.id} className="table-tr">
                        <td className="table-td font-medium text-slate-800 max-w-sm">
                          <span className="line-clamp-2">{article.title}</span>
                        </td>
                        <td className="table-td text-slate-500">
                          <span className="badge badge-neutral text-[10px]">{domain}</span>
                        </td>
                        <td className="table-td text-slate-600">
                          {article.author ? (
                            <span className="flex items-center gap-1">
                              <User className="h-3 w-3" />
                              {article.author}
                            </span>
                          ) : (
                            <span className="text-slate-400">—</span>
                          )}
                        </td>
                        <td className="table-td text-slate-500 whitespace-nowrap">
                          <span className="flex items-center gap-1">
                            <Calendar className="h-3 w-3" />
                            {fmtDate(article.publication_date) ?? fmtDate(article.scraped_at) ?? "—"}
                          </span>
                        </td>
                        <td className="table-td">
                          <a
                            href={article.source_url}
                            target="_blank"
                            rel="noreferrer"
                            className="flex items-center gap-1 text-brand-500 hover:text-brand-600 text-xs transition-colors"
                          >
                            <ExternalLink className="h-3 w-3" />
                            Read
                          </a>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination */}
          <div className="card px-4 py-3">
            <Pagination
              total={total}
              limit={PAGE_SIZE}
              offset={offset}
              onOffsetChange={setOffset}
            />
          </div>
        </>
      )}
    </div>
  );
}
