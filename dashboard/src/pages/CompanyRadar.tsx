import { useState, useEffect, useRef, useCallback } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  AlertCircle,
  TrendingDown,
  Layers,
  Star,
  Quote,
  Sparkles,
  Search,
  ArrowRight,
  X,
  ExternalLink,
  BookOpen,
} from "lucide-react";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  ComposedChart,
  Line,
  ScatterChart,
  Scatter,
  ZAxis,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Cell,
} from "recharts";

const API = import.meta.env.VITE_API_URL || "";

// ─── CSS ─────────────────────────────────────────────────────────────────────

const STYLES = `
  @keyframes cr-shimmer { 0%,100% { opacity: 0.4; } 50% { opacity: 0.8; } }
  @keyframes cr-fade-in { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
  .cr-skel { background: #1F2937; border-radius: 4px; animation: cr-shimmer 1.5s ease-in-out infinite; }
  .cr-section { opacity: 0; animation: cr-fade-in 250ms ease-out forwards; }
  .cr-search-input { background: #111827; border: 1px solid #1F2937; color: #F9FAFB; padding: 14px 20px 14px 48px;
    border-radius: 10px; font-size: 15px; width: 100%; outline: none; font-family: 'DM Sans', sans-serif;
    transition: border-color 150ms ease; }
  .cr-search-input:focus { border-color: #6366f1; }
  .cr-search-input::placeholder { color: #6B7280; }
  .cr-dropdown-item { padding: 10px 16px; cursor: pointer; display: flex; align-items: center; gap: 12px;
    transition: background-color 150ms ease; }
  .cr-dropdown-item:hover { background-color: #1F2937; }
  .cr-card { background: #111827; border: 1px solid #1F2937; border-radius: 10px; padding: 20px;
    transition: border-color 150ms ease; }
  .cr-card:hover { border-color: #374151; }
  .cr-news-item { cursor: pointer; transition: border-color 150ms ease, background 150ms ease; }
  .cr-news-item:hover { border-color: #6366f1 !important; background: #131929 !important; }
  @keyframes cr-modal-in { from { opacity: 0; transform: scale(0.97) translateY(8px); } to { opacity: 1; transform: scale(1) translateY(0); } }
  .cr-modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.75); backdrop-filter: blur(4px);
    display: flex; align-items: center; justify-content: center; z-index: 1000; padding: 24px; }
  .cr-modal { background: #0D1117; border: 1px solid #1F2937; border-radius: 14px; max-width: 560px; width: 100%;
    padding: 28px; animation: cr-modal-in 220ms ease-out; position: relative; }
  .cr-modal-summary { font-size: 14px; line-height: 1.75; color: #D1D5DB; font-style: italic;
    border-left: 3px solid #6366f1; padding-left: 16px; margin: 16px 0; }
  .cr-modal-read-btn { display: flex; align-items: center; gap: 8px; background: #6366f1; color: #fff;
    border: none; border-radius: 8px; padding: 10px 18px; font-size: 13px; font-weight: 600;
    cursor: pointer; transition: background 150ms ease; text-decoration: none; }
  .cr-modal-read-btn:hover { background: #4F46E5; }
  @keyframes cr-pulse { 0%,100% { opacity: 0.4; } 50% { opacity: 1; } }
  .cr-summary-loading { display: flex; align-items: center; gap: 8px; color: #6B7280; font-size: 13px; padding: 12px 0; }
  .cr-summary-loading-dot { width: 6px; height: 6px; border-radius: 50%; background: #6366f1; animation: cr-pulse 1.2s ease-in-out infinite; }
  .cr-summary-loading-dot:nth-child(2) { animation-delay: 0.2s; }
  .cr-summary-loading-dot:nth-child(3) { animation-delay: 0.4s; }
`;

// ─── Types ───────────────────────────────────────────────────────────────────

interface SearchResult {
  id: string;
  name: string;
  type: "car" | "insurance";
  sector: string;
  region: string | null;
  score: number | null;
  data_origin: string | null;
}

interface ComplaintItem {
  label: string;
  count: number;
  pct: number;
}

interface SentimentMonth {
  month: string;
  negative_pct: number;
  avg_rating: number | null;
}

interface RealQuote {
  text: string;
  rating: number | null;
  date: string | null;
  sentiment: string;
}

interface ScoringBreakdown {
  article_signal: number;
  sentiment_trend: number;
  market_presence: number;
  complaint_intensity: number;
}

interface MLArticlePoint {
  title: string;
  similarity: number;
  pub_date: string | null;
  category: string | null;
  days_old: number;
  recency_weight: number;
}

interface MLTrendPoint {
  period: string;
  avg_sentiment: number | null;
  review_count: number;
  neg_pct: number | null;
  regression_predicted: number | null;
  poly_predicted: number | null;
}

interface MLSectorPeer {
  name: string;
  value: number;
  is_current: boolean;
}

interface MLDimensions {
  entity_name: string;
  entity_type: string;
  total_score: number;
  article_score: number;
  article_max: number;
  article_percentile: number;
  article_count: number;
  top_articles: MLArticlePoint[];
  trend_score: number;
  trend_max: number;
  trend_slope: number;
  trend_r_squared: number;
  trend_direction: string;
  trend_percentile: number;
  trend_series: MLTrendPoint[];
  trend_method: string;
  mk_trend: string | null;
  mk_p_value: number | null;
  mk_significant: boolean;
  poly_acceleration: number;
  poly_concavity: string;
  trend_min_reviews: number;
  trend_months_filtered: number;
  trend_clean_r_squared: number;
  presence_score: number;
  presence_max: number;
  review_count: number;
  presence_percentile: number;
  sector_presence_peers: MLSectorPeer[];
  intensity_score: number;
  intensity_max: number;
  negative_pct: number;
  intensity_percentile: number;
  sector_avg_negative_pct: number;
  sector_intensity_peers: MLSectorPeer[];
}

interface CompanyNewsItem {
  id: string;
  title: string;
  source_url: string;
  publication_date: string | null;
  category: string | null;
  region: string | null;
  source_name: string | null;
}

interface ArticleSummaryData {
  article_id: string;
  title: string;
  summary: string;
  source_url: string;
  publication_date: string | null;
  source_name: string | null;
}

interface CompanyProfile {
  id: string;
  name: string;
  type: "car" | "insurance";
  sector: string;
  region: string | null;
  country: string | null;
  score: number | null;
  score_percentile: number | null;
  data_origin: string | null;
  cluster_id: number | null;
  cluster_label: string | null;
  cluster_color: string | null;
  erp_module_primary: string | null;
  erp_module_secondary: string | null;
  prospect_type: string;
  review_count: number;
  negative_pct: number;
  avg_rating: number | null;
  top_complaints: ComplaintItem[];
  sentiment_trend: SentimentMonth[];
  real_quotes: RealQuote[];
  why_now: string;
  scoring_breakdown: ScoringBreakdown | null;
  data_note: string | null;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function getScoreColor(score: number | null): string {
  if (score == null) return "#3B82F6";
  if (score > 80) return "#EF4444";
  if (score >= 65) return "#F59E0B";
  return "#3B82F6";
}

function getSentimentLabel(negPct: number): { label: string; color: string } {
  if (negPct > 65) return { label: "CRITICAL", color: "#EF4444" };
  if (negPct > 40) return { label: "DECLINING", color: "#F59E0B" };
  return { label: "STABLE", color: "#10B981" };
}

function formatMonth(m: string): string {
  const [y, mo] = m.split("-");
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return `${months[parseInt(mo, 10) - 1] || mo} ${y?.slice(2)}`;
}

function formatDate(d: string | null): string {
  if (!d) return "";
  const date = new Date(d);
  return date.toLocaleDateString("en-US", { month: "short", year: "numeric" });
}

function getComplaintSalesTip(label: string): string {
  const lower = label.toLowerCase();
  if (lower.includes("service") || lower.includes("customer")) return "Ask about their customer service workflow";
  if (lower.includes("billing") || lower.includes("pricing") || lower.includes("policy")) return "Ask about their invoicing and billing process";
  if (lower.includes("claim")) return "Ask about their claims processing system";
  if (lower.includes("wait") || lower.includes("response") || lower.includes("time")) return "Ask about their response time management";
  if (lower.includes("reliab") || lower.includes("quality")) return "Ask about their quality control systems";
  if (lower.includes("staff") || lower.includes("commun")) return "Ask about their team coordination tools";
  return "Explore their current operational workflow";
}

function generateOpeningLine(company: CompanyProfile): string {
  const topComplaint = company.top_complaints[0]?.label || "operational challenges";
  const sector = company.sector.toLowerCase();
  return `We noticed companies in the ${sector} sector are increasingly struggling with ${topComplaint.toLowerCase()} — is that something your team has been dealing with?`;
}

// ─── Skeleton ────────────────────────────────────────────────────────────────

function SkeletonBlock({ w, h, mb = 0 }: { w: string | number; h: number; mb?: number }) {
  return <div className="cr-skel" style={{ width: w, height: h, marginBottom: mb }} />;
}

function SectionSkeleton() {
  return (
    <div className="cr-card" style={{ marginBottom: 16 }}>
      <SkeletonBlock w={180} h={14} mb={12} />
      <SkeletonBlock w="80%" h={12} mb={8} />
      <SkeletonBlock w="60%" h={12} />
    </div>
  );
}

// ─── Component ───────────────────────────────────────────────────────────────

export default function CompanyRadar() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [selectedCompany, setSelectedCompany] = useState<{ type: string; id: string } | null>(null);
  const [showDropdown, setShowDropdown] = useState(false);
  const [articleModal, setArticleModal] = useState<{ item: CompanyNewsItem } | null>(null);
  const searchRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  // Inject styles
  useEffect(() => {
    const id = "cr-styles";
    if (!document.getElementById(id)) {
      const s = document.createElement("style");
      s.id = id;
      s.textContent = STYLES;
      document.head.appendChild(s);
    }
  }, []);

  // Auto-load from URL params
  useEffect(() => {
    const type = params.get("type");
    const id = params.get("id");
    if (type && id) {
      setSelectedCompany({ type, id });
    }
  }, [params]);

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // Debounced search
  const handleSearch = useCallback((value: string) => {
    setQuery(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      if (value.trim().length >= 2) setShowDropdown(true);
      else setShowDropdown(false);
    }, 300);
  }, []);

  // Search query
  const { data: searchResults, isLoading: searchLoading } = useQuery<SearchResult[]>({
    queryKey: ["company-search", query],
    queryFn: () => fetch(`${API}/api/search/companies?q=${encodeURIComponent(query)}`).then(r => r.json()),
    enabled: query.trim().length >= 2,
    staleTime: 30000,
  });

  // Company news query
  const { data: companyNews } = useQuery<CompanyNewsItem[]>({
    queryKey: ["company-news", selectedCompany?.type, selectedCompany?.id],
    queryFn: () =>
      fetch(`${API}/api/company/${selectedCompany!.type}/${selectedCompany!.id}/news?limit=5`)
        .then(r => r.json()),
    enabled: !!selectedCompany,
    staleTime: 30000,
  });

  // Article summary query — fires only when a news item is clicked
  const { data: articleSummary, isLoading: summaryLoading, error: summaryError } = useQuery<ArticleSummaryData>({
    queryKey: ["article-summary", articleModal?.item.id],
    queryFn: () =>
      fetch(`${API}/api/article/${articleModal!.item.id}/summary`).then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      }),
    enabled: !!articleModal,
    staleTime: 0, // always re-fetch — format changes frequently during dev
  });

  // ML dimensions query
  const { data: mlDims } = useQuery<MLDimensions>({
    queryKey: ["ml-dimensions", selectedCompany?.type, selectedCompany?.id],
    queryFn: () =>
      fetch(`${API}/api/company/${selectedCompany!.type}/${selectedCompany!.id}/ml-dimensions`)
        .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); }),
    enabled: !!selectedCompany,
    staleTime: 30000,
  });

  // Company profile query
  const { data: profile, isLoading: profileLoading, error: profileError } = useQuery<CompanyProfile>({
    queryKey: ["company-profile", selectedCompany?.type, selectedCompany?.id],
    queryFn: () => {
      const endpoint = selectedCompany!.type === "car"
        ? `/api/company/car/${selectedCompany!.id}`
        : `/api/company/insurance/${selectedCompany!.id}`;
      return fetch(`${API}${endpoint}`).then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      });
    },
    enabled: !!selectedCompany,
    staleTime: 30000,
  });

  const selectCompany = (result: SearchResult) => {
    setSelectedCompany({ type: result.type, id: result.id });
    setQuery(result.name);
    setShowDropdown(false);
  };

  const sentimentInfo = profile ? getSentimentLabel(profile.negative_pct) : null;
  const scoreColor = profile ? getScoreColor(profile.score) : "#3B82F6";

  return (
    <div style={{ padding: "0 32px 48px", maxWidth: 1200, margin: "0 auto" }}>

      {/* ═══ A. SEARCH BAR HERO ═══ */}
      <div
        ref={searchRef}
        style={{
          position: "sticky", top: 0, zIndex: 40,
          backgroundColor: "#0A0F1E", paddingTop: 28, paddingBottom: 16,
        }}
      >
        <div style={{ position: "relative" }}>
          <Search
            size={18}
            style={{ position: "absolute", left: 16, top: "50%", transform: "translateY(-50%)", color: "#6B7280", pointerEvents: "none" }}
          />
          <input
            className="cr-search-input"
            type="text"
            placeholder="Search any company — Hyundai, Budget Direct, STAR Assurances..."
            value={query}
            onChange={e => handleSearch(e.target.value)}
            onFocus={() => { if (query.trim().length >= 2) setShowDropdown(true); }}
          />

          {/* Dropdown */}
          {showDropdown && (
            <div
              style={{
                position: "absolute", top: "calc(100% + 4px)", left: 0, right: 0,
                backgroundColor: "#111827", border: "1px solid #1F2937", borderRadius: 10,
                boxShadow: "0 4px 12px rgba(0,0,0,0.3)", maxHeight: 320, overflowY: "auto", zIndex: 50,
              }}
            >
              {searchLoading ? (
                <div style={{ padding: 16 }}>
                  <SkeletonBlock w="70%" h={14} mb={10} />
                  <SkeletonBlock w="60%" h={14} mb={10} />
                  <SkeletonBlock w="50%" h={14} />
                </div>
              ) : searchResults && searchResults.length > 0 ? (
                searchResults.map(r => (
                  <div key={r.id} className="cr-dropdown-item" onClick={() => selectCompany(r)}>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 14, fontWeight: 500, color: "#F9FAFB" }}>{r.name}</div>
                      <div style={{ display: "flex", gap: 6, marginTop: 4 }}>
                        <span style={{
                          fontSize: 10, fontWeight: 500, padding: "1px 6px", borderRadius: 9999,
                          backgroundColor: r.type === "insurance" ? "#1e3a5f" : "#1c3320",
                          color: r.type === "insurance" ? "#60a5fa" : "#4ade80",
                        }}>
                          {r.sector}
                        </span>
                        {r.region && (
                          <span style={{ fontSize: 10, padding: "1px 6px", borderRadius: 9999, backgroundColor: "#1f2937", color: "#9ca3af" }}>
                            {r.region}
                          </span>
                        )}
                      </div>
                    </div>
                    {r.score != null && (
                      <span style={{
                        fontFamily: "'JetBrains Mono', monospace", fontSize: 14, fontWeight: 700,
                        color: getScoreColor(r.score),
                      }}>
                        {r.score.toFixed(0)}
                      </span>
                    )}
                  </div>
                ))
              ) : query.trim().length >= 2 ? (
                <div style={{ padding: 16, fontSize: 13, color: "#6B7280" }}>No companies found for "{query}"</div>
              ) : null}
            </div>
          )}
        </div>

        {!selectedCompany && (
          <div style={{ fontSize: 12, color: "#6B7280", marginTop: 8, textAlign: "center" }}>
            Search across 68 active signals...
          </div>
        )}
      </div>

      {/* ═══ PROFILE CONTENT ═══ */}
      {profileLoading && selectedCompany && (
        <div style={{ marginTop: 16 }}>
          <SectionSkeleton />
          <SectionSkeleton />
          <SectionSkeleton />
          <SectionSkeleton />
        </div>
      )}

      {profileError && (
        <div className="cr-card" style={{ marginTop: 16, textAlign: "center", padding: 40 }}>
          <AlertCircle size={32} style={{ color: "#EF4444", margin: "0 auto 12px" }} />
          <div style={{ fontSize: 16, fontWeight: 600, color: "#F9FAFB", marginBottom: 8 }}>Company Not Found</div>
          <div style={{ fontSize: 13, color: "#6B7280", marginBottom: 16 }}>Could not load this company profile.</div>
          <button
            onClick={() => { setSelectedCompany(null); setQuery(""); }}
            style={{
              background: "transparent", border: "1px solid #374151", color: "#9CA3AF",
              padding: "7px 14px", borderRadius: 6, fontSize: 12, fontWeight: 500, cursor: "pointer",
              fontFamily: "'DM Sans', sans-serif",
            }}
          >
            Search another company
          </button>
        </div>
      )}

      {profile && !profileLoading && (
        <div>
          {/* ═══ B. COMPANY HEADER ═══ */}
          <div className="cr-section" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginTop: 8, marginBottom: 24, animationDelay: "0ms" }}>
            <div>
              <h1 style={{ fontFamily: "'Syne', sans-serif", fontWeight: 800, fontSize: 32, color: "#F9FAFB", margin: 0, lineHeight: 1.2 }}>
                {profile.name}
              </h1>
              {/* Badges */}
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12 }}>
                <span style={{ fontSize: 10, fontWeight: 500, padding: "2px 8px", borderRadius: 9999, backgroundColor: "#0c1f3d", color: "#3B82F6" }}>
                  {profile.sector}
                </span>
                {profile.region && (
                  <span style={{ fontSize: 10, fontWeight: 500, padding: "2px 8px", borderRadius: 9999, backgroundColor: "#1f2937", color: "#9ca3af" }}>
                    {profile.region}
                  </span>
                )}
                <span style={{
                  fontSize: 9, fontWeight: 600, padding: "2px 8px", borderRadius: 9999,
                  letterSpacing: "0.1em", textTransform: "uppercase",
                  backgroundColor: profile.data_origin === "analyst" ? "#2e1065" : "#052e16",
                  color: profile.data_origin === "analyst" ? "#8B5CF6" : "#10B981",
                }}>
                  {profile.data_origin === "analyst" ? "ANALYST SIGNAL" : "VERIFIED DATA"}
                </span>
                {/* Prospect type badge */}
                <span style={{
                  fontSize: 9, fontWeight: 600, padding: "2px 8px", borderRadius: 9999,
                  letterSpacing: "0.1em", textTransform: "uppercase",
                  backgroundColor: profile.prospect_type === "NO_ERP" ? "#450a0a"
                    : profile.prospect_type === "ERP_FAILING" ? "#451a03" : "#431407",
                  color: profile.prospect_type === "NO_ERP" ? "#EF4444"
                    : profile.prospect_type === "ERP_FAILING" ? "#F59E0B" : "#F97316",
                }}>
                  {profile.prospect_type === "NO_ERP" ? "NO ERP DETECTED"
                    : profile.prospect_type === "ERP_FAILING" ? "ERP UNDERPERFORMING"
                    : "OPERATIONAL GAPS"}
                </span>
              </div>
              {/* Score text */}
              {profile.score != null && (
                <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 13, color: "#9CA3AF", marginTop: 12 }}>
                  Score: {profile.score.toFixed(0)} · Top {Math.max(1, 100 - (profile.score_percentile ?? 50))}% of market
                </div>
              )}
            </div>

            {/* Right: score circle + cluster */}
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", flexShrink: 0 }}>
              {profile.score != null && (
                <div style={{
                  width: 80, height: 80, borderRadius: "50%",
                  border: `3px solid ${scoreColor}`,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  backgroundColor: "rgba(0,0,0,0.2)",
                }}>
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 28, fontWeight: 700, color: scoreColor }}>
                    {profile.score.toFixed(0)}
                  </span>
                </div>
              )}
              {profile.cluster_label && (
                <span style={{
                  marginTop: 8, fontSize: 10, fontWeight: 500, padding: "2px 8px", borderRadius: 9999,
                  backgroundColor: `${profile.cluster_color || "#6B7280"}20`,
                  color: profile.cluster_color || "#6B7280",
                  border: `1px solid ${profile.cluster_color || "#6B7280"}40`,
                  maxWidth: 140, textAlign: "center", lineHeight: 1.3,
                }}>
                  {profile.cluster_label}
                </span>
              )}
            </div>
          </div>

          {/* ═══ C. WHY NOW BANNER ═══ */}
          <div
            className="cr-section"
            style={{
              animationDelay: "50ms",
              padding: "16px 20px",
              borderRadius: 10,
              marginBottom: 20,
              backgroundColor: (profile.score ?? 0) > 80 ? "#450a0a" : "#451a03",
              border: `1px solid ${(profile.score ?? 0) > 80 ? "#991b1b" : "#92400e"}`,
              display: "flex", alignItems: "flex-start", gap: 12,
            }}
          >
            <AlertTriangle size={20} style={{ color: (profile.score ?? 0) > 80 ? "#EF4444" : "#F59E0B", flexShrink: 0, marginTop: 2 }} />
            <div>
              <div style={{
                fontSize: 10, fontWeight: 600, letterSpacing: "0.15em", textTransform: "uppercase",
                color: (profile.score ?? 0) > 80 ? "#EF4444" : "#F59E0B",
                marginBottom: 6,
              }}>
                WHY TEAMWILL SHOULD CALL NOW
              </div>
              <div style={{ fontSize: 13, fontWeight: 500, color: "#F9FAFB", lineHeight: 1.5 }}>
                {profile.why_now}
              </div>
            </div>
          </div>

          {/* ═══ D. PROSPECT DIAGNOSIS BOX ═══ */}
          <div className="cr-section cr-card" style={{ animationDelay: "100ms", marginBottom: 20 }}>
            <ProspectDiagnosis type={profile.prospect_type} />
          </div>

          {/* ═══ E. STATS + TREND CHART ═══ */}
          <div className="cr-section" style={{ animationDelay: "150ms", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 20 }}>
            {/* Left: Stats */}
            <div className="cr-card">
              <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.1em", textTransform: "uppercase", color: "#6B7280", marginBottom: 16 }}>
                What Customers Are Experiencing
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                <StatRow label="Total Reviews" value={profile.review_count.toLocaleString()} mono />
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                    <span style={{ fontSize: 12, color: "#9CA3AF" }}>Negative %</span>
                    <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 13, color: "#F9FAFB" }}>{profile.negative_pct.toFixed(1)}%</span>
                  </div>
                  <div style={{ height: 4, backgroundColor: "#1F2937", borderRadius: 2, overflow: "hidden" }}>
                    <div style={{ height: "100%", width: `${Math.min(profile.negative_pct, 100)}%`, backgroundColor: "#EF4444", borderRadius: 2 }} />
                  </div>
                </div>
                <div>
                  <span style={{ fontSize: 12, color: "#9CA3AF", marginRight: 8 }}>Avg Rating</span>
                  <StarsDisplay rating={profile.avg_rating} />
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 13, color: "#F9FAFB", marginLeft: 8 }}>
                    {profile.avg_rating != null ? profile.avg_rating.toFixed(1) : "N/A"}
                  </span>
                </div>
                {sentimentInfo && (
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontSize: 12, color: "#9CA3AF" }}>Sentiment</span>
                    <span style={{
                      fontSize: 10, fontWeight: 600, padding: "2px 8px", borderRadius: 9999,
                      backgroundColor: `${sentimentInfo.color}20`,
                      color: sentimentInfo.color,
                    }}>
                      {sentimentInfo.label}
                    </span>
                  </div>
                )}
                {profile.data_note && (
                  <div style={{ fontSize: 11, color: "#6B7280", fontStyle: "italic", lineHeight: 1.5, marginTop: 4 }}>
                    {profile.data_note}
                  </div>
                )}
              </div>
            </div>

            {/* Right: Trend chart */}
            <div className="cr-card">
              <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.1em", textTransform: "uppercase", color: "#6B7280", marginBottom: 4 }}>
                Complaint Rate Trend
              </div>
              {profile.sentiment_trend.length > 1 ? (
                <>
                  {profile.negative_pct > 40 && (
                    <div style={{ fontSize: 10, color: "#EF4444", marginBottom: 8 }}>
                      ▼ Declining
                    </div>
                  )}
                  <ResponsiveContainer width="100%" height={180}>
                    <AreaChart data={[...profile.sentiment_trend].reverse()} margin={{ top: 8, right: 8, bottom: 0, left: -20 }}>
                      <defs>
                        <linearGradient id="negFill" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#EF4444" stopOpacity={0.2} />
                          <stop offset="100%" stopColor="#EF4444" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <XAxis dataKey="month" tick={{ fontSize: 11, fill: "#6B7280", fontFamily: "DM Sans" }} tickFormatter={formatMonth} axisLine={false} tickLine={false} />
                      <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: "#6B7280", fontFamily: "JetBrains Mono" }} axisLine={false} tickLine={false} />
                      <Tooltip
                        contentStyle={{ backgroundColor: "#111827", border: "1px solid #374151", borderRadius: 8, fontSize: 13 }}
                        labelStyle={{ color: "#9CA3AF" }}
                        itemStyle={{ color: "#EF4444" }}
                        formatter={(v: number) => [`${v.toFixed(1)}%`, "Negative"]}
                        labelFormatter={formatMonth}
                      />
                      <Area type="monotone" dataKey="negative_pct" stroke="#EF4444" strokeWidth={2} fill="url(#negFill)" />
                    </AreaChart>
                  </ResponsiveContainer>
                </>
              ) : (
                <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 180, color: "#6B7280", fontSize: 12, fontStyle: "italic" }}>
                  Insufficient data for trend analysis
                </div>
              )}
            </div>
          </div>

          {/* ═══ F. TOP COMPLAINTS BAR CHART ═══ */}
          <div className="cr-section cr-card" style={{ animationDelay: "200ms", marginBottom: 20 }}>
            <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.1em", textTransform: "uppercase", color: "#6B7280", marginBottom: 4 }}>
              What Customers Are Complaining About
            </div>
            <div style={{ fontSize: 11, color: "#6B7280", marginBottom: 16 }}>
              These are the pain points to open your sales conversation with
            </div>
            {profile.top_complaints.length > 0 ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                {profile.top_complaints.slice(0, 5).map((c, i) => (
                  <div key={i}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                      <span style={{ fontSize: 13, fontWeight: 500, color: "#F9FAFB" }}>{c.label}</span>
                      <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 13, color: "#F9FAFB" }}>{c.pct.toFixed(1)}%</span>
                    </div>
                    <div style={{ height: 6, backgroundColor: "#1F2937", borderRadius: 3, overflow: "hidden" }}>
                      <div style={{ height: "100%", width: `${Math.min(c.pct, 100)}%`, backgroundColor: "#EF4444", borderRadius: 3 }} />
                    </div>
                    <div style={{ fontSize: 11, color: "#6B7280", marginTop: 4, fontStyle: "italic" }}>
                      → {getComplaintSalesTip(c.label)}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ fontSize: 12, color: "#6B7280", fontStyle: "italic" }}>
                Complaint breakdown unavailable for this company
              </div>
            )}
          </div>

          {/* ═══ G. WHAT TO PITCH ═══ */}
          <div className="cr-section" style={{ animationDelay: "250ms", marginBottom: 20 }}>
            <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.1em", textTransform: "uppercase", color: "#6B7280", marginBottom: 12 }}>
              Your Sales Pitch for This Company
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              {/* Primary */}
              <div style={{
                background: "#111827", border: "1px solid #6366F1", borderRadius: 10, padding: 20,
              }}>
                <div style={{ fontSize: 9, fontWeight: 600, letterSpacing: "0.15em", textTransform: "uppercase", color: "#6366F1", marginBottom: 8 }}>
                  PRIMARY RECOMMENDATION
                </div>
                <div style={{ fontFamily: "'Syne', sans-serif", fontWeight: 700, fontSize: 18, color: "#F9FAFB", marginBottom: 8 }}>
                  {profile.erp_module_primary || "ERP Suite"}
                </div>
                <div style={{ fontSize: 12, color: "#9CA3AF", lineHeight: 1.5, marginBottom: 10 }}>
                  {profile.prospect_type === "NO_ERP"
                    ? "Full ERP implementation to replace manual processes causing service failures."
                    : profile.prospect_type === "ERP_FAILING"
                    ? "ERP consulting, upgrade, or migration to address persistent operational gaps."
                    : "Integration suite to unify fragmented service domains."}
                </div>
                <span style={{ fontSize: 10, fontWeight: 600, padding: "2px 8px", borderRadius: 9999, backgroundColor: "#052e16", color: "#10B981" }}>
                  Confidence: HIGH
                </span>
              </div>
              {/* Secondary */}
              <div style={{
                background: "#111827", border: "1px solid #1F2937", borderRadius: 10, padding: 20,
              }}>
                <div style={{ fontSize: 9, fontWeight: 600, letterSpacing: "0.15em", textTransform: "uppercase", color: "#6B7280", marginBottom: 8 }}>
                  SECONDARY OPPORTUNITY
                </div>
                <div style={{ fontFamily: "'Syne', sans-serif", fontWeight: 700, fontSize: 16, color: "#F9FAFB", marginBottom: 8 }}>
                  {profile.erp_module_secondary || "Analytics Suite"}
                </div>
                <div style={{ fontSize: 12, color: "#9CA3AF", lineHeight: 1.5 }}>
                  Complement the primary solution with advanced reporting and customer analytics.
                </div>
              </div>
            </div>
            {/* Opening line */}
            <div style={{ marginTop: 12, padding: "12px 16px", backgroundColor: "#111827", border: "1px solid #1F2937", borderRadius: 10 }}>
              <div style={{ fontSize: 10, fontWeight: 500, color: "#6B7280", marginBottom: 6 }}>Suggested opening line:</div>
              <div style={{ fontSize: 13, color: "#9CA3AF", fontStyle: "italic", lineHeight: 1.5 }}>
                "{generateOpeningLine(profile)}"
              </div>
            </div>
          </div>

          {/* ═══ H. REAL CUSTOMER VOICES ═══ */}
          <div className="cr-section" style={{ animationDelay: "300ms", marginBottom: 20 }}>
            <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.1em", textTransform: "uppercase", color: "#6B7280", marginBottom: 4 }}>
              What Their Customers Are Actually Saying
            </div>
            <div style={{ fontSize: 11, color: "#6B7280", marginBottom: 16 }}>
              Use these insights to demonstrate market knowledge in your call
            </div>
            {profile.real_quotes.length > 0 ? (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
                {profile.real_quotes.map((q, i) => (
                  <div key={i} className="cr-card" style={{ position: "relative" }}>
                    <Quote size={14} style={{ color: "#374151", marginBottom: 8 }} />
                    <div style={{ fontSize: 12, color: "#D1D5DB", fontStyle: "italic", lineHeight: 1.6, marginBottom: 12 }}>
                      "{q.text.length > 200 ? q.text.slice(0, 200) + "..." : q.text}"
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <StarsDisplay rating={q.rating} size={12} />
                      {q.date && (
                        <span style={{ fontSize: 11, color: "#6B7280" }}>{formatDate(q.date)}</span>
                      )}
                      <span style={{
                        fontSize: 9, fontWeight: 600, padding: "1px 6px", borderRadius: 9999,
                        backgroundColor: "#450a0a", color: "#EF4444",
                      }}>
                        NEGATIVE
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="cr-card" style={{ textAlign: "center", padding: 24 }}>
                <div style={{ fontSize: 12, color: "#6B7280", fontStyle: "italic" }}>
                  No Trustpilot reviews available for this company. Intelligence is based on market analysis.
                </div>
              </div>
            )}
          </div>

          {/* ═══ I. ACTION BUTTONS ═══ */}
          {/* ── Recent Industry News ─────────────────────────────────────── */}
          {companyNews && companyNews.length > 0 && (
            <div className="cr-section" style={{ animationDelay: "320ms", marginBottom: 28 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
                <div style={{
                  width: 28, height: 28, borderRadius: 7, background: "rgba(99,102,241,0.15)",
                  display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                }}>
                  <Layers size={14} style={{ color: "#6366f1" }} />
                </div>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: "#F9FAFB" }}>Recent Industry News</div>
                  <div style={{ fontSize: 11, color: "#6B7280" }}>Use as conversation hooks before your call</div>
                </div>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {companyNews.map((item) => {
                  const regionColor = item.region === "TN" ? "#FBBF24" : item.region === "EU" ? "#818CF8" : "#6B7280";
                  const regionBg = item.region === "TN" ? "rgba(251,191,36,0.1)" : item.region === "EU" ? "rgba(99,102,241,0.1)" : "rgba(107,114,128,0.1)";
                  const catColor = item.category === "insurance" ? "#6366f1" : item.category === "EV" ? "#10B981" : "#F59E0B";
                  return (
                    <div
                      key={item.id}
                      className="cr-card cr-news-item"
                      style={{ padding: "10px 14px", display: "flex", alignItems: "flex-start", gap: 10 }}
                      onClick={() => setArticleModal({ item })}
                    >
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 12, fontWeight: 600, color: "#E5E7EB", lineHeight: 1.4, marginBottom: 4 }}>
                          {item.title}
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                          {item.category && (
                            <span style={{
                              fontSize: 10, fontWeight: 700, padding: "1px 6px", borderRadius: 20,
                              background: `${catColor}18`, color: catColor, textTransform: "uppercase",
                            }}>{item.category}</span>
                          )}
                          {item.region && (
                            <span style={{
                              fontSize: 10, fontWeight: 600, padding: "1px 6px", borderRadius: 20,
                              background: regionBg, color: regionColor,
                            }}>{item.region}</span>
                          )}
                          {item.source_name && (
                            <span style={{ fontSize: 10, color: "#4B5563" }}>{item.source_name}</span>
                          )}
                          {item.publication_date && (
                            <span style={{ fontSize: 10, color: "#4B5563", marginLeft: "auto" }}>
                              {new Date(item.publication_date).toLocaleDateString("en-GB", { day: "numeric", month: "short" })}
                            </span>
                          )}
                        </div>
                      </div>
                      <BookOpen size={12} style={{ color: "#6366f1", flexShrink: 0, marginTop: 2 }} />
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* ═══ J. ML SCORING DIMENSIONS ═══ */}
          {mlDims && <MLDimensionsPanel ml={mlDims} />}

          <div className="cr-section" style={{ animationDelay: "350ms", display: "flex", gap: 12, justifyContent: "center", paddingTop: 8, paddingBottom: 32 }}>
            <button
              onClick={() => {
                const context = [
                  profile.name,
                  profile.sector,
                  profile.top_complaints[0]?.label || "",
                  profile.erp_module_primary || "",
                ].filter(Boolean).join(",");
                navigate(`/analyst?context=${encodeURIComponent(context)}`);
              }}
              style={{
                background: "#8B5CF6", border: "none", color: "#fff",
                padding: "10px 20px", borderRadius: 8, fontSize: 13, fontWeight: 600,
                cursor: "pointer", fontFamily: "'DM Sans', sans-serif",
                display: "flex", alignItems: "center", gap: 8,
                transition: "background-color 150ms ease",
              }}
              onMouseEnter={e => { e.currentTarget.style.backgroundColor = "#7C3AED"; }}
              onMouseLeave={e => { e.currentTarget.style.backgroundColor = "#8B5CF6"; }}
            >
              <Sparkles size={16} />
              Ask AI to Help Me Prepare This Call
              <ArrowRight size={14} />
            </button>
            <a
              href={selectedCompany ? `${API}/api/export/company/${selectedCompany.type}/${selectedCompany.id}` : "#"}
              download
              style={{
                background: "transparent", border: "1px solid #374151", color: "#D1D5DB",
                padding: "10px 20px", borderRadius: 8, fontSize: 13, fontWeight: 500,
                cursor: "pointer", fontFamily: "'DM Sans', sans-serif",
                display: "flex", alignItems: "center", gap: 8,
                textDecoration: "none", transition: "border-color 150ms ease, color 150ms ease",
              }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = "#6366f1"; e.currentTarget.style.color = "#fff"; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = "#374151"; e.currentTarget.style.color = "#D1D5DB"; }}
            >
              Export PDF Brief
            </a>
          </div>
        </div>
      )}

      {/* Empty state — no company selected */}
      {!selectedCompany && !profileLoading && (
        <div style={{ textAlign: "center", marginTop: 80 }}>
          <Search size={40} style={{ color: "#374151", margin: "0 auto 16px" }} />
          <div style={{ fontFamily: "'Syne', sans-serif", fontWeight: 700, fontSize: 24, color: "#F9FAFB", marginBottom: 8 }}>
            Company Radar
          </div>
          <div style={{ fontSize: 14, color: "#6B7280", maxWidth: 400, margin: "0 auto", lineHeight: 1.6 }}>
            Search any company to get a complete pre-call sales intelligence dossier.
            Everything you need before picking up the phone.
          </div>
        </div>
      )}

      {/* ── Article Summary Modal ─────────────────────────────────────────── */}
      {articleModal && (
        <div
          className="cr-modal-overlay"
          onClick={(e) => { if (e.target === e.currentTarget) setArticleModal(null); }}
        >
          <div className="cr-modal">
            {/* Header */}
            <div style={{ display: "flex", alignItems: "flex-start", gap: 12, marginBottom: 16 }}>
              <div style={{
                width: 32, height: 32, borderRadius: 8, background: "rgba(99,102,241,0.15)",
                display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, marginTop: 2,
              }}>
                <BookOpen size={15} style={{ color: "#6366f1" }} />
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: "#6366f1", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>
                  Intelligence Brief
                </div>
                <div style={{ fontSize: 14, fontWeight: 700, color: "#F9FAFB", lineHeight: 1.4 }}>
                  {articleModal.item.title}
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6, flexWrap: "wrap" }}>
                  {articleModal.item.source_name && (
                    <span style={{ fontSize: 11, color: "#6B7280" }}>{articleModal.item.source_name}</span>
                  )}
                  {articleModal.item.publication_date && (
                    <span style={{ fontSize: 11, color: "#4B5563" }}>
                      · {new Date(articleModal.item.publication_date).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })}
                    </span>
                  )}
                </div>
              </div>
              <button
                onClick={() => setArticleModal(null)}
                style={{
                  background: "none", border: "none", cursor: "pointer", color: "#6B7280",
                  padding: 4, borderRadius: 6, display: "flex", alignItems: "center",
                  transition: "color 150ms ease",
                }}
                onMouseEnter={e => { e.currentTarget.style.color = "#F9FAFB"; }}
                onMouseLeave={e => { e.currentTarget.style.color = "#6B7280"; }}
              >
                <X size={16} />
              </button>
            </div>

            {/* Divider */}
            <div style={{ height: 1, background: "#1F2937", marginBottom: 16 }} />

            {/* Summary */}
            {summaryLoading && (
              <div className="cr-summary-loading">
                <div className="cr-summary-loading-dot" />
                <div className="cr-summary-loading-dot" />
                <div className="cr-summary-loading-dot" />
                <span>Generating intelligence brief…</span>
              </div>
            )}
            {summaryError && (
              <div style={{ fontSize: 13, color: "#EF4444", padding: "8px 0" }}>
                Could not generate summary. Check that GROQ_API_KEY is configured.
              </div>
            )}
            {articleSummary && !summaryLoading && (() => {
              // ── Helpers ──────────────────────────────────────────────────
              // Render inline **bold** tokens
              const renderBold = (text: string, baseKey: number) => {
                const parts = text.split(/(\*\*[^*]+\*\*)/g);
                return (
                  <span key={baseKey}>
                    {parts.map((p, i) =>
                      p.startsWith("**") && p.endsWith("**")
                        ? <strong key={i} style={{ color: "#F9FAFB", fontWeight: 700, fontStyle: "normal" }}>{p.slice(2, -2)}</strong>
                        : <span key={i}>{p}</span>
                    )}
                  </span>
                );
              };

              // Extract leading emoji from a string (handles multi-codepoint emoji)
              const emojiRx = /^(\p{Emoji_Presentation}|\p{Emoji}\uFE0F|\p{Emoji}\u20E3|[\u{1F000}-\u{1FFFF}])/u;
              const splitEmoji = (line: string): [string, string] => {
                const m = line.match(emojiRx);
                if (m) return [m[0], line.slice(m[0].length).replace(/^[:\s]+/, "").trim()];
                return ["", line.trim()];
              };

              // ── Parse ────────────────────────────────────────────────────
              const raw = articleSummary.summary.trim();

              // Robust separator: tolerate ---  /  \n---  /  \n---\n  /  ---\n
              const sepMatch = raw.match(/\n?-{3,}\n?/);
              const hook = sepMatch ? raw.slice(0, sepMatch.index!).trim() : raw;
              const bulletBlock = sepMatch
                ? raw.slice(sepMatch.index! + sepMatch[0].length).trim()
                : "";

              // Keep only non-empty lines from the bullet block
              const bulletLines = bulletBlock
                .split("\n")
                .map(l => l.trim())
                .filter(l => l.length > 0 && l !== "---");

              // ── Render ───────────────────────────────────────────────────
              return (
                <div style={{ marginTop: 4 }}>
                  {/* ── HOOK — no label, just visual weight ── */}
                  <div style={{
                    background: "linear-gradient(135deg, rgba(99,102,241,0.1) 0%, rgba(139,92,246,0.06) 100%)",
                    borderLeft: "3px solid #6366f1",
                    borderRadius: "0 8px 8px 0",
                    padding: "12px 16px",
                    marginBottom: 14,
                  }}>
                    <div style={{ fontSize: 13.5, fontWeight: 600, color: "#E5E7EB", lineHeight: 1.6, fontStyle: "italic" }}>
                      {renderBold(hook, 0)}
                    </div>
                  </div>

                  {/* ── BULLET POINTS ── */}
                  {bulletLines.length > 0 && (
                    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                      {bulletLines.map((line, i) => {
                        const [emoji, body] = splitEmoji(line);
                        return (
                          <div key={i} style={{
                            display: "flex", alignItems: "flex-start", gap: 10,
                            background: "#111827", border: "1px solid #1F2937",
                            borderRadius: 8, padding: "9px 13px",
                          }}>
                            {emoji && (
                              <span style={{ fontSize: 16, lineHeight: 1, flexShrink: 0, marginTop: 2 }}>
                                {emoji}
                              </span>
                            )}
                            <div style={{ fontSize: 12.5, color: "#D1D5DB", lineHeight: 1.65 }}>
                              {renderBold(body, i + 1)}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })()}

            {/* CTA */}
            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 20 }}>
              <a
                href={articleModal.item.source_url}
                target="_blank"
                rel="noreferrer"
                className="cr-modal-read-btn"
              >
                <ExternalLink size={14} />
                Read full article
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Sub-components ──────────────────────────────────────────────────────────

function ProspectDiagnosis({ type }: { type: string }) {
  if (type === "NO_ERP") {
    return (
      <div style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
        <AlertCircle size={24} style={{ color: "#EF4444", flexShrink: 0, marginTop: 2 }} />
        <div>
          <div style={{ fontFamily: "'Syne', sans-serif", fontWeight: 700, fontSize: 16, color: "#F9FAFB", marginBottom: 6 }}>
            No ERP System Detected
          </div>
          <div style={{ fontSize: 13, color: "#9CA3AF", lineHeight: 1.6 }}>
            Complaint patterns suggest this company is operating without enterprise resource planning.
            Manual processes are causing service failures.
            TEAMWILL opportunity: full ERP implementation.
          </div>
        </div>
      </div>
    );
  }
  if (type === "ERP_FAILING") {
    return (
      <div style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
        <TrendingDown size={24} style={{ color: "#F59E0B", flexShrink: 0, marginTop: 2 }} />
        <div>
          <div style={{ fontFamily: "'Syne', sans-serif", fontWeight: 700, fontSize: 16, color: "#F9FAFB", marginBottom: 6 }}>
            ERP System Underperforming
          </div>
          <div style={{ fontSize: 13, color: "#9CA3AF", lineHeight: 1.6 }}>
            This company likely has an ERP solution in place but it is not solving their operational problems.
            High complaint rates persist despite scale.
            TEAMWILL opportunity: consulting, upgrade, or migration.
          </div>
        </div>
      </div>
    );
  }
  return (
    <div style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
      <Layers size={24} style={{ color: "#F97316", flexShrink: 0, marginTop: 2 }} />
      <div>
        <div style={{ fontFamily: "'Syne', sans-serif", fontWeight: 700, fontSize: 16, color: "#F9FAFB", marginBottom: 6 }}>
          Operational Fragmentation Detected
        </div>
        <div style={{ fontSize: 13, color: "#9CA3AF", lineHeight: 1.6 }}>
          Multiple service domains showing simultaneous failures — billing, response time, and process consistency.
          Classic symptom of a company that has outgrown its systems.
          TEAMWILL opportunity: integration suite.
        </div>
      </div>
    </div>
  );
}

function StarsDisplay({ rating, size = 14 }: { rating: number | null; size?: number }) {
  const filled = rating != null ? Math.round(rating) : 0;
  return (
    <span style={{ display: "inline-flex", gap: 1 }}>
      {[1, 2, 3, 4, 5].map(i => (
        <Star
          key={i}
          size={size}
          fill={i <= filled ? "#F59E0B" : "transparent"}
          style={{ color: i <= filled ? "#F59E0B" : "#374151" }}
        />
      ))}
    </span>
  );
}

// ─── ML Dimensions Panel ─────────────────────────────────────────────────────

const DIRECTION_COLOR: Record<string, string> = {
  declining_fast: "#EF4444",
  declining: "#F59E0B",
  stable: "#6B7280",
  improving: "#10B981",
};

function DimHeader({ title, score, max, percentile, color }: { title: string; score: number; max: number; percentile: number; color: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
      <div>
        <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.12em", textTransform: "uppercase", color: "#6B7280" }}>{title}</div>
        <div style={{ fontSize: 11, color: "#4B5563", marginTop: 2 }}>{percentile.toFixed(0)}th percentile among sector peers</div>
      </div>
      <div style={{ textAlign: "right" }}>
        <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 22, fontWeight: 700, color }}>{score.toFixed(1)}</span>
        <span style={{ fontSize: 12, color: "#4B5563" }}>/{max}</span>
      </div>
    </div>
  );
}

function MLDimensionsPanel({ ml }: { ml: MLDimensions }) {
  const trendColor = DIRECTION_COLOR[ml.trend_direction] ?? "#6B7280";

  // Article scatter data: x=days_old, y=similarity, z=recency_weight
  const articleScatter = ml.top_articles.map(a => ({
    x: a.days_old,
    y: parseFloat(a.similarity.toFixed(3)),
    z: Math.round(a.recency_weight * 100),
    label: a.title.slice(0, 50),
    cat: a.category ?? "",
  }));

  // Peers sorted descending for bar charts (max 12)
  const presencePeers = [...ml.sector_presence_peers].reverse();
  const intensityPeers = [...ml.sector_intensity_peers].reverse();

  return (
    <div className="cr-section" style={{ animationDelay: "340ms", marginBottom: 24 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 20 }}>
        <div style={{ width: 28, height: 28, borderRadius: 7, background: "rgba(99,102,241,0.15)", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <span style={{ fontSize: 14 }}>🧠</span>
        </div>
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, color: "#F9FAFB" }}>ML Scoring Breakdown</div>
          <div style={{ fontSize: 11, color: "#6B7280" }}>
            Score {ml.total_score.toFixed(1)}/100 — 4 data-driven dimensions, all sector-relative
          </div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>

        {/* ── Dim 1: Article Signal ─────────────────────────────────── */}
        <div className="cr-card">
          <DimHeader title="Article Signal" score={ml.article_score} max={ml.article_max} percentile={ml.article_percentile} color="#6366F1" />
          <div style={{ fontSize: 11, color: "#6B7280", marginBottom: 10 }}>
            Top {ml.article_count} semantically matched articles · x = days old, y = similarity, bubble = recency weight
          </div>
          {articleScatter.length > 0 ? (
            <ResponsiveContainer width="100%" height={190}>
              <ScatterChart margin={{ top: 4, right: 8, bottom: 20, left: -10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1F2937" />
                <XAxis
                  dataKey="x" type="number" name="Days old"
                  tick={{ fontSize: 10, fill: "#6B7280" }} axisLine={false} tickLine={false}
                  label={{ value: "Days old", position: "insideBottom", offset: -12, fontSize: 10, fill: "#4B5563" }}
                />
                <YAxis
                  dataKey="y" type="number" name="Similarity" domain={[0, 1]}
                  tick={{ fontSize: 10, fill: "#6B7280" }} axisLine={false} tickLine={false}
                  label={{ value: "Similarity", angle: -90, position: "insideLeft", offset: 12, fontSize: 10, fill: "#4B5563" }}
                />
                <ZAxis dataKey="z" range={[40, 220]} name="Recency %" />
                <Tooltip
                  contentStyle={{ backgroundColor: "#111827", border: "1px solid #374151", borderRadius: 8, fontSize: 12 }}
                  cursor={{ strokeDasharray: "3 3", stroke: "#374151" }}
                  content={({ payload }) => {
                    if (!payload?.length) return null;
                    const d = payload[0].payload as typeof articleScatter[0];
                    return (
                      <div style={{ background: "#111827", border: "1px solid #374151", borderRadius: 8, padding: "8px 12px", maxWidth: 220 }}>
                        <div style={{ fontSize: 11, color: "#F9FAFB", fontWeight: 600, marginBottom: 4 }}>{d.label}…</div>
                        <div style={{ fontSize: 10, color: "#9CA3AF" }}>Similarity: {(d.y * 100).toFixed(1)}%</div>
                        <div style={{ fontSize: 10, color: "#9CA3AF" }}>Age: {d.x} days · Recency: {d.z}%</div>
                        {d.cat && <div style={{ fontSize: 10, color: "#6366F1", marginTop: 2 }}>{d.cat}</div>}
                      </div>
                    );
                  }}
                />
                <Scatter data={articleScatter} fill="#6366F1" fillOpacity={0.8} />
                <ReferenceLine y={0.5} stroke="#374151" strokeDasharray="4 4" label={{ value: "0.5 threshold", fontSize: 9, fill: "#4B5563", position: "right" }} />
              </ScatterChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ height: 190, display: "flex", alignItems: "center", justifyContent: "center", color: "#6B7280", fontSize: 12, fontStyle: "italic" }}>
              No article embeddings matched yet — run scoring again after indexing.
            </div>
          )}
        </div>

        {/* ── Dim 2: Sentiment Trend — full-width dual chart ───────── */}
        <div className="cr-card" style={{ gridColumn: "1 / -1" }}>
          <DimHeader title="Sentiment Trend" score={ml.trend_score} max={ml.trend_max} percentile={ml.trend_percentile} color={trendColor} />

          {/* ── methodology explanation banner ── */}
          <div style={{
            background: "rgba(99,102,241,0.06)", border: "1px solid rgba(99,102,241,0.18)",
            borderRadius: 8, padding: "10px 14px", marginBottom: 12, fontSize: 11, color: "#D1D5DB", lineHeight: 1.7,
          }}>
            <div style={{ fontWeight: 700, color: "#A5B4FC", marginBottom: 4, fontSize: 12 }}>
              Why two charts?
            </div>
            <div>
              <span style={{ color: "#F9FAFB", fontWeight: 600 }}>Left — Raw signal (reference only):</span>
              {" "}average sentiment score per month. This NLP model outputs near-binary values (±1), so a single
              positive review in a month flips the average from −0.99 to +0.99 — pure noise, not a real trend.
            </div>
            <div style={{ marginTop: 4 }}>
              <span style={{ color: "#F9FAFB", fontWeight: 600 }}>Right — Clean signal (used for scoring):</span>
              {" "}% of negative reviews per month, restricted to months with ≥ {ml.trend_min_reviews} reviews
              ({ml.trend_months_filtered > 0 ? `${ml.trend_months_filtered} thin month${ml.trend_months_filtered > 1 ? "s" : ""} removed` : "no months removed"}).
              This is a 0–1 ratio — stable, robust to outliers, and directly meaningful.
              Regression is weighted by √(review count) so busy months dominate the fit.
            </div>
          </div>

          {/* ── stat row ── */}
          <div style={{ display: "flex", gap: 10, marginBottom: 12, flexWrap: "wrap", alignItems: "center" }}>
            <div style={{ fontSize: 11, color: "#6B7280" }}>
              Slope (neg_pct/month): <span style={{ color: trendColor, fontWeight: 700, fontFamily: "'JetBrains Mono', monospace" }}>
                {ml.trend_slope > 0 ? "+" : ""}{ml.trend_slope.toFixed(5)}
              </span>
            </div>
            <div style={{ fontSize: 11, color: "#6B7280" }}>
              R² (clean): <span style={{
                color: ml.trend_clean_r_squared < 0.35 ? "#F59E0B" : "#10B981",
                fontWeight: 700, fontFamily: "'JetBrains Mono', monospace",
              }}>{ml.trend_clean_r_squared.toFixed(3)}</span>
            </div>
            <span style={{
              fontSize: 9, fontWeight: 700, padding: "2px 8px", borderRadius: 9999,
              textTransform: "uppercase", letterSpacing: "0.08em",
              background: ml.trend_method === "mann_kendall" ? "rgba(245,158,11,0.15)" : "rgba(99,102,241,0.15)",
              color: ml.trend_method === "mann_kendall" ? "#F59E0B" : "#6366F1",
            }}>
              {ml.trend_method === "mann_kendall" ? "Mann-Kendall (Theil-Sen)" : "Linear fit"}
            </span>
            <span style={{
              fontSize: 9, fontWeight: 700, padding: "2px 8px", borderRadius: 9999,
              textTransform: "uppercase", letterSpacing: "0.08em",
              background: `${trendColor}20`, color: trendColor,
            }}>
              {ml.trend_direction.replace(/_/g, " ")}
            </span>
          </div>

          {/* ── MK insight (only when triggered) ── */}
          {ml.trend_method === "mann_kendall" && ml.mk_trend && (
            <div style={{
              background: "rgba(245,158,11,0.06)", border: "1px solid rgba(245,158,11,0.2)",
              borderRadius: 8, padding: "7px 12px", marginBottom: 10, fontSize: 10, color: "#D1D5DB", lineHeight: 1.6,
            }}>
              <span style={{ color: "#F59E0B", fontWeight: 700 }}>⚠ R²={ml.trend_clean_r_squared.toFixed(2)} — linear fit is weak.</span>
              {" "}Switched to <strong>Mann-Kendall</strong> non-parametric rank test.
              {" "}<strong>Theil-Sen slope</strong> = median of all pairwise slopes (robust to extreme months).
              {" "}Verdict: <strong style={{ color: ml.mk_significant ? "#F59E0B" : "#9CA3AF" }}>{ml.mk_trend}</strong>
              {ml.mk_p_value !== null && ` — p=${ml.mk_p_value} ${ml.mk_significant ? "✓ statistically significant" : "(not significant)"}`}.
            </div>
          )}

          {/* ── Poly acceleration insight ── */}
          {ml.poly_concavity !== "linear" && (
            <div style={{
              background: "rgba(16,185,129,0.06)", border: "1px solid rgba(16,185,129,0.15)",
              borderRadius: 8, padding: "7px 12px", marginBottom: 10, fontSize: 10, color: "#D1D5DB", lineHeight: 1.6,
            }}>
              <span style={{ color: "#10B981", fontWeight: 700 }}>Polynomial degree-2 curvature detected:</span>
              {" "}{ml.poly_concavity === "accelerating_decline"
                ? "⬇ The proportion of negative reviews is growing faster over time — complaints are accelerating. Urgent intervention window."
                : "⬆ The growth in negative reviews is slowing down — sentiment may be stabilising or recovering. Monitor closely."}
              {" "}Acceleration coefficient: <span style={{ fontFamily: "'JetBrains Mono', monospace", color: ml.poly_acceleration < 0 ? "#EF4444" : "#10B981" }}>
                {ml.poly_acceleration > 0 ? "+" : ""}{ml.poly_acceleration.toFixed(6)}
              </span>
            </div>
          )}

          {/* ── dual chart row ── */}
          {ml.trend_series.length > 1 ? (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>

              {/* LEFT — raw avg_sentiment (noisy reference) */}
              <div>
                <div style={{ fontSize: 10, fontWeight: 600, color: "#6B7280", marginBottom: 6, letterSpacing: "0.05em", textTransform: "uppercase" }}>
                  Raw signal — avg sentiment score{" "}
                  <span style={{ fontWeight: 400, color: "#4B5563" }}>(reference only, not used for scoring)</span>
                </div>
                <ResponsiveContainer width="100%" height={200}>
                  <ComposedChart data={ml.trend_series} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1F2937" />
                    <XAxis dataKey="period" tick={{ fontSize: 9, fill: "#6B7280" }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
                    <YAxis domain={[-1, 1]} tick={{ fontSize: 9, fill: "#6B7280" }} axisLine={false} tickLine={false} />
                    <Tooltip
                      contentStyle={{ backgroundColor: "#111827", border: "1px solid #374151", borderRadius: 8, fontSize: 11 }}
                      labelStyle={{ color: "#9CA3AF" }}
                      formatter={(v: number, name: string) => [
                        typeof v === "number" ? v.toFixed(4) : v,
                        name === "avg_sentiment" ? "Avg sentiment" : name,
                      ]}
                    />
                    <ReferenceLine y={0} stroke="#374151" strokeDasharray="4 4" label={{ value: "neutral", fontSize: 9, fill: "#4B5563", position: "right" }} />
                    <Line connectNulls type="monotone" dataKey="avg_sentiment" stroke="#6B7280" strokeWidth={1.5} dot={{ r: 2, fill: "#6B7280" }} name="avg_sentiment" />
                  </ComposedChart>
                </ResponsiveContainer>
                <div style={{ fontSize: 10, color: "#4B5563", marginTop: 4, fontStyle: "italic" }}>
                  Notice the erratic spikes caused by single-review months flipping ±1 — this is why avg sentiment cannot be used for trend fitting.
                </div>
              </div>

              {/* RIGHT — clean neg_pct (used for scoring) */}
              <div>
                <div style={{ fontSize: 10, fontWeight: 600, color: trendColor, marginBottom: 6, letterSpacing: "0.05em", textTransform: "uppercase" }}>
                  Clean signal — % negative reviews{" "}
                  <span style={{ fontWeight: 400, color: "#4B5563" }}>(≥{ml.trend_min_reviews} reviews/month · used for scoring)</span>
                </div>
                <ResponsiveContainer width="100%" height={200}>
                  <ComposedChart data={ml.trend_series} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1F2937" />
                    <XAxis dataKey="period" tick={{ fontSize: 9, fill: "#6B7280" }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
                    <YAxis domain={[0, 1]} tickFormatter={(v: number) => `${Math.round(v * 100)}%`} tick={{ fontSize: 9, fill: "#6B7280" }} axisLine={false} tickLine={false} />
                    <Tooltip
                      contentStyle={{ backgroundColor: "#111827", border: "1px solid #374151", borderRadius: 8, fontSize: 11 }}
                      labelStyle={{ color: "#9CA3AF" }}
                      formatter={(v: number, name: string) => {
                        if (name === "neg_pct") return [`${(v * 100).toFixed(1)}%`, "% negative reviews"];
                        if (name === "regression_predicted") return [`${(v * 100).toFixed(1)}%`, ml.trend_method === "mann_kendall" ? "Theil-Sen fit" : "Linear fit"];
                        if (name === "poly_predicted") return [`${(v * 100).toFixed(1)}%`, "Poly-2 curve"];
                        return [v, name];
                      }}
                    />
                    <Legend
                      formatter={(value) => {
                        if (value === "neg_pct") return "% negative (monthly)";
                        if (value === "regression_predicted") return ml.trend_method === "mann_kendall" ? "Theil-Sen (Mann-Kendall)" : "Linear regression";
                        if (value === "poly_predicted") return "Polynomial degree-2";
                        return value;
                      }}
                      wrapperStyle={{ fontSize: 10, color: "#9CA3AF" }}
                    />
                    <ReferenceLine y={0.5} stroke="#374151" strokeDasharray="4 4" label={{ value: "50%", fontSize: 9, fill: "#4B5563", position: "right" }} />
                    <Line connectNulls type="monotone" dataKey="neg_pct" stroke={trendColor} strokeWidth={2} dot={(props) => {
                      const { cx, cy, payload } = props;
                      if (payload.neg_pct === null) return <g key={`dot-${cx}-${cy}`} />;
                      const isFiltered = payload.review_count < ml.trend_min_reviews;
                      return <circle key={`dot-${cx}-${cy}`} cx={cx} cy={cy} r={isFiltered ? 2 : 3} fill={isFiltered ? "#4B5563" : trendColor} opacity={isFiltered ? 0.4 : 1} />;
                    }} name="neg_pct" />
                    <Line connectNulls type="monotone" dataKey="regression_predicted" stroke="#6366F1" strokeWidth={1.5} strokeDasharray="5 3" dot={false} name="regression_predicted" />
                    <Line connectNulls type="monotone" dataKey="poly_predicted" stroke="#F59E0B" strokeWidth={1.5} strokeDasharray="3 2" dot={false} name="poly_predicted" />
                  </ComposedChart>
                </ResponsiveContainer>
                <div style={{ fontSize: 10, color: "#4B5563", marginTop: 4, fontStyle: "italic" }}>
                  Faded dots = thin months ({"<"}{ml.trend_min_reviews} reviews) excluded from fit.
                  Indigo dashed = {ml.trend_method === "mann_kendall" ? "Theil-Sen line" : "linear fit"}.
                  Amber dashed = polynomial curve.
                </div>
              </div>

            </div>
          ) : (
            <div style={{ height: 200, display: "flex", alignItems: "center", justifyContent: "center", color: "#6B7280", fontSize: 12, fontStyle: "italic" }}>
              {ml.trend_series.length === 0 ? "No dated reviews — trend unavailable" : "Need ≥ 3 months of data for regression"}
            </div>
          )}
        </div>

        {/* ── Dim 3: Market Presence ────────────────────────────────── */}
        <div className="cr-card">
          <DimHeader title="Market Presence" score={ml.presence_score} max={ml.presence_max} percentile={ml.presence_percentile} color="#10B981" />
          <div style={{ fontSize: 11, color: "#6B7280", marginBottom: 10 }}>
            {ml.review_count.toLocaleString()} reviews · log-percentile within {ml.entity_type} sector · green = this company
          </div>
          <ResponsiveContainer width="100%" height={190}>
            <BarChart data={presencePeers} layout="vertical" margin={{ top: 0, right: 12, bottom: 0, left: 70 }}>
              <XAxis type="number" tick={{ fontSize: 9, fill: "#6B7280" }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 9, fill: "#6B7280" }} axisLine={false} tickLine={false} width={68} />
              <Tooltip
                contentStyle={{ backgroundColor: "#111827", border: "1px solid #374151", borderRadius: 8, fontSize: 12 }}
                formatter={(v: number) => [`${Math.round(v)} reviews`, "Review count"]}
              />
              <Bar dataKey="value" radius={[0, 3, 3, 0]}>
                {presencePeers.map((p, i) => (
                  <Cell key={i} fill={p.is_current ? "#10B981" : "#1F2937"} stroke={p.is_current ? "#10B981" : "none"} strokeWidth={p.is_current ? 1 : 0} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* ── Dim 4: Complaint Intensity ───────────────────────────── */}
        <div className="cr-card">
          <DimHeader title="Complaint Intensity" score={ml.intensity_score} max={ml.intensity_max} percentile={ml.intensity_percentile} color="#EF4444" />
          <div style={{ fontSize: 11, color: "#6B7280", marginBottom: 10 }}>
            {ml.negative_pct.toFixed(1)}% negative · sector avg {ml.sector_avg_negative_pct.toFixed(1)}% · red = this company
          </div>
          <ResponsiveContainer width="100%" height={190}>
            <BarChart data={intensityPeers} layout="vertical" margin={{ top: 0, right: 12, bottom: 0, left: 70 }}>
              <XAxis type="number" tick={{ fontSize: 9, fill: "#6B7280" }} axisLine={false} tickLine={false} tickFormatter={(v: number) => `${v}%`} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 9, fill: "#6B7280" }} axisLine={false} tickLine={false} width={68} />
              <Tooltip
                contentStyle={{ backgroundColor: "#111827", border: "1px solid #374151", borderRadius: 8, fontSize: 12 }}
                formatter={(v: number) => [`${v.toFixed(1)}%`, "Negative reviews"]}
              />
              <ReferenceLine x={ml.sector_avg_negative_pct} stroke="#F59E0B" strokeDasharray="4 4" label={{ value: "Sector avg", fontSize: 9, fill: "#F59E0B", position: "top" }} />
              <Bar dataKey="value" radius={[0, 3, 3, 0]}>
                {intensityPeers.map((p, i) => (
                  <Cell key={i} fill={p.is_current ? "#EF4444" : "#1F2937"} stroke={p.is_current ? "#EF4444" : "none"} strokeWidth={p.is_current ? 1 : 0} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

      </div>
    </div>
  );
}

function StatRow({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
      <span style={{ fontSize: 12, color: "#9CA3AF" }}>{label}</span>
      <span style={{
        fontFamily: mono ? "'JetBrains Mono', monospace" : "'DM Sans', sans-serif",
        fontSize: 16, fontWeight: 700, color: "#F9FAFB",
      }}>
        {value}
      </span>
    </div>
  );
}