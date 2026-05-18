import { useState, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import {
  Newspaper, ExternalLink, Calendar, Tag,
  ChevronDown, ChevronUp, MessageSquare, Loader2,
  MapPin, Sparkles, Clock,
} from "lucide-react";
import { api, type Article, type ArticleCategory, type ArticleEvent } from "../api/client";
import EmptyState from "../components/EmptyState";
import ErrorState from "../components/ErrorState";
import Pagination from "../components/Pagination";
import { format, parseISO, formatDistanceToNow, differenceInDays } from "date-fns";
import clsx from "clsx";

const PAGE_SIZE = 12;

// ── Category colors ───────────────────────────────────────────────────────────

const CAT_COLOR: Record<string, { fg: string; bg: string }> = {
  forum:      { fg: "#6366F1", bg: "rgba(99,102,241,0.12)" },
  erp:        { fg: "#7F77DD", bg: "rgba(127,119,221,0.12)" },
  startup:    { fg: "#1D9E75", bg: "rgba(29,158,117,0.12)" },
  finance:    { fg: "#378ADD", bg: "rgba(55,138,221,0.12)" },
  consulting: { fg: "#EF9F27", bg: "rgba(239,159,39,0.12)" },
  data:       { fg: "#D85A30", bg: "rgba(216,90,48,0.12)" },
  management: { fg: "#888780", bg: "rgba(136,135,128,0.12)" },
  automotive: { fg: "#639922", bg: "rgba(99,153,34,0.12)" },
  insurance:  { fg: "#E24B4A", bg: "rgba(226,75,74,0.12)" },
  market:     { fg: "#94A3B8", bg: "rgba(148,163,184,0.08)" },
  tunisia:    { fg: "#94A3B8", bg: "rgba(148,163,184,0.08)" },
};

function catStyle(cat: string | null) {
  return CAT_COLOR[(cat ?? "").toLowerCase()] ?? { fg: "#94A3B8", bg: "rgba(148,163,184,0.08)" };
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtDate(d: string | null): string | null {
  if (!d) return null;
  try { return format(parseISO(d), "MMM d, yyyy"); } catch { return d; }
}

function relativeOrAbsolute(d: string | null): string {
  if (!d) return "—";
  try {
    const parsed = parseISO(d);
    const days = differenceInDays(new Date(), parsed);
    if (days < 7) return formatDistanceToNow(parsed, { addSuffix: true });
    return format(parsed, "MMM d, yyyy");
  } catch { return d; }
}

function extractDomain(url: string): string {
  try { return new URL(url).hostname.replace(/^www\./, ""); }
  catch { return url; }
}

const TOPIC_KEYWORDS = [
  "AI", "ERP", "CRM", "digital transformation", "automation", "claims",
  "underwriting", "fleet", "dealer", "insurtech", "agentic", "cloud",
  "SAP", "Microsoft", "Oracle", "startup", "VC",
] as const;

function extractTopics(body: string): string[] {
  const lower = body.toLowerCase();
  return TOPIC_KEYWORDS.filter(kw => lower.includes(kw.toLowerCase()));
}

// ── Inline Groq summary ───────────────────────────────────────────────────────

function ArticleSummary({ article }: { article: Article }) {
  const [expanded, setExpanded] = useState(false);
  const [summary, setSummary] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSummarize = useCallback(async () => {
    if (summary) { setExpanded(e => !e); return; }
    setExpanded(true);
    setLoading(true);
    setError(null);
    try {
      const res = await api.articleSummarize(article.title, article.body_text ?? "");
      setSummary(res.reply);
    } catch {
      setError("Failed to summarize. Try again.");
    } finally {
      setLoading(false);
    }
  }, [article, summary]);

  return (
    <div className="mt-2">
      <button
        onClick={handleSummarize}
        className="flex items-center gap-1.5 text-xs text-indigo-400 hover:text-indigo-300 transition-colors font-medium"
      >
        <MessageSquare className="h-3 w-3" />
        {summary ? (expanded ? "Hide summary" : "Show summary") : "Summarize"}
      </button>
      {expanded && (
        <div className="mt-2 rounded-lg border border-slate-700/60 bg-slate-800/40 p-3">
          {loading ? (
            <div className="space-y-2 animate-pulse">
              <div className="h-3 w-full bg-slate-700 rounded" />
              <div className="h-3 w-5/6 bg-slate-700 rounded" />
              <div className="h-3 w-4/5 bg-slate-700 rounded" />
            </div>
          ) : error ? (
            <p className="text-xs text-red-400">{error}</p>
          ) : summary ? (
            <>
              <p className="text-xs text-slate-300 leading-relaxed whitespace-pre-line">{summary}</p>
              <a href={article.source_url} target="_blank" rel="noreferrer"
                className="inline-flex items-center gap-1 mt-2 text-xs text-indigo-400 hover:text-indigo-300 font-medium transition-colors">
                Visit source <ExternalLink className="h-3 w-3" />
              </a>
            </>
          ) : null}
        </div>
      )}
    </div>
  );
}

// ── Article card ──────────────────────────────────────────────────────────────

function ArticleCard({ article }: { article: Article }) {
  const { fg, bg } = catStyle(article.category);
  const domain = extractDomain(article.source_url);
  const dateLabel = relativeOrAbsolute(article.publication_date ?? article.scraped_at);

  return (
    <div
      className="flex flex-col gap-3 rounded-xl p-4 border transition-all duration-200 hover:-translate-y-0.5"
      style={{ background: "rgba(15,23,42,0.7)", borderColor: "rgba(255,255,255,0.07)" }}
    >
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2 flex-wrap">
          {article.category && (
            <span className="inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-medium"
              style={{ color: fg, background: bg }}>
              <Tag className="h-2.5 w-2.5" />
              {article.category_label}
            </span>
          )}
          {article.forum_subcategory && (
            <span className="text-[11px] text-indigo-400/80 font-mono">r/{article.forum_subcategory}</span>
          )}
          {article.is_new && (
            <span className="rounded-full bg-emerald-500/15 text-emerald-400 text-[10px] font-bold px-2 py-0.5 tracking-wide">NEW</span>
          )}
        </div>
        <span className="text-[11px] text-slate-500 whitespace-nowrap">{dateLabel}</span>
      </div>
      <h3 className="text-sm font-medium text-slate-200 leading-snug line-clamp-2">{article.title}</h3>
      <div className="flex items-center justify-between mt-auto pt-2 border-t border-slate-800/60">
        <div className="flex items-center gap-3">
          <span className="text-[11px] text-slate-600">{domain}</span>
          {article.region && (
            <span className="text-[10px] text-slate-600 border border-slate-700 rounded px-1.5 py-0.5">{article.region}</span>
          )}
        </div>
        <a href={article.source_url} target="_blank" rel="noreferrer" onClick={e => e.stopPropagation()}
          className="flex items-center gap-1 text-[11px] text-slate-500 hover:text-indigo-400 transition-colors">
          <ExternalLink className="h-3 w-3" />
        </a>
      </div>
      {article.body_text && <ArticleSummary article={article} />}
    </div>
  );
}

function ArticleCardSkeleton() {
  return (
    <div className="rounded-xl p-4 border border-slate-800/40 bg-slate-900/50 space-y-3 animate-pulse">
      <div className="flex justify-between">
        <div className="h-5 w-24 bg-slate-800 rounded-full" />
        <div className="h-4 w-16 bg-slate-800 rounded" />
      </div>
      <div className="space-y-1.5">
        <div className="h-4 w-full bg-slate-800 rounded" />
        <div className="h-4 w-4/5 bg-slate-800 rounded" />
      </div>
      <div className="flex justify-between pt-2 border-t border-slate-800">
        <div className="h-3 w-20 bg-slate-800 rounded" />
        <div className="h-3 w-8 bg-slate-800 rounded" />
      </div>
    </div>
  );
}

// ── Forum row (compact, for reddit posts section) ─────────────────────────────

function ForumRow({ article }: { article: Article }) {
  const { fg, bg } = catStyle(article.category);
  const subcategory = article.forum_subcategory;
  return (
    <a href={article.source_url} target="_blank" rel="noreferrer"
      className="flex items-center gap-3 px-4 py-2.5 rounded-lg hover:bg-slate-800/40 transition-colors group">
      <span className="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold" style={{ color: fg, background: bg }}>
        {subcategory ? `r/${subcategory}` : article.category_label}
      </span>
      <span className="flex-1 text-sm text-slate-400 group-hover:text-slate-200 transition-colors truncate">
        {article.title.slice(0, 80)}{article.title.length > 80 ? "…" : ""}
      </span>
      <span className="shrink-0 text-[11px] text-slate-600">{extractDomain(article.source_url)}</span>
      <span className="shrink-0 text-[11px] text-slate-600 whitespace-nowrap">{fmtDate(article.publication_date) ?? "—"}</span>
      <ExternalLink className="h-3 w-3 text-slate-700 group-hover:text-slate-400 shrink-0" />
    </a>
  );
}

// ── Category pill filter bar ──────────────────────────────────────────────────

function CategoryBar({
  categories,
  active,
  onSelect,
}: {
  categories: ArticleCategory[];
  active: string;
  onSelect: (cat: string) => void;
}) {
  const total = categories.reduce((s, c) => s + c.count, 0);
  const all = [{ category: "all", label: "All", count: total }, ...categories];

  return (
    <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-hide">
      {all.map(cat => {
        const isActive = active === cat.category;
        const { fg, bg } = catStyle(cat.category === "all" ? null : cat.category);
        return (
          <button
            key={cat.category}
            onClick={() => onSelect(cat.category)}
            className={clsx(
              "shrink-0 flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-all border",
              isActive
                ? "border-transparent text-white"
                : "border-slate-700/60 text-slate-400 hover:border-slate-600 hover:text-slate-200 bg-transparent"
            )}
            style={isActive ? { background: cat.category === "all" ? "#4F46E5" : bg, color: cat.category === "all" ? "#fff" : fg, borderColor: fg } : {}}
          >
            {cat.label}
            <span className={clsx("rounded-full px-1.5 py-0.5 text-[10px] font-bold", isActive ? "bg-white/20" : "bg-slate-800 text-slate-500")}>
              {cat.count}
            </span>
          </button>
        );
      })}
    </div>
  );
}

// ── Events: date block ────────────────────────────────────────────────────────

function DateBlock({ event }: { event: ArticleEvent }) {
  const today = new Date();
  const d = event.days_until;
  const pubDate = event.publication_date ? parseISO(event.publication_date) : null;

  let topEl: React.ReactNode = null;
  let midEl: React.ReactNode = null;
  let accent = "#94A3B8";

  if (event.is_upcoming) {
    if (d === 0) {
      topEl = <span style={{ color: "#EF4444", fontWeight: 800, fontSize: 11, letterSpacing: "0.04em" }}>TODAY</span>;
      accent = "#EF4444";
    } else if (d === 1) {
      topEl = <span style={{ color: "#F97316", fontWeight: 800, fontSize: 10, letterSpacing: "0.04em" }}>TOMORROW</span>;
      accent = "#F97316";
    } else {
      accent = d <= 7 ? "#14B8A6" : d <= 30 ? "#F59E0B" : "#94A3B8";
      topEl = <span style={{ color: accent, fontSize: 24, fontWeight: 700, lineHeight: 1 }}>{d}</span>;
      midEl = <span style={{ color: accent, fontSize: 9, fontWeight: 700, letterSpacing: "0.06em" }}>DAYS</span>;
    }
  } else {
    topEl = pubDate
      ? <span style={{ color: "#6B7280", fontSize: 13, fontWeight: 600 }}>{format(pubDate, "MMM d")}</span>
      : null;
    accent = "#4B5563";
  }

  const monthLabel = pubDate
    ? format(pubDate, pubDate.getFullYear() === today.getFullYear() ? "MMM" : "MMM yy").toUpperCase()
    : "";

  return (
    <div style={{
      width: 72, flexShrink: 0, display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center", gap: 2,
      borderRight: "1px solid rgba(255,255,255,0.05)", paddingRight: 14, paddingLeft: 4,
    }}>
      {topEl}
      {midEl}
      <span style={{ fontSize: 9, color: accent, fontWeight: 700, letterSpacing: "0.08em", marginTop: 2 }}>
        {monthLabel}
      </span>
    </div>
  );
}

// ── Events: individual event row ──────────────────────────────────────────────

function EventRow({
  event,
  expanded,
  onToggle,
  aiResponse,
  aiLoading,
  onAI,
}: {
  event: ArticleEvent;
  expanded: boolean;
  onToggle: () => void;
  aiResponse?: string;
  aiLoading?: boolean;
  onAI: () => void;
}) {
  const { fg, bg } = catStyle(event.category);
  const topics = extractTopics(event.body_text ?? "");
  const domain = extractDomain(event.source_url);

  return (
    <div className="border-b border-slate-800/40 last:border-0">
      {/* Main row */}
      <div className="flex items-stretch gap-0 py-3.5 hover:bg-slate-800/10 transition-colors">
        <DateBlock event={event} />

        {/* Center info */}
        <div className="flex-1 px-4 min-w-0">
          {/* Row 1: pills */}
          <div className="flex items-center gap-1.5 flex-wrap mb-1.5">
            <span className="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold"
              style={{ color: fg, background: bg }}>
              {event.category_label}
            </span>
            <span className="text-[10px] text-slate-500 bg-slate-800/60 rounded-full px-2 py-0.5">
              {event.event_audience}
            </span>
            {event.is_upcoming ? (
              <span className="text-[10px] text-emerald-400 bg-emerald-400/10 rounded-full px-2 py-0.5 font-bold tracking-wide">
                UPCOMING
              </span>
            ) : (
              <span className="text-[10px] text-slate-600 bg-slate-800/60 rounded-full px-2 py-0.5">
                PAST
              </span>
            )}
          </div>

          {/* Row 2: title */}
          <div className="text-sm font-medium text-slate-200 mb-1.5 leading-snug">
            {event.title}
          </div>

          {/* Row 3: location + domain */}
          <div className="flex items-center gap-3 flex-wrap">
            {event.event_location && (
              <span className="flex items-center gap-1 text-[11px] font-medium text-slate-400">
                <MapPin className="h-3 w-3" />
                {event.event_location}
              </span>
            )}
            <span className="text-[11px] text-slate-600">{domain}</span>
            {event.forum_subcategory && (
              <span className="text-[11px] text-indigo-400/70 font-mono">r/{event.forum_subcategory}</span>
            )}
          </div>
        </div>

        {/* Right: actions */}
        <div className="flex flex-col gap-2 items-end justify-center shrink-0 px-4">
          <button
            onClick={onToggle}
            className="text-xs border border-slate-700 rounded-md px-2.5 py-1 transition-colors whitespace-nowrap"
            style={{ color: expanded ? "#F9FAFB" : "#94A3B8", background: expanded ? "rgba(99,102,241,0.15)" : "transparent", borderColor: expanded ? "rgba(99,102,241,0.4)" : undefined }}
          >
            {expanded ? "Close" : "Details →"}
          </button>
          <a href={event.source_url} target="_blank" rel="noreferrer"
            className="text-slate-600 hover:text-indigo-400 transition-colors">
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
        </div>
      </div>

      {/* Expanded inline panel */}
      {expanded && (
        <div className="pb-5 pl-[88px] pr-4">
          <div className="rounded-xl border border-slate-700/50 bg-slate-800/30 p-4 flex gap-5">
            {/* Left 60%: body + topics */}
            <div style={{ flex: "0 0 60%" }} className="min-w-0">
              {event.body_text && (
                <p className="text-xs text-slate-400 leading-relaxed mb-3 whitespace-pre-line">
                  {event.body_text}
                </p>
              )}
              <div className="text-[11px] mb-2">
                <span className="text-slate-500">Who is this for: </span>
                <span className="text-slate-300 font-medium">{event.event_audience}</span>
              </div>
              {topics.length > 0 && (
                <div className="flex flex-wrap gap-1.5 items-center">
                  <span className="text-[11px] text-slate-600">Topics:</span>
                  {topics.map(t => (
                    <span key={t} className="text-[10px] bg-slate-700/60 text-slate-400 rounded px-1.5 py-0.5">
                      {t}
                    </span>
                  ))}
                </div>
              )}
            </div>

            {/* Right 40%: AI + visit */}
            <div style={{ flex: "0 0 40%" }} className="flex flex-col gap-3 items-start min-w-0">
              <button
                onClick={onAI}
                disabled={aiLoading}
                className="flex items-center gap-1.5 text-xs rounded-lg px-3 py-1.5 font-medium transition-colors disabled:opacity-50"
                style={{ background: "rgba(99,102,241,0.15)", color: "#A5B4FC", border: "1px solid rgba(99,102,241,0.25)" }}
              >
                <Sparkles className="h-3 w-3" />
                {aiLoading ? "Analyzing…" : aiResponse ? "Regenerate" : "Add to context"}
              </button>

              {aiResponse && (
                <div className="text-xs text-slate-300 leading-relaxed bg-slate-900/50 rounded-lg p-3 border border-slate-700/40 w-full">
                  {aiResponse.split("\n").filter(Boolean).map((line, i) => (
                    <p key={i} className={i > 0 ? "mt-1.5" : ""}>{line}</p>
                  ))}
                </div>
              )}

              <a href={event.source_url} target="_blank" rel="noreferrer"
                className="inline-flex items-center gap-1.5 text-xs font-medium text-indigo-400 hover:text-indigo-300 transition-colors">
                Visit event <ExternalLink className="h-3 w-3" />
              </a>

              {event.region && (
                <span className="text-[10px] text-slate-500 border border-slate-700 rounded px-1.5 py-0.5">
                  {event.region}
                </span>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Events: month timeline bar ────────────────────────────────────────────────

function MonthTimeline({ events }: { events: ArticleEvent[] }) {
  const today = new Date();

  const groups: Record<string, number> = {};
  events.forEach(e => {
    if (e.publication_date) {
      const key = e.publication_date.slice(0, 7);
      groups[key] = (groups[key] ?? 0) + 1;
    }
  });

  const months = Object.entries(groups).sort(([a], [b]) => a.localeCompare(b));
  if (months.length === 0) return null;

  const currentKey = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}`;

  return (
    <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-hide">
      {months.map(([key, count]) => {
        const [yr, mo] = key.split("-");
        const d = new Date(Number(yr), Number(mo) - 1, 1);
        const label = format(d, Number(yr) === today.getFullYear() ? "MMM yyyy" : "MMM yyyy");
        const isCurrent = key === currentKey;
        return (
          <button
            key={key}
            onClick={() => document.getElementById(`month-${key}`)?.scrollIntoView({ behavior: "smooth", block: "start" })}
            className={clsx(
              "shrink-0 flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-all border",
              isCurrent
                ? "border-teal-500/40 text-teal-400"
                : "border-slate-700/60 text-slate-500 hover:border-slate-600 hover:text-slate-300"
            )}
            style={isCurrent ? { background: "rgba(20,184,166,0.12)" } : {}}
          >
            {isCurrent && <span className="w-1.5 h-1.5 rounded-full bg-teal-400 inline-block animate-pulse" />}
            {label}
            <span className={clsx(
              "rounded-full text-[10px] font-bold px-1.5 py-0.5",
              isCurrent ? "bg-teal-500/20 text-teal-300" : "bg-slate-800 text-slate-500"
            )}>
              {count}
            </span>
          </button>
        );
      })}
    </div>
  );
}

// ── Events: full timeline view (shown when category = forum) ──────────────────

function EventsView() {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [pastOpen, setPastOpen] = useState(false);
  const [aiResponses, setAiResponses] = useState<Record<string, string>>({});
  const [aiLoadingMap, setAiLoadingMap] = useState<Record<string, boolean>>({});

  const { data: events, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["articleEvents"],
    queryFn: api.articleEvents,
    staleTime: 30000,
  });

  const handleAI = useCallback(async (event: ArticleEvent) => {
    setAiLoadingMap(m => ({ ...m, [event.id]: true }));
    try {
      const res = await api.articleSummarize(
        event.title,
        `Summarize this event and explain why it matters for ERP vendors targeting automotive and insurance companies: ${event.title} — ${(event.body_text ?? "").slice(0, 600)}`
      );
      setAiResponses(m => ({ ...m, [event.id]: res.reply }));
    } catch {
      setAiResponses(m => ({ ...m, [event.id]: "Could not generate analysis. Check API connection." }));
    } finally {
      setAiLoadingMap(m => ({ ...m, [event.id]: false }));
    }
  }, []);

  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="rounded-xl border border-slate-800/40 bg-slate-900/30 p-4 animate-pulse flex gap-4">
            <div className="w-16 h-14 bg-slate-800 rounded-lg shrink-0" />
            <div className="flex-1 space-y-2">
              <div className="h-3 w-32 bg-slate-800 rounded-full" />
              <div className="h-4 w-3/4 bg-slate-800 rounded" />
              <div className="h-3 w-1/2 bg-slate-800 rounded" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-6">
        <ErrorState error={error} onRetry={refetch} />
      </div>
    );
  }

  const evts = events ?? [];
  const upcoming = evts.filter(e => e.is_upcoming);
  const allPast = evts.filter(e => e.is_past);
  const shownPast = pastOpen ? allPast : allPast.slice(0, 5);

  const thisMonthCount = evts.filter(e => e.is_this_month).length;
  const erpCount = evts.filter(e => (e.category ?? "").toLowerCase() === "erp").length;
  const insurCount = evts.filter(e => (e.category ?? "").toLowerCase() === "insurance").length;

  // Group upcoming by month for scrollable sections
  const upcomingByMonth: Record<string, ArticleEvent[]> = {};
  upcoming.forEach(e => {
    const key = (e.publication_date ?? "").slice(0, 7);
    (upcomingByMonth[key] = upcomingByMonth[key] ?? []).push(e);
  });
  const monthKeys = Object.keys(upcomingByMonth).sort();

  const toggleExpand = (id: string) => setExpandedId(prev => prev === id ? null : id);

  return (
    <div className="space-y-6">

      {/* ── Task 4: Stats bar ─────────────────────────────────────────────── */}
      <p className="text-xs text-slate-500 flex items-center gap-2 flex-wrap">
        <Clock className="h-3 w-3 text-slate-600" />
        <span>{evts.length} events tracked</span>
        <span className="text-slate-700">·</span>
        <span>{thisMonthCount} coming this month</span>
        <span className="text-slate-700">·</span>
        <span>{erpCount} ERP conferences</span>
        <span className="text-slate-700">·</span>
        <span>{insurCount} insurance forums</span>
      </p>

      {/* ── Task 3: Month timeline ────────────────────────────────────────── */}
      <MonthTimeline events={upcoming} />

      {/* ── Section A: Upcoming ───────────────────────────────────────────── */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <Calendar className="h-4 w-4 text-teal-400" />
          <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wide">
            Upcoming forums &amp; events
          </h3>
          <span className="text-[11px] text-slate-600 bg-slate-800/60 rounded-full px-2 py-0.5">
            {upcoming.length}
          </span>
        </div>

        {upcoming.length === 0 ? (
          <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-8">
            <EmptyState
              icon={Calendar}
              title="No upcoming events in the next 30 days"
              message="Check back soon — new forums are added weekly."
            />
          </div>
        ) : (
          <div className="space-y-4">
            {monthKeys.map(monthKey => {
              const [yr, mo] = monthKey.split("-");
              const d = new Date(Number(yr), Number(mo) - 1, 1);
              const monthLabel = format(d, "MMMM yyyy");
              const monthEvents = upcomingByMonth[monthKey];
              return (
                <div key={monthKey} id={`month-${monthKey}`}>
                  <div className="text-[10px] font-bold text-slate-600 uppercase tracking-widest mb-2 px-1">
                    {monthLabel}
                  </div>
                  <div className="rounded-xl border border-slate-800/60 bg-slate-900/20 overflow-hidden">
                    {monthEvents.map(e => (
                      <EventRow
                        key={e.id}
                        event={e}
                        expanded={expandedId === e.id}
                        onToggle={() => toggleExpand(e.id)}
                        aiResponse={aiResponses[e.id]}
                        aiLoading={aiLoadingMap[e.id]}
                        onAI={() => handleAI(e)}
                      />
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ── Section B: Recently concluded ────────────────────────────────── */}
      {allPast.length > 0 && (
        <div className="rounded-xl border border-slate-800/60 bg-slate-900/20 overflow-hidden">
          <button
            className="w-full flex items-center justify-between px-5 py-3.5 text-left hover:bg-slate-800/20 transition-colors"
            onClick={() => setPastOpen(o => !o)}
          >
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
                Recently concluded
              </span>
              <span className="text-[11px] text-slate-600 bg-slate-800/60 rounded-full px-2 py-0.5">
                {allPast.length}
              </span>
            </div>
            {pastOpen
              ? <ChevronUp className="h-4 w-4 text-slate-600" />
              : <ChevronDown className="h-4 w-4 text-slate-600" />}
          </button>

          {pastOpen && (
            <div className="border-t border-slate-800/40">
              {shownPast.map(e => (
                <EventRow
                  key={e.id}
                  event={e}
                  expanded={expandedId === e.id}
                  onToggle={() => toggleExpand(e.id)}
                  aiResponse={aiResponses[e.id]}
                  aiLoading={aiLoadingMap[e.id]}
                  onAI={() => handleAI(e)}
                />
              ))}
              {allPast.length > 5 && (
                <button
                  onClick={() => setPastOpen(true)}
                  className="w-full text-center py-2.5 text-xs text-slate-600 hover:text-slate-400 transition-colors"
                >
                  Show all {allPast.length} past events
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

type OriginFilter = "scraped" | "reference" | "all";

export default function Articles() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [offset, setOffset] = useState(0);
  const [originFilter, setOriginFilter] = useState<OriginFilter>("scraped");
  const [forumOpen, setForumOpen] = useState(false);

  const activeCategory = searchParams.get("category") ?? "all";
  const isForumView = activeCategory === "forum";

  const setCategory = (cat: string) => {
    setOffset(0);
    const next = new URLSearchParams(searchParams);
    if (cat === "all") next.delete("category");
    else next.set("category", cat);
    setSearchParams(next, { replace: true });
  };

  const origin = originFilter === "all" ? undefined : originFilter;
  const categoryParam = activeCategory === "all" ? undefined : activeCategory;

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["articles", offset, origin, categoryParam],
    queryFn: () => api.articles({ limit: PAGE_SIZE, offset, origin, category: categoryParam, sort: "recent" }),
    placeholderData: (prev) => prev,
    staleTime: 30000,
    enabled: !isForumView,
  });

  const { data: categories } = useQuery({
    queryKey: ["articleCategories"],
    queryFn: api.articleCategories,
    staleTime: 30000,
  });

  const { data: forumData } = useQuery({
    queryKey: ["articles-forum"],
    queryFn: () => api.articles({ limit: 10, category: "forum", sort: "recent" }),
    staleTime: 30000,
    enabled: forumOpen && !isForumView,
  });

  const items: Article[] = data?.items ?? [];
  const total = data?.total ?? 0;

  return (
    <div className="space-y-6 text-slate-200">

      {/* ── Controls — hidden when forum/events view is active ────────────── */}
      {!isForumView && (
        <div className="flex flex-wrap items-center gap-3 justify-between">
          <div className="flex items-center gap-1.5 bg-slate-900/60 border border-slate-800 rounded-lg p-1">
            {(["scraped", "all", "reference"] as OriginFilter[]).map((o) => (
              <button
                key={o}
                onClick={() => { setOriginFilter(o); setOffset(0); }}
                className={clsx(
                  "px-3 py-1.5 text-xs font-medium rounded-md transition-colors",
                  originFilter === o
                    ? o === "scraped" ? "bg-emerald-600 text-white"
                    : o === "reference" ? "bg-slate-600 text-white"
                    : "bg-indigo-600 text-white"
                    : "text-slate-400 hover:text-slate-200"
                )}
              >
                {o === "scraped" ? "Live" : o === "reference" ? "Reference" : "All"}
              </button>
            ))}
          </div>
          {!isLoading && total > 0 && (
            <span className="text-sm text-slate-500">{total.toLocaleString()} articles</span>
          )}
        </div>
      )}

      {/* ── Category pill filter bar — always visible ─────────────────────── */}
      {categories && categories.length > 0 ? (
        <CategoryBar categories={categories} active={activeCategory} onSelect={setCategory} />
      ) : (
        <div className="flex gap-2">
          {[1,2,3,4,5].map(i => <div key={i} className="h-8 w-24 bg-slate-800 rounded-full animate-pulse" />)}
        </div>
      )}

      {/* ── Conditional view: EventsView vs article grid ──────────────────── */}
      {isForumView ? (
        <EventsView />
      ) : (
        <>
          {isError ? (
            <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-6">
              <ErrorState error={error} onRetry={refetch} />
            </div>
          ) : isLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {Array.from({ length: PAGE_SIZE }).map((_, i) => <ArticleCardSkeleton key={i} />)}
            </div>
          ) : items.length === 0 ? (
            <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-8">
              <EmptyState icon={Newspaper} title="No articles found" message="Try a different category or origin filter." />
            </div>
          ) : (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {items.map(article => <ArticleCard key={article.id} article={article} />)}
              </div>
              <div className="rounded-xl border border-slate-800 bg-slate-900/40 px-4 py-3">
                <Pagination total={total} limit={PAGE_SIZE} offset={offset} onOffsetChange={setOffset} />
              </div>
            </>
          )}

          {/* ── Reddit posts section (collapsible, non-forum views) ─────── */}
          <div className="rounded-xl border border-slate-800 bg-slate-900/40 overflow-hidden">
            <button
              className="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-slate-800/30 transition-colors"
              onClick={() => setForumOpen(o => !o)}
            >
              <div className="flex items-center gap-2.5">
                <MessageSquare className="h-4 w-4 text-indigo-400" />
                <span className="text-sm font-semibold text-slate-300 uppercase tracking-wide">
                  Forum & Professional Discourse
                </span>
                <span className="text-[11px] text-slate-500">ERP · Startups · Finance · Data · Consulting · Management</span>
              </div>
              {forumOpen ? <ChevronUp className="h-4 w-4 text-slate-500" /> : <ChevronDown className="h-4 w-4 text-slate-500" />}
            </button>
            {forumOpen && (
              <div className="border-t border-slate-800 divide-y divide-slate-800/50">
                {!forumData ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="h-5 w-5 text-slate-600 animate-spin" />
                  </div>
                ) : forumData.items.length === 0 ? (
                  <div className="px-5 py-6 text-sm text-slate-600 text-center">No professional articles found.</div>
                ) : (
                  forumData.items.map(article => <ForumRow key={article.id} article={article} />)
                )}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
