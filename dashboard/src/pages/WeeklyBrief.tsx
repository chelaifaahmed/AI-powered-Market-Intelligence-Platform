import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Target, AlertCircle, ChevronDown, ChevronUp } from "lucide-react";

const API = import.meta.env.VITE_API_URL || "";

// ─── CSS (Gen Z / Neobrutalist / Glassmorphic) ──────────────────────────────

const STYLES = `
  @keyframes wb-shimmer { 0%,100% { opacity: 0.4; } 50% { opacity: 0.8; } }
  @keyframes wb-card-in { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
  @keyframes wb-float { 0% { transform: translateY(0px) rotate(0deg); } 50% { transform: translateY(-10px) rotate(2deg); } 100% { transform: translateY(0px) rotate(0deg); } }
  
  @keyframes wb-fade-in-scale {
    0% { opacity: 0; transform: scale(0.95) translateY(15px); filter: blur(8px); }
    100% { opacity: 1; transform: scale(1) translateY(0); filter: blur(0px); }
  }
  @keyframes wb-gradient-move {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
  }
  @keyframes pulse-glow {
    0% { box-shadow: 6px 6px 0px #4F46E5, 0 0 20px rgba(79, 70, 229, 0.3); border-color: #4F46E5; }
    50% { box-shadow: 8px 8px 0px #FF007F, 0 0 40px rgba(255, 0, 127, 0.6); border-color: #FF007F; }
    100% { box-shadow: 6px 6px 0px #4F46E5, 0 0 20px rgba(79, 70, 229, 0.3); border-color: #4F46E5; }
  }
  @keyframes pulse-dot {
    0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(255, 0, 127, 0.9); }
    70% { transform: scale(1.2); box-shadow: 0 0 0 12px rgba(255, 0, 127, 0); }
    100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(255, 0, 127, 0); }
  }
  .wb-slide-active { animation: wb-fade-in-scale 0.7s cubic-bezier(0.34, 1.56, 0.64, 1) forwards; }
  
  .wb-container {
    padding: 32px 40px; 
    min-height: 100vh;
    font-family: 'DM Sans', sans-serif;
    background: url("/genz_bg.png") center/cover no-repeat fixed, #0f0c29;
    color: #F9FAFB;
    /* Noise overlay */
    position: relative;
  }
  .wb-container::before {
    content: ""; position: fixed; inset: 0; z-index: 0; pointer-events: none;
    background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 400 400' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)' opacity='0.05'/%3E%3C/svg%3E");
  }

  .wb-skel { background: rgba(255,255,255,0.1); border-radius: 8px; animation: wb-shimmer 1.5s ease-in-out infinite; }
  
  .wb-card {
    background: rgba(15, 15, 20, 0.4);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 2px solid rgba(255, 255, 255, 0.1);
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 20px;
    position: relative;
    transition: all 0.25s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    animation-fill-mode: forwards;
  }
  
  
  .wb-card-priority {
    border-color: rgba(255, 255, 255, 0.15);
  }
  .wb-card-priority:hover {
    transform: translateY(-6px) scale(1.02);
    border-color: #C6F91F;
    box-shadow: 0 10px 30px rgba(198, 249, 31, 0.2), inset 0 0 20px rgba(198, 249, 31, 0.05);
    z-index: 10;
  }

  .wb-hook {
    background: linear-gradient(135deg, rgba(15, 20, 35, 0.8), rgba(25, 20, 50, 0.9));
    backdrop-filter: blur(24px);
    -webkit-backdrop-filter: blur(24px);
    border: 3px solid #4F46E5;
    border-radius: 28px;
    padding: 40px;
    margin: 40px 0;
    box-shadow: 6px 6px 0px #4F46E5;
    position: relative;
    overflow: hidden;
    transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    animation: pulse-glow 5s infinite ease-in-out;
  }
  .wb-hook:hover {
    transform: translate(-2px, -3px) scale(1.01);
  }

  .wb-hook::after {
    content: "CRITICAL INTEL";
    position: absolute;
    top: 25px; right: -35px;
    background: #FF007F; color: #FFF;
    font-family: 'Syne', sans-serif; font-weight: 800; font-size: 13px;
    padding: 8px 40px; border: 2px solid #FFF;
    transform: rotate(45deg);
    box-shadow: 0 4px 15px rgba(0,0,0,0.4);
    letter-spacing: 2px;
    z-index: 10;
  }

  .wb-hook-header {
    font-family: 'Syne', sans-serif; 
    font-weight: 900; 
    font-size: 26px;
    margin: 0; 
    letter-spacing: 1px;
    background: linear-gradient(90deg, #C6F91F, #00FFFF, #C6F91F);
    background-size: 200% auto;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    text-transform: uppercase;
    display: flex;
    align-items: center;
    gap: 16px;
    animation: wb-gradient-move 3s linear infinite;
  }

  .wb-live-dot {
    width: 14px;
    height: 14px;
    background-color: #FF007F;
    border-radius: 50%;
    display: inline-block;
    animation: pulse-dot 2s infinite;
    box-shadow: 0 0 10px #FF007F;
  }

  .wb-btn { 
    background: transparent; border: 2px solid rgba(255,255,255,0.2); color: #F9FAFB; padding: 10px 20px; border-radius: 12px;
    font-size: 13px; font-weight: 700; cursor: pointer; font-family: 'Syne', sans-serif;
    transition: all 0.2s; white-space: nowrap; text-transform: uppercase; letter-spacing: 0.5px;
  }
  .wb-btn:hover { 
    background: #F9FAFB; color: #000; border-color: #F9FAFB;
    transform: scale(1.05); box-shadow: 0 0 15px rgba(255,255,255,0.5);
  }
  .wb-btn-export { border-color: #00FFFF; color: #00FFFF; }
  .wb-btn-export:hover { background: #00FFFF; color: #000; box-shadow: 0 0 20px rgba(0, 255, 255, 0.6); }

  .wb-link-title { font-size: 14px; color: #E5E7EB; line-height: 1.5; transition: all 0.2s; cursor: pointer; font-family: 'Syne', sans-serif; font-weight: 600; text-decoration: none;}
  .wb-link-title:hover { color: #C6F91F; text-shadow: 0 0 8px rgba(198, 249, 31, 0.5); padding-left: 5px; }

  /* Utility badges */
  .wb-badge-insurance { background: #1e3a5f; color: #60a5fa; border: 1px solid #60a5fa; box-shadow: 0 0 10px rgba(96,165,250,0.3); }
  .wb-badge-auto { background: #1c3320; color: #4ade80; border: 1px solid #4ade80; box-shadow: 0 0 10px rgba(74,222,128,0.3); }
  .wb-badge-tn { background: #3b0764; color: #d8b4fe; border: 1px solid #d8b4fe; }
  .wb-badge-analyst { background: #2e1065; color: #c4b5fd; border: 1px dashed #c4b5fd; }
  .wb-badge-verified { background: #052e16; color: #86efac; border: 1px solid #86efac; }

  @keyframes highlight-swoosh {
    0% { clip-path: polygon(0 0, 0 0, 0 100%, 0% 100%); }
    100% { clip-path: polygon(0 0, 100% 0, 100% 100%, 0 100%); }
  }

  .wb-highlight {
    position: relative;
    display: inline-block;
    color: #FFF;
    text-shadow: 0 2px 4px rgba(0,0,0,0.8);
    font-weight: 800;
    padding: 0 4px;
    margin: 0;
    z-index: 1;
    transition: color 0.3s ease;
  }
  .wb-highlight::before {
    content: "";
    position: absolute;
    z-index: -1;
    top: 60%;
    bottom: 0;
    left: 0; right: 0;
    background: #C6F91F;
    border-radius: 2px;
    transform: skewX(-4deg);
    box-shadow: none;
    animation: highlight-swoosh 0.5s ease-out forwards;
    animation-delay: 0.3s; 
    clip-path: polygon(0 0, 0 0, 0 100%, 0% 100%);
    transition: all 0.3s ease;
  }
  .wb-highlight:hover {
    color: #FFF;
  }
  .wb-highlight:hover::before {
    background: #FF007F;
    transform: skewX(0deg) scale(1.05);
    box-shadow: 4px 4px 0px rgba(0,0,0,0.4);
  }
  .wb-highlight span {
    position: relative;
    z-index: 2;
  }
`;

// ─── Types ───────────────────────────────────────────────────────────────────

interface TrendReasoning {
  score: number;
  reason: string;
  direction: string;
  change_pct: number;
}

interface FitReasoning {
  score: number;
  reason: string;
  matched_category: string;
}

interface PresenceReasoning {
  score: number;
  reason: string;
  review_count: number;
}

interface SectorContext {
  sector: string;
  percentile: number;
  sector_avg_score: number;
  performance_vs_sector: string;
  sector_avg_negative_pct: number;
}

interface IntensityReasoning {
  score: number;
  reason: string;
  sector: string;
  negative_pct: number;
}

interface ScoreReasoning {
  total: number;
  trend: TrendReasoning;
  teamwill_fit: FitReasoning;
  sector_context: SectorContext;
  market_presence: PresenceReasoning;
  signal_strength: string;
  complaint_intensity: IntensityReasoning;
  data_origin?: string;
  briefing_text?: string;
  why_text?: string;
  erp_module_recommendation?: string;
}

interface Opportunity {
  entity_name: string;
  entity_type: string;
  entity_id: string;
  region: string | null;
  overall_score: number;
  signal_strength: string;
  top_complaint_types: string[];
  score_reasoning: ScoreReasoning;
  sector_percentile: number;
  sector_avg_score: number;
  computed_at: string;
}

interface OppSummary {
  strong_signals: number;
  moderate_signals: number;
  weak_signals: number;
}

interface DashboardSummary {
  total_car_reviews: number;
  total_insurance_reviews: number;
  total_articles: number;
  total_brands: number;
  total_insurance_companies: number;
}

interface Article {
  id: string;
  title: string;
  source_url: string | null;
  publication_date: string | null;
  scraped_at: string;
}

interface ArticlesResponse {
  items: Article[];
  total: number;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function getCurrentDateTime(): string {
  const now = new Date();
  return now.toLocaleString("en-US", { 
    month: "short", 
    day: "numeric", 
    year: "numeric", 
    hour: "numeric", 
    minute: "2-digit",
    hour12: true
  });
}

function getScoreColor(score: number): string {
  if (score >= 80) return "#FF007F";
  if (score >= 65) return "#00FFFF";
  if (score >= 40) return "#C6F91F";
  return "#A78BFA";
}

function fmtTrend(direction: string): string {
  const map: Record<string, string> = {
    declining_fast: "declining fast 📉",
    declining: "declining 📉",
    stable: "stable ➖",
    improving: "improving 📈",
  };
  return map[direction] ?? direction.replace(/_/g, " ");
}

function deriveErpModule(entityType: string, matchedCategory: string): string {
  const cat = matchedCategory.toLowerCase();
  if (cat.includes("claim"))   return "Claims Mgt";
  if (cat.includes("customer")) return "Customer Service";
  if (cat.includes("policy"))  return "Policy Mgt";
  if (cat.includes("engine") || cat.includes("battery")) return "Fleet & Service";
  return entityType === "insurance" ? "Claims Mgt" : "Fleet & Service";
}

function timeAgo(dateStr: string): string {
  const diff = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
  if (diff < 3600)   return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400)  return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
  return new Date(dateStr).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

// ─── Main Page ────────────────────────────────────────────────────────────────

function HighlightMarker({ text }: { text: string }) {
  const regex = /(\b(?:priority target|surging|plummeting|priority|critical|urgent|declining|improving|negative|positive)\b|\b\d+(?:\.\d+)?%?\b)/gi;
  const parts = text.split(regex);
  return (
    <>
      {parts.map((part, i) => {
        if (i % 2 === 1) {
          return (
            <span key={i} className="wb-highlight">
              <span>{part}</span>
            </span>
          );
        }
        return part;
      })}
    </>
  );
}

export default function WeeklyBrief() {
  const navigate = useNavigate();
  const [showAll, setShowAll] = useState(false);
  const [slideIndex, setSlideIndex] = useState(0);
  const [slideVisible, setSlideVisible] = useState(true);

  useEffect(() => {
    const id = "wb-styles-genz";
    if (!document.getElementById(id)) {
      const el = document.createElement("style");
      el.id = id;
      el.textContent = STYLES;
      document.head.appendChild(el);
    }
  }, []);

  const { data: opportunities, isLoading, isError } = useQuery<Opportunity[]>({
    queryKey: ["opportunities-brief"],
    queryFn: () => fetch(`${API}/api/opportunities?limit=25`).then((r) => r.json()),
    staleTime: 30000,
  });

  const { data: oppSummary } = useQuery<OppSummary>({
    queryKey: ["opp-summary"],
    queryFn: () => fetch(`${API}/api/opportunities/summary`).then((r) => r.json()),
    staleTime: 30000,
  });

  const { data: dashSummary } = useQuery<DashboardSummary>({
    queryKey: ["dashboard-summary-brief"],
    queryFn: () => fetch(`${API}/api/dashboard/summary`).then((r) => r.json()),
    staleTime: 0,
  });

  const { data: articles } = useQuery<ArticlesResponse>({
    queryKey: ["articles-brief"],
    queryFn: () => fetch(`${API}/api/articles?limit=3`).then((r) => r.json()),
    staleTime: 30000,
  });

  const totalSignals = (oppSummary?.strong_signals ?? 0) + (oppSummary?.moderate_signals ?? 0);
  const top5 = opportunities?.slice(0, 5) ?? [];
  const rest = opportunities?.slice(5) ?? [];

  // Build 2 live slides from real data
  const slides: string[] = [];
  if (opportunities?.[0]) {
    const o = opportunities[0];
    const neg = o.score_reasoning?.complaint_intensity?.negative_pct ?? 0;
    const dir = fmtTrend(o.score_reasoning?.trend?.direction ?? "stable");
    const issue = o.top_complaint_types?.[0] ?? "operational issues";
    slides.push(
      `${o.entity_name} is the #1 priority target — ${o.overall_score.toFixed(0)}/100 score, ${neg.toFixed(0)}% negative sentiment, ${dir}. Key issue: ${issue}.`
    );
  }
  if (opportunities?.[1]) {
    const o = opportunities[1];
    const neg = o.score_reasoning?.complaint_intensity?.negative_pct ?? 0;
    const issue = o.top_complaint_types?.[0] ?? "operational issues";
    slides.push(
      `${o.entity_name} is surging as a #2 signal — ${o.overall_score.toFixed(0)}/100 with ${neg.toFixed(0)}% negative sentiment flagged. Top complaint: ${issue}.`
    );
  }

  useEffect(() => {
    if (slides.length < 2) return;
    const interval = setInterval(() => {
      setSlideVisible(false);
      setTimeout(() => {
        setSlideIndex((i) => (i + 1) % slides.length);
        setSlideVisible(true);
      }, 420);
    }, 5000);
    return () => clearInterval(interval);
  }, [slides.length]);

  return (
    <div className="wb-container">
      {/* Absolute positioning for UI layer over background */}
      <div style={{ position: "relative", zIndex: 10 }}>

        {/* ── Header ── */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 10 }}>
          <div>
            <h1 style={{
              fontFamily: "'Syne', sans-serif", fontWeight: 700, fontSize: 48,
              color: "#F9FAFB", margin: 0, lineHeight: 1.2,
              letterSpacing: "-0.5px"
            }}>
              Intelligence Brief
            </h1>
            <div style={{ 
              fontSize: 14, color: "#9CA3AF", fontWeight: 500, 
              fontFamily: "'DM Sans', sans-serif", marginTop: 6, letterSpacing: "1px",
              textTransform: "uppercase"
            }}>
              {getCurrentDateTime()}
            </div>
          </div>
          
          {totalSignals > 0 && (
            <div style={{
              background: "rgba(10, 15, 30, 0.7)", color: "#00FFFF",
              padding: "10px 20px", borderRadius: "12px", border: "1px solid rgba(0, 255, 255, 0.4)",
              fontSize: 13, fontWeight: 700, fontFamily: "'Syne', sans-serif",
              backdropFilter: "blur(12px)", letterSpacing: "1px",
              boxShadow: "0 4px 20px rgba(0, 255, 255, 0.15)"
            }}>
              ⚡ {totalSignals} SIGNALS ACTIVE
            </div>
          )}
        </div>

        {/* ── Middle Hook Area (The Focus) ── */}
        <div className="wb-hook">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24, paddingBottom: 16, borderBottom: "1px dashed rgba(255,255,255,0.15)" }}>
            <h2 className="wb-hook-header">
              <span className="wb-live-dot" />
              WHAT YOU NEED TO KNOW
            </h2>
            {/* Dot indicators */}
            {slides.length > 1 && (
              <div style={{ display: "flex", gap: 8 }}>
                {slides.map((_, i) => (
                  <div key={i} onClick={() => { setSlideVisible(false); setTimeout(() => { setSlideIndex(i); setSlideVisible(true); }, 420); }} style={{
                    width: i === slideIndex ? 24 : 10, height: 10, borderRadius: 5,
                    background: i === slideIndex ? "#FF007F" : "rgba(255,255,255,0.2)",
                    transition: "all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275)", cursor: "pointer",
                    boxShadow: i === slideIndex ? "0 0 10px rgba(255,0,127,0.5)" : "none"
                  }} />
                ))}
              </div>
            )}
          </div>

          {slides.length > 0 ? (
            <p
              key={slideIndex}
              className="wb-slide-active"
              style={{
                fontSize: 24, color: "#F9FAFB", lineHeight: 1.7, margin: 0,
                fontFamily: "'Syne', sans-serif", fontWeight: 600,
                textShadow: "0 2px 8px rgba(0,0,0,0.6)",
                opacity: slideVisible ? 1 : 0,
                transition: "opacity 0.4s ease",
              }}
            >
              <HighlightMarker text={slides[slideIndex]} />
            </p>
          ) : (
            <div style={{ padding: "12px 0" }}>
              <div className="wb-skel" style={{ height: 24, marginBottom: 16, width: "100%", background: "rgba(198,249,31,0.15)", borderRadius: "6px" }} />
              <div className="wb-skel" style={{ height: 24, width: "70%", background: "rgba(198,249,31,0.15)", borderRadius: "6px" }} />
            </div>
          )}
        </div>

        {/* ── Two-column layout ── */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 400px", gap: 32, alignItems: "start" }}>

          {/* Left: Priority cards */}
          <div>
            <div style={{
              fontFamily: "'Syne', sans-serif", fontSize: 20, fontWeight: 700, 
              color: "#FFF", marginBottom: 24, textTransform: "uppercase",
              borderBottom: "2px solid rgba(255,255,255,0.2)", paddingBottom: 12
            }}>
              🔥 Priority Targets
            </div>

            {isLoading && (
              <>
                <div className="wb-card"><div className="wb-skel" style={{height: 100}}/></div>
                <div className="wb-card"><div className="wb-skel" style={{height: 100}}/></div>
              </>
            )}

            {isError && (
              <div className="wb-card" style={{border: "2px solid #FF007F", textAlign: "center", padding: 40}}>
                <AlertCircle size={48} style={{ color: "#FF007F", margin: "0 auto 16px" }} />
                <div style={{ fontSize: 18, color: "#FFF", fontWeight: "bold" }}>System Glitch</div>
                <div style={{ color: "#AAA" }}>API Connection Failed</div>
              </div>
            )}

            {top5.map((opp, i) => (
              <PriorityCard key={opp.entity_id} opp={opp} rank={i + 1} delay={i * 100} onViewProfile={(type, id) => navigate(`/company?type=${type}&id=${id}`)} />
            ))}

            {showAll && rest.map((opp, i) => (
              <PriorityCard key={opp.entity_id} opp={opp} rank={top5.length + i + 1} delay={i * 50} onViewProfile={(type, id) => navigate(`/company?type=${type}&id=${id}`)} />
            ))}

            {rest.length > 0 && (
              <button
                onClick={() => setShowAll((v) => !v)}
                className="wb-btn" style={{ width: "100%", padding: "16px", marginTop: "10px", borderColor: "rgba(255,255,255,0.1)", background: "rgba(0,0,0,0.5)"}}
              >
                {showAll
                  ? "HIDE EXTRA SIGNALS ▲"
                  : `UNCOVER ${rest.length} MORE TARGETS ▼`}
              </button>
            )}
          </div>

          {/* Right: Market sidebar */}
          <MarketSidebar opportunities={opportunities} articles={articles} dashSummary={dashSummary} />

        </div>
      </div>
    </div>
  );
}

// ─── Extracted Components ───

function PriorityCard({ opp, rank, delay, onViewProfile }: { opp: Opportunity; rank: number; delay: number; onViewProfile: (type: string, id: string) => void }) {
  const accentColor = getScoreColor(opp.overall_score);
  const r = opp.score_reasoning;
  const isAnalyst   = r.data_origin === "analyst";
  const negPct      = r.complaint_intensity?.negative_pct ?? 0;
  const revCount    = r.market_presence?.review_count ?? 0;
  const trendDir    = r.trend?.direction ?? "stable";
  const matchedCat  = r.teamwill_fit?.matched_category ?? "";
  const erpModule   = isAnalyst && r.erp_module_recommendation
    ? r.erp_module_recommendation
    : deriveErpModule(opp.entity_type, matchedCat);
  const topComplaint = opp.top_complaint_types?.[0] ?? "General issues";

  const whyNow = isAnalyst && r.why_text
    ? r.why_text
    : [
        negPct > 0 ? `${negPct.toFixed(0)}% neg volume` : null,
        `Trend: ${fmtTrend(trendDir)}`,
        topComplaint ? `Issue: ${topComplaint}` : null,
      ].filter(Boolean).join(" · ");

  return (
    <div className="wb-card wb-card-priority" style={{ animationDelay: `${delay}ms` }}>
      <div style={{ display: "flex", gap: 20, alignItems: "center" }}>
        
        {/* Huge Rank Number */}
        <div style={{ 
          fontFamily: "'Syne', sans-serif", fontSize: 48, fontWeight: 900, 
          color: "rgba(255,255,255,0.05)", WebkitTextStroke: "1px rgba(255,255,255,0.2)",
          minWidth: "50px", textAlign: "right"
        }}>
          0{rank}
        </div>
        
        <div style={{ flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
            <h3 style={{ margin: 0, fontSize: 22, fontFamily: "'Syne', sans-serif", fontWeight: 700 }}>{opp.entity_name}</h3>
            
            <div style={{ display: "flex", gap: 6 }}>
              <span className={`wb-badge-${opp.entity_type === "insurance" ? "insurance" : "auto"}`} style={{ fontSize: 10, padding: "2px 8px", borderRadius: 4, fontWeight: "bold" }}>
                {opp.entity_type === "insurance" ? "INS" : "AUTO"}
              </span>
              {isAnalyst && <span className="wb-badge-analyst" style={{ fontSize: 10, padding: "2px 8px", borderRadius: 4, fontWeight: "bold"}}>ANALYST</span>}
            </div>
          </div>
          
          <div style={{ fontSize: 13, color: "#AAA", margin: "4px 0 12px 0", lineHeight: 1.5 }}>
            <strong style={{color:"#FFF"}}>WHY NOW:</strong> {whyNow}
            <br />
            <strong style={{color:"#C6F91F"}}>PITCH:</strong> ➔ {erpModule}
          </div>
        </div>
        
        <div style={{ textAlign: "center", minWidth: "120px" }}>
          <div style={{ fontFamily: "'Syne', sans-serif", fontSize: 40, fontWeight: 800, color: accentColor, textShadow: `0 0 20px ${accentColor}40` }}>
            {opp.overall_score.toFixed(0)}
          </div>
          <div style={{ fontSize: 11, color: "#888", letterSpacing: "1px", textTransform:"uppercase" }}>
            Top {Math.max(1, 100 - opp.sector_percentile)}%
          </div>
          <div style={{ marginTop: 12, display: "flex", gap: 6, justifyContent: "center" }}>
            <button className="wb-btn" onClick={() => onViewProfile(opp.entity_type === "insurance" ? "insurance" : "car", opp.entity_id)} style={{padding: "6px 12px", fontSize: 11}}>VIEW</button>
          </div>
        </div>
        
      </div>
    </div>
  );
}

function MarketSidebar({ opportunities, articles, dashSummary }: any) {
  const sectorStats = (() => {
    if (!opportunities) return [] as { label: string; value: number }[];
    const sectors: Record<string, number[]> = {};
    opportunities.forEach((o: any) => {
      const negPct = o.score_reasoning?.complaint_intensity?.negative_pct;
      if (negPct == null) return;
      const key = o.entity_type === "insurance" ? "INSURANCE" : "AUTOMOTIVE";
      sectors[key] = [...(sectors[key] ?? []), negPct];
    });
    return Object.entries(sectors).map(([label, vals]) => ({
      label,
      value: vals.reduce((s, v) => s + v, 0) / vals.length,
    }));
  })();

  const topComplaint = (() => {
    if (!opportunities) return null;
    const counts: Record<string, number> = {};
    opportunities.forEach((o: any) => {
      o.top_complaint_types?.forEach((c: string) => {
        counts[c] = (counts[c] ?? 0) + 1;
      });
    });
    const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]);
    return sorted[0] ?? null;
  })();

  return (
    <div style={{ position: "sticky", top: 40 }}>
      {/* ── Giant Stats Grid ── */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 24 }}>
        <div className="wb-card" style={{ padding: 20, marginBottom: 0 }}>
          <div style={{ fontSize: 11, color: "#AAA", letterSpacing: "1px" }}>COMPANIES</div>
          <div style={{ fontFamily: "'Syne', sans-serif", fontSize: 32, fontWeight: 800, color: "#C6F91F" }}>
            {(dashSummary?.total_brands ?? 0) + (dashSummary?.total_insurance_companies ?? 0)}
          </div>
        </div>
        <div className="wb-card" style={{ padding: 20, marginBottom: 0 }}>
          <div style={{ fontSize: 11, color: "#AAA", letterSpacing: "1px" }}>REVIEWS</div>
          <div style={{ fontFamily: "'Syne', sans-serif", fontSize: 32, fontWeight: 800, color: "#FF007F" }}>
            {((dashSummary?.total_car_reviews ?? 0) + (dashSummary?.total_insurance_reviews ?? 0)) > 1000 
              ? `${(((dashSummary?.total_car_reviews ?? 0) + (dashSummary?.total_insurance_reviews ?? 0)) / 1000).toFixed(1)}k` 
              : (dashSummary?.total_car_reviews ?? 0) + (dashSummary?.total_insurance_reviews ?? 0)}
          </div>
        </div>
      </div>

      <div className="wb-card" style={{ padding: 30 }}>
        <h3 style={{ fontFamily: "'Syne', sans-serif", fontSize: 18, color: "#FFF", marginTop: 0, textTransform: "uppercase" }}>
          Sector Heat
        </h3>
        
        {sectorStats.map(({ label, value }) => (
          <div key={label} style={{ marginBottom: 20 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
              <span style={{ fontSize: 12, fontWeight: 700 }}>{label}</span>
              <span style={{ fontSize: 12, color: value > 50 ? "#FF007F" : "#00FFFF", fontWeight: "bold" }}>
                {value.toFixed(0)}% NEG
              </span>
            </div>
            <div style={{ width: "100%", height: 8, background: "rgba(255,255,255,0.1)", borderRadius: 4, overflow: "hidden" }}>
              <div style={{ width: `${Math.min(value, 100)}%`, height: "100%", background: value > 50 ? "#FF007F" : "#00FFFF", borderRadius: 4 }} />
            </div>
          </div>
        ))}
        
        {topComplaint && (
          <div style={{ marginTop: 32, paddingTop: 24, borderTop: "2px dashed rgba(255,255,255,0.1)" }}>
            <div style={{ fontSize: 11, color: "#AAA", letterSpacing: "1px", marginBottom: 8}}>TOP MARKET COMPLAINT</div>
            <div style={{ fontSize: 18, color: "#FFF", fontWeight: 700, lineHeight: 1.3 }}>{topComplaint[0]}</div>
          </div>
        )}
      </div>
      
      <div className="wb-card" style={{ padding: 30 }}>
        <h3 style={{ fontFamily: "'Syne', sans-serif", fontSize: 18, color: "#FFF", marginTop: 0, textTransform: "uppercase", marginBottom: 20 }}>
          Latest Radar
        </h3>
        {articles?.items.map((art: any) => (
          <a key={art.id} href={art.source_url ?? "#"} target="_blank" rel="noreferrer" style={{ textDecoration: "none", display: "block", marginBottom: 16, padding: "12px", background: "rgba(255,255,255,0.05)", borderRadius: "8px", border: "1px solid rgba(255,255,255,0.05)" }}>
            <div className="wb-link-title" style={{marginBottom: 6}}>{art.title}</div>
            <div style={{ fontSize: 11, color: "#888", fontWeight: "bold" }}>{timeAgo(art.publication_date || art.scraped_at)}</div>
          </a>
        ))}
        {(!articles || articles.items.length === 0) && (
           <div style={{textAlign: "center", color: "#666", padding: 20}}>No recent intel.</div>
        )}
      </div>
    </div>
  );
}
