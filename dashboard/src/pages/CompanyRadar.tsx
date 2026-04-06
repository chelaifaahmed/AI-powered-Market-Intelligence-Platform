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
} from "lucide-react";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
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
  teamwill_fit: number;
  sentiment_trend: number;
  market_presence: number;
  complaint_intensity: number;
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
            <button
              disabled
              title="Coming soon"
              style={{
                background: "transparent", border: "1px solid #374151", color: "#6B7280",
                padding: "10px 20px", borderRadius: 8, fontSize: 13, fontWeight: 500,
                cursor: "not-allowed", fontFamily: "'DM Sans', sans-serif", opacity: 0.6,
              }}
            >
              Export PDF Brief
            </button>
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