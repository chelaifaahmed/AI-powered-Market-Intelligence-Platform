import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type CompanyIntelligence, type ActionSignal, type SentimentTrendPoint, type ErpBrief } from "../api/client";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
} from "recharts";
import {
  X,
  Building2,
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  Minus,
  ChevronRight,
  ChevronDown,
  ExternalLink,
  Briefcase,
  Clock,
  Shield,
  Zap,
  Users,
  Activity,
  LogIn,
  Target,
  MessageCircle,
  Calendar,
} from "lucide-react";
import clsx from "clsx";

// ── Styles ──────────────────────────────────────────────────────────────────

const CI_STYLES = `
  .ci-overlay {
    position: fixed; inset: 0; z-index: 50;
    background: rgba(4, 9, 20, 0.85); backdrop-filter: blur(12px);
    display: flex; align-items: center; justify-content: center;
    padding: 24px;
    animation: fade-in 0.3s ease-out;
  }
  .ci-modal {
    background: linear-gradient(145deg, #0f172a 0%, #080b14 100%);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 20px; width: 100%; max-width: 1100px;
    max-height: 90vh; overflow: hidden;
    display: flex; flex-direction: column;
    box-shadow: 0 40px 100px -20px rgba(0,210,255,0.15), inset 0 1px 1px rgba(255,255,255,0.1);
    position: relative;
  }
  /* Glowing orb in the modal background */
  .ci-modal::before {
    content: ''; position: absolute; top: -150px; left: -150px; width: 400px; height: 400px;
    background: radial-gradient(circle, rgba(34,211,238,0.12) 0%, transparent 70%);
    border-radius: 50%; pointer-events: none; z-index: 0;
  }
  .ci-modal-body { overflow-y: auto; flex: 1; position: relative; z-index: 1; }
  
  .ci-tab { 
    padding: 10px 20px; font-size: 13px; font-weight: 600;
    border-radius: 8px; cursor: pointer; transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    border: 1px solid transparent; background: transparent; 
    position: relative; overflow: hidden;
  }
  .ci-tab.active { 
    background: linear-gradient(180deg, rgba(30,41,59,0.8) 0%, rgba(15,23,42,0.8) 100%); 
    color: #fff; border-color: rgba(255,255,255,0.1);
    box-shadow: 0 4px 15px rgba(0,0,0,0.3);
  }
  .ci-tab:not(.active) { color: #94A3B8; }
  .ci-tab:not(.active):hover { color: #E2E8F0; background: rgba(255,255,255,0.03); }
  
  .ci-table-row { 
    transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275); 
    animation: row-fade-in 0.5s cubic-bezier(0.4, 0, 0.2, 1) forwards; 
    opacity: 0; 
    transform-origin: center center;
    position: relative;
    z-index: 1;
    background: rgba(15, 23, 42, 0.5) !important;
    border: 1px solid rgba(255,255,255,0.04) !important;
  }
  .ci-table-row::before {
    content: ''; position: absolute; inset: 0; border-radius: inherit;
    background: linear-gradient(90deg, rgba(34,211,238,0) 0%, rgba(34,211,238,0.08) 50%, rgba(34,211,238,0) 100%);
    opacity: 0; transition: opacity 0.4s ease; z-index: -1;
  }
  .ci-table-row:hover { 
    background: linear-gradient(90deg, rgba(30,41,59,0.95), rgba(15,23,42,0.95)) !important; 
    cursor: pointer; 
    transform: perspective(1200px) rotateX(6deg) translateY(-6px) scale(1.02);
    border-color: rgba(34,211,238,0.4) !important;
    box-shadow: 0 22px 40px -12px rgba(0,0,0,0.8), 0 0 25px rgba(34,211,238,0.15), inset 3px 0 0 0 #22D3EE !important;
    z-index: 10;
  }
  .ci-table-row:hover::before { opacity: 1; }
  
  .ci-kpi-card {
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    background: linear-gradient(145deg, rgba(30,41,59,0.6) 0%, rgba(15,23,42,0.9) 100%) !important;
    backdrop-filter: blur(12px);
    border: 1px solid rgba(255,255,255,0.06) !important;
    position: relative; overflow: hidden;
  }
  .ci-kpi-card:hover {
    transform: translateY(-5px);
    box-shadow: 0 15px 35px -5px rgba(0,0,0,0.6), 0 0 15px rgba(255,255,255,0.05);
    border-color: rgba(255,255,255,0.15) !important;
  }
  .ci-kpi-card::after {
    content: ''; position: absolute; top: 0; left: -100%; width: 50%; height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.06), transparent);
    transform: skewX(-20deg); transition: all 0.6s ease;
  }
  .ci-kpi-card:hover::after { left: 200%; }

  .ci-glass-panel {
    background: linear-gradient(145deg, rgba(30,41,59,0.4) 0%, rgba(15,23,42,0.7) 100%) !important;
    border: 1px solid rgba(255,255,255,0.06) !important;
    backdrop-filter: blur(10px);
    transition: all 0.3s ease;
    box-shadow: 0 10px 25px rgba(0,0,0,0.2);
  }
  .ci-glass-panel:hover {
    border-color: rgba(255,255,255,0.12) !important;
    box-shadow: 0 15px 35px rgba(0,0,0,0.4);
    transform: translateY(-2px);
  }

  @keyframes row-fade-in { 
    from { opacity: 0; transform: translateY(24px) scale(0.97); } 
    to { opacity: 1; transform: translateY(0) scale(1); } 
  }
  @keyframes ci-fade-in { 
    from { opacity:0; transform: translateY(20px) scale(0.98); } 
    to { opacity:1; transform: translateY(0) scale(1); } 
  }
  @keyframes fade-in { from { opacity: 0; } to { opacity: 1; } }
  @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
  .ci-animate { animation: ci-fade-in 0.5s cubic-bezier(0.16, 1, 0.3, 1) forwards; }
  
  .ci-gradient-text {
    background: linear-gradient(90deg, #F8FAFC, #94A3B8);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }
  
  .ci-glow-tag {
    position: relative;
    box-shadow: 0 0 10px currentColor;
  }
`;

// ── Helpers ──────────────────────────────────────────────────────────────────

function tierColor(tier: string | null): string {
  if (tier === "engage") return "#22D3EE";
  if (tier === "develop") return "#A78BFA";
  if (tier === "watch") return "#F59E0B";
  return "#64748B";
}

function tierBg(tier: string | null): string {
  if (tier === "engage") return "rgba(34,211,238,0.12)";
  if (tier === "develop") return "rgba(167,139,250,0.12)";
  if (tier === "watch") return "rgba(245,158,11,0.12)";
  return "rgba(100,116,139,0.12)";
}

function interventionColor(level: string | null): string {
  if (level === "heavy") return "#F87171";
  if (level === "medium") return "#FB923C";
  if (level === "light") return "#4ADE80";
  return "#94A3B8";
}

function timingColor(timing: string | null): string {
  if (timing === "now") return "#4ADE80";
  if (timing === "3m") return "#22D3EE";
  if (timing === "6m") return "#A78BFA";
  if (timing === "hold") return "#64748B";
  return "#94A3B8";
}

function evidenceStrengthPct(strength: string | null | undefined): string {
  if (strength === "high")   return "90%";
  if (strength === "medium") return "75%";
  if (strength === "low")    return "55%";
  if (strength === "thin")   return "40%";
  return "N/A";
}

const getTrendIcon = (direction: string | null | undefined) => {
  if (direction === "improving")
    return <TrendingUp className="w-4 h-4" style={{ color: "#22c55e" }} />;
  if (direction === "declining_fast")
    return <TrendingDown className="w-4 h-4" style={{ color: "#ef4444" }} />;
  if (direction === "declining")
    return <TrendingDown className="w-4 h-4" style={{ color: "#f97316" }} />;
  if (direction === "stable")
    return <Minus className="w-4 h-4" style={{ color: "#eab308" }} />;
  return <Minus className="w-4 h-4" style={{ color: "#4b5563" }} />;
};

function suggestedOfferLabel(state: string | null, pain: string | null): string {
  if (state === "Digital Push")    return "Digital Transformation Suite";
  if (state === "Scaling Crisis" && pain?.toLowerCase().includes("customer")) return "Customer Service Management ERP";
  if (state === "Scaling Crisis")  return "Integrated ERP Suite";
  if (state === "Rapid Growth")    return "Advanced Analytics & Reporting";
  if (state === "AI Exploration")  return "Digital Transformation Suite";
  if (state === "Hiring Surge")    return "Customer Service Management ERP";
  if (state === "Survival Mode")   return "N/A";
  return "General ERP";
}

function tierPainLabel(tier: string | null): string {
  if (tier === "engage")               return "High market distress";
  if (tier === "develop")              return "Moderate operational friction";
  if (tier === "watch")                return "Low urgency signals";
  if (tier === "needs_investigation")  return "Insufficient data";
  return "—";
}


function KpiCard({ label, value, sub, accent }: { label: string; value: string | number; sub?: string; accent?: string }) {
  return (
    <div
      className="ci-kpi-card"
      style={{
        borderRadius: 12, padding: "16px 20px",
        borderLeft: accent ? `3px solid ${accent}` : undefined,
      }}
    >
      <p style={{ fontSize: 11, color: "#64748B", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 6 }}>{label}</p>
      <p style={{ fontSize: 24, fontWeight: 700, color: accent ?? "#F1F5F9", lineHeight: 1 }}>{value}</p>
      {sub && <p style={{ fontSize: 11, color: "#64748B", marginTop: 4 }}>{sub}</p>}
    </div>
  );
}

// ── ERP Brief Tab — AI-powered sales brief (Groq LLaMA-3.3-70B) ─────────────

function ErpBriefTab({ entity }: { entity: CompanyIntelligence }) {
  const [avoidOpen, setAvoidOpen] = useState(false);

  const { data: brief, isLoading, isError, error } = useQuery<ErpBrief>({
    queryKey: ["erp-brief", entity.entity_id],
    queryFn: () => api.erpBrief(entity.entity_id),
    staleTime: 300000,
    retry: 1,
  });

  if (isLoading) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 14, paddingTop: 4 }}>
        <p style={{ fontSize: 13, color: "#64748B", display: "flex", alignItems: "center", gap: 10, lineHeight: 1.5 }}>
          <span style={{ display: "inline-block", width: 14, height: 14, border: "2px solid #6366f1", borderTopColor: "transparent", borderRadius: "50%", animation: "spin 0.8s linear infinite", flexShrink: 0 }} />
          Generating expert brief — analyzing pain profile, ERP catalog match, and competitor intelligence...
        </p>
        {[1, 2, 3].map(i => (
          <div key={i} style={{ background: "rgba(30,41,59,0.5)", borderRadius: 12, padding: 16, border: "1px solid rgba(255,255,255,0.06)" }}>
            <div style={{ display: "flex", gap: 10, marginBottom: 14 }}>
              <div style={{ width: 28, height: 28, borderRadius: "50%", background: "rgba(255,255,255,0.06)" }} />
              <div style={{ flex: 1 }}>
                <div style={{ height: 13, width: `${35 + i * 12}%`, background: "rgba(255,255,255,0.06)", borderRadius: 4, marginBottom: 8 }} />
                <div style={{ height: 10, width: "22%", background: "rgba(255,255,255,0.04)", borderRadius: 4 }} />
              </div>
            </div>
            <div style={{ height: 10, background: "rgba(255,255,255,0.04)", borderRadius: 4, marginBottom: 6 }} />
            <div style={{ height: 10, width: "85%", background: "rgba(255,255,255,0.04)", borderRadius: 4, marginBottom: 6 }} />
            <div style={{ height: 10, width: "60%", background: "rgba(255,255,255,0.04)", borderRadius: 4 }} />
          </div>
        ))}
      </div>
    );
  }

  if (isError || !brief) {
    const errMsg = isError && error instanceof Error ? error.message : null;
    return (
      <div style={{ padding: "16px 0", display: "flex", flexDirection: "column", gap: 8 }}>
        <p style={{ fontSize: 13, color: "#64748B", lineHeight: 1.6 }}>
          Could not generate brief — the data will be available on next load.
        </p>
        {errMsg && (
          <pre style={{ fontSize: 11, color: "#F87171", background: "rgba(248,113,113,0.06)", border: "1px solid rgba(248,113,113,0.18)", borderRadius: 8, padding: "8px 12px", whiteSpace: "pre-wrap", wordBreak: "break-all", margin: 0 }}>
            {errMsg}
          </pre>
        )}
      </div>
    );
  }

  const scores = brief._metadata?.erp_scores ?? {};
  const topS   = scores[brief.top_pick?.erp_name ?? ""];
  const altS   = scores[brief.alternative?.erp_name ?? ""];
  const isAuto = brief._metadata?.entity_type === "brand";

  const fitLabel = isAuto ? "Automotive fit" : "Insurance fit";
  const fitVal   = (s: typeof topS) => s ? (isAuto ? s.automotive_fit : s.insurance_fit) : null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, paddingBottom: 20 }}>

      {/* ── Header ── */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
        <div>
          <p style={{ fontSize: 13, color: "#94A3B8", fontWeight: 500 }}>
            TEAMWILL's recommended pitch order for{" "}
            <span style={{ color: "#F1F5F9", fontWeight: 700 }}>{entity.entity_name}</span>
          </p>
          <p style={{ fontSize: 11, color: "#475569", marginTop: 3 }}>
            Based on pain profile · company state · ERP catalog · competitor intelligence
          </p>
        </div>
        <span style={{ fontSize: 10, color: "#64748B", background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", padding: "3px 8px", borderRadius: 6, whiteSpace: "nowrap", flexShrink: 0 }}>
          Groq LLaMA-3.3-70B
        </span>
      </div>

      {/* ── Card 1 — Top Pick ── */}
      <div style={{ border: "1px solid rgba(99,102,241,0.25)", borderLeft: "3px solid #6366f1", borderRadius: 12, background: "rgba(99,102,241,0.04)", overflow: "hidden" }}>
        <div style={{ padding: "14px 18px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
            <span style={{ width: 26, height: 26, borderRadius: "50%", background: "#EEEDFE", color: "#534AB7", fontSize: 12, fontWeight: 900, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>1</span>
            <span style={{ fontSize: 15, fontWeight: 600, color: "#F1F5F9", flex: 1 }}>{brief.top_pick.erp_name}</span>
            {topS?.teamwill_relevance === 5 && (
              <span style={{ fontSize: 10, color: "#818CF8", background: "rgba(99,102,241,0.15)", border: "1px solid rgba(99,102,241,0.35)", padding: "2px 9px", borderRadius: 20, fontWeight: 700, flexShrink: 0 }}>
                TEAMWILL certified
              </span>
            )}
          </div>

          <p style={{ fontSize: 13, color: "#CBD5E1", lineHeight: 1.65, marginBottom: 12 }}>{brief.top_pick.verdict}</p>

          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {brief.top_pick.tags.map((tag, i) => (
              <span key={i} style={{ fontSize: 10, fontWeight: 700, color: "#818CF8", background: "rgba(99,102,241,0.12)", border: "1px solid rgba(99,102,241,0.22)", padding: "3px 10px", borderRadius: 20 }}>{tag}</span>
            ))}
          </div>
        </div>

        {/* Evidence row */}
        {topS && (
          <div style={{ background: "rgba(0,0,0,0.22)", padding: "10px 18px", display: "flex", flexWrap: "wrap", gap: 20, borderTop: "1px solid rgba(255,255,255,0.05)", alignItems: "flex-start" }}>
            <div>
              <p style={{ fontSize: 9, color: "#475569", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 3 }}>{fitLabel}</p>
              <p style={{ fontSize: 15, fontWeight: 700, color: "#F1F5F9", lineHeight: 1 }}>
                {fitVal(topS)}<span style={{ fontSize: 10, color: "#64748B" }}>/10</span>
              </p>
            </div>
            <div>
              <p style={{ fontSize: 9, color: "#475569", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 3 }}>TEAMWILL relevance</p>
              <p style={{ fontSize: 15, fontWeight: 700, color: "#6366f1", lineHeight: 1 }}>
                {topS.teamwill_relevance}<span style={{ fontSize: 10, color: "#64748B" }}>/5</span>
              </p>
            </div>
            <div>
              <p style={{ fontSize: 9, color: "#475569", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 3 }}>MENA adoption</p>
              <p style={{ fontSize: 11, fontWeight: 600, color: "#94A3B8" }}>{topS.mena_adoption}</p>
            </div>
            {brief.top_pick.peer_customers.length > 0 && (
              <div>
                <p style={{ fontSize: 9, color: "#475569", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 5 }}>Peer reference customers</p>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                  {brief.top_pick.peer_customers.map((c, i) => {
                    const isRef = topS.notable_customers.some(n => n.toLowerCase().includes(c.toLowerCase()));
                    return (
                      <span key={i} style={{ fontSize: 10, fontWeight: 700, padding: "2px 9px", borderRadius: 20, background: isRef ? "rgba(99,102,241,0.18)" : "rgba(255,255,255,0.06)", color: isRef ? "#818CF8" : "#64748B", border: isRef ? "1px solid rgba(99,102,241,0.3)" : "1px solid transparent" }}>{c}</span>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Opening line */}
        <div style={{ margin: "14px 18px 0", borderLeft: "3px solid #6366f1", background: "rgba(0,0,0,0.2)", padding: "10px 14px", borderRadius: "0 8px 8px 0" }}>
          <p style={{ fontSize: 9, color: "#6366f1", textTransform: "uppercase", letterSpacing: "0.1em", fontWeight: 800, marginBottom: 5 }}>Opening line for the call</p>
          <p style={{ fontSize: 13, color: "#CBD5E1", fontStyle: "italic", lineHeight: 1.55 }}>"{brief.top_pick.opening_line}"</p>
        </div>

        {/* TEAMWILL edge */}
        <div style={{ margin: "10px 18px 16px", background: "rgba(0,0,0,0.15)", border: "1px solid rgba(255,255,255,0.06)", padding: "10px 14px", borderRadius: 8 }}>
          <p style={{ fontSize: 9, color: "#475569", textTransform: "uppercase", letterSpacing: "0.1em", fontWeight: 800, marginBottom: 5 }}>TEAMWILL's edge</p>
          <p style={{ fontSize: 12, color: "#94A3B8", lineHeight: 1.55 }}>{brief.top_pick.teamwill_advantage}</p>
        </div>
      </div>

      {/* ── Card 2 — Alternative ── */}
      {brief.alternative && (
        <div style={{ border: "1px solid rgba(20,184,166,0.2)", borderLeft: "3px solid #14b8a6", borderRadius: 12, background: "rgba(20,184,166,0.03)", padding: "14px 18px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
            <span style={{ width: 26, height: 26, borderRadius: "50%", background: "#E1F5EE", color: "#0F6E56", fontSize: 12, fontWeight: 900, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>2</span>
            <span style={{ fontSize: 15, fontWeight: 600, color: "#F1F5F9", flex: 1 }}>{brief.alternative.erp_name}</span>
            {altS && (
              <span style={{ fontSize: 11, color: "#64748B" }}>
                {fitLabel}: <span style={{ color: "#94A3B8", fontWeight: 600 }}>{fitVal(altS)}/10</span>
              </span>
            )}
          </div>
          <p style={{ fontSize: 13, color: "#94A3B8", lineHeight: 1.6, marginBottom: 10 }}>{brief.alternative.verdict}</p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 10 }}>
            {brief.alternative.tags.map((tag, i) => (
              <span key={i} style={{ fontSize: 10, fontWeight: 700, color: "#2DD4BF", background: "rgba(20,184,166,0.1)", border: "1px solid rgba(20,184,166,0.22)", padding: "3px 10px", borderRadius: 20 }}>{tag}</span>
            ))}
          </div>
          <div style={{ background: "rgba(0,0,0,0.2)", padding: "8px 12px", borderRadius: 8 }}>
            <p style={{ fontSize: 9, color: "#475569", textTransform: "uppercase", letterSpacing: "0.07em", fontWeight: 700, marginBottom: 4 }}>Why ranked below</p>
            <p style={{ fontSize: 12, color: "#64748B", lineHeight: 1.55 }}>{brief.alternative.why_ranked_lower}</p>
          </div>
        </div>
      )}

      {/* ── Competitor Intelligence ── */}
      {brief.competitor_alerts?.length > 0 && (
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 10 }}>
            <AlertTriangle size={12} color="#F59E0B" />
            <p style={{ fontSize: 10, color: "#64748B", textTransform: "uppercase", letterSpacing: "0.08em", fontWeight: 700 }}>
              Competitor intelligence — who else may be pitching this account
            </p>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {brief.competitor_alerts.map((c, i) => (
              <div key={i} style={{ border: "1px solid #F0997B", background: "rgba(250,236,231,0.07)", borderRadius: 10, padding: "10px 14px", display: "flex", gap: 10, alignItems: "flex-start" }}>
                <Building2 size={13} style={{ color: "#FB923C", marginTop: 2, flexShrink: 0 }} />
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 4 }}>
                    <span style={{ fontSize: 12, fontWeight: 700, color: "#F1F5F9" }}>{c.company_name}</span>
                    {c.tier && (
                      <span style={{ fontSize: 9, color: "#FB923C", background: "rgba(251,146,60,0.12)", border: "1px solid rgba(251,146,60,0.3)", padding: "1px 7px", borderRadius: 10, fontWeight: 700 }}>{c.tier}</span>
                    )}
                  </div>
                  <p style={{ fontSize: 12, color: "#94A3B8", lineHeight: 1.55 }}>{c.threat}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Avoid (collapsible) ── */}
      {brief.avoid && (
        <div>
          <button
            onClick={() => setAvoidOpen(v => !v)}
            style={{ display: "flex", alignItems: "center", gap: 6, background: "transparent", border: "none", cursor: "pointer", padding: "5px 0", color: "#475569", fontSize: 11, fontWeight: 500 }}
          >
            <ChevronDown size={13} style={{ color: "#475569", transform: avoidOpen ? "rotate(180deg)" : "rotate(0deg)", transition: "transform 0.2s ease" }} />
            Why we skip <strong style={{ color: "#64748B", margin: "0 3px" }}>{brief.avoid.erp_name}</strong> despite the fit score
          </button>
          {avoidOpen && (
            <div style={{ background: "rgba(248,113,113,0.05)", border: "1px solid rgba(248,113,113,0.18)", borderRadius: 8, padding: "10px 14px", marginTop: 4 }}>
              <p style={{ fontSize: 12, color: "#94A3B8", lineHeight: 1.55 }}>{brief.avoid.reason}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Modal tabs ───────────────────────────────────────────────────────────────

function SignalTimeline({ signals }: { signals: ActionSignal[] }) {
  if (!signals.length) {
    return <p style={{ color: "#64748B", fontSize: 13, padding: "16px 0" }}>No action signals recorded yet.</p>;
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {signals.map((s, i) => (
        <div
          key={i}
          className="ci-glass-panel"
            style={{
              borderRadius: 10, padding: "12px 14px",
            borderLeft: `3px solid ${s.polarity === "positive" ? "#4ADE80" : s.polarity === "negative" ? "#F87171" : "#64748B"}`,
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
            <span style={{ fontSize: 11, color: "#94A3B8", textTransform: "uppercase", letterSpacing: "0.06em" }}>
              {s.signal_type?.replace(/_/g, " ") ?? "signal"}
            </span>
            <span style={{ fontSize: 11, color: "#64748B" }}>{s.signal_date ?? ""}</span>
          </div>
          <p style={{ fontSize: 13, color: "#E2E8F0", fontWeight: 500, marginBottom: 4 }}>{s.headline}</p>
          {s.summary && <p style={{ fontSize: 12, color: "#94A3B8", lineHeight: 1.5 }}>{s.summary}</p>}
          {s.source_url && (
            <a href={s.source_url} target="_blank" rel="noopener noreferrer"
              style={{ fontSize: 11, color: "#22D3EE", display: "flex", alignItems: "center", gap: 3, marginTop: 6 }}>
              <ExternalLink size={10} /> {s.source_name ?? "Source"}
            </a>
          )}
        </div>
      ))}
    </div>
  );
}

function SentimentChart({ trend }: { trend: SentimentTrendPoint[] }) {
  if (!trend.length) {
    return (
      <div style={{ height: 160, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <p style={{ color: "#475569", fontSize: 13, fontStyle: "italic", textAlign: "center", maxWidth: 360, lineHeight: 1.6 }}>
          No sentiment history available — this entity has no public review data yet.
          <br />
          <span style={{ color: "#334155" }}>The visibility gap itself is a sales signal.</span>
        </p>
      </div>
    );
  }
  const data = trend.map(t => ({
    date: t.period_date.slice(0, 7),
    negative: t.negative_count,
    positive: t.positive_count,
    neutral: t.neutral_count,
  }));
  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
        <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#64748B" }} />
        <YAxis tick={{ fontSize: 10, fill: "#64748B" }} />
        <Tooltip
          contentStyle={{ background: "#0F172A", border: "1px solid #1E293B", borderRadius: 8, fontSize: 12 }}
          labelStyle={{ color: "#94A3B8" }}
        />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        <Line type="monotone" dataKey="negative" stroke="#F87171" strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="positive" stroke="#4ADE80" strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="neutral" stroke="#94A3B8" strokeWidth={1.5} dot={false} strokeDasharray="4 2" />
      </LineChart>
    </ResponsiveContainer>
  );
}

function IntelligenceModal({ entity, onClose }: { entity: CompanyIntelligence; onClose: () => void }) {
  const [tab, setTab] = useState<"signals" | "intel" | "erp">("signals");
  const [openSection, setOpenSection] = useState<number | null>(null);

  const axes = (entity.v2_reasoning?.axes ?? {}) as Record<string, { score?: number }>;
  const hiringRoles = entity.key_hiring_roles
    ? entity.key_hiring_roles.split(",").map(r => r.trim()).filter(Boolean)
    : [];

  return (
    <div className="ci-overlay" onClick={onClose}>
      <div className="ci-modal ci-animate" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div style={{ padding: "20px 24px", borderBottom: "1px solid #1E293B", display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
              {entity.entity_type === "brand" ? <Building2 size={18} color="#22D3EE" /> : <Shield size={18} color="#A78BFA" />}
              <h2 className="ci-gradient-text" style={{ fontSize: 24, fontWeight: 800 }}>{entity.entity_name}</h2>
              {entity.v2_tier && (
                <span style={{ fontSize: 11, fontWeight: 600, color: tierColor(entity.v2_tier), background: tierBg(entity.v2_tier), padding: "2px 8px", borderRadius: 4 }}>
                  {entity.v2_tier.toUpperCase()}
                </span>
              )}
            </div>
            <p style={{ fontSize: 12, color: "#64748B" }}>
              {entity.entity_type === "brand" ? "Automotive" : "Insurance"} · {entity.region ?? "—"} · {entity.v2_overall_score != null ? `Opportunity Score ${entity.v2_overall_score.toFixed(1)}` : `Distress Score ${entity.overall_score?.toFixed(1) ?? "—"}`}
            </p>
          </div>
          <button onClick={onClose} style={{ background: "transparent", border: "none", color: "#64748B", cursor: "pointer", padding: 4 }}>
            <X size={18} />
          </button>
        </div>

        {/* Tabs */}
        <div style={{ padding: "12px 24px", borderBottom: "1px solid #1E293B", display: "flex", gap: 6 }}>
          <button className={`ci-tab ${tab === "signals" ? "active" : ""}`} onClick={() => setTab("signals")}>
            Public Signals · Intervention
          </button>
          <button className={`ci-tab ${tab === "intel" ? "active" : ""}`} onClick={() => setTab("intel")}>
            Company Intelligence · Chart
          </button>
          <button className={`ci-tab ${tab === "erp" ? "active" : ""}`} onClick={() => setTab("erp")}>
            ERP Catalog Match
          </button>
        </div>

        {/* Body */}
        <div className="ci-modal-body" style={{ padding: "20px 24px" }}>
          {tab === "signals" && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 460px", gap: 24 }}>
              {/* Signal timeline */}
              <div>
                <p style={{ fontSize: 12, color: "#64748B", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 12 }}>Signal Timeline (last 5)</p>
                <SignalTimeline signals={entity.recent_signals} />
              </div>

              {/* Right column */}
              <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                {/* Intervention card */}
                <div className="ci-glass-panel" style={{ borderRadius: 12, padding: 16 }}>
                  <p style={{ fontSize: 11, color: "#64748B", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 10 }}>Intervention</p>
                  <div style={{ display: "flex", gap: 10, marginBottom: 10 }}>
                    <div style={{ flex: 1, textAlign: "center", background: "#1E293B", borderRadius: 8, padding: "10px 6px" }}>
                      <p style={{ fontSize: 10, color: "#64748B", marginBottom: 4 }}>Level</p>
                      <p style={{ fontSize: 15, fontWeight: 700, color: interventionColor(entity.intervention_level) }}>
                        {entity.intervention_level ?? "—"}
                      </p>
                    </div>
                    <div style={{ flex: 1, textAlign: "center", background: "#1E293B", borderRadius: 8, padding: "10px 6px" }}>
                      <p style={{ fontSize: 10, color: "#64748B", marginBottom: 4 }}>Timing</p>
                      <p style={{ fontSize: 15, fontWeight: 700, color: timingColor(entity.outreach_timing) }}>
                        {entity.outreach_timing ?? "—"}
                      </p>
                    </div>
                  </div>
                  <div>
                    <p style={{ fontSize: 11, color: "#64748B", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 8 }}>Four-Axis Profile</p>
                    <ResponsiveContainer width="100%" height={200}>
                      <RadarChart
                        data={[
                          { axis: "Pain",         value: entity.v2_pain_score         ?? 0 },
                          { axis: "Recovery",     value: entity.v2_recovery_score     ?? 0 },
                          { axis: "ERP Fit",      value: entity.v2_erp_fit_score      ?? 0 },
                          { axis: "Reachability", value: entity.v2_reachability_score ?? 0 },
                        ]}
                        margin={{ top: 10, right: 30, bottom: 10, left: 30 }}
                      >
                        <PolarGrid stroke="#1F2937" />
                        <PolarAngleAxis dataKey="axis" tick={{ fill: "#9CA3AF", fontSize: 11, fontWeight: 700 }} />
                        <Radar
                          name={entity.entity_name}
                          dataKey="value"
                          stroke="#6366f1"
                          fill="#6366f1"
                          fillOpacity={0.18}
                          strokeWidth={2}
                        />
                        <Tooltip
                          contentStyle={{ backgroundColor: "#0F172A", border: "1px solid #1E293B", borderRadius: 8, fontSize: 11 }}
                          formatter={(v: number) => [`${Math.round(v)}`, "Score"]}
                        />
                      </RadarChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* Suggested Intervention — Accordion */}
                {(() => {
                  const brief = entity.intervention_brief && !entity.intervention_brief.error
                    ? entity.intervention_brief : null;

                  function firstSentence(text: string): string {
                    const parts = text.split(". ");
                    return parts[0] + (parts.length > 1 ? "..." : "");
                  }

                  const entryFallback =
                    entity.intervention_level === "Immediate Intervention" ? "Direct outreach to decision-maker — timing is critical" :
                    entity.intervention_level === "Strategic Contact" ? "Schedule a discovery call within 2 weeks" :
                    entity.intervention_level === "Soft Entry" ? "Lead with insight, not a pitch" :
                    "Monitor — not ready yet";

                  const positioningFallback = suggestedOfferLabel(entity.company_state, null);

                  const toneFallback =
                    entity.v2_tier === "engage" ? "Direct and solution-focused" :
                    entity.v2_tier === "develop" ? "Consultative and analytical" :
                    "Observational";

                  const sections: { icon: React.ReactNode; label: string; hook: string; content: React.ReactNode }[] = [
                    {
                      icon: <LogIn size={16} style={{ color: "#22D3EE", flexShrink: 0 }} />,
                      label: "Entry Strategy",
                      hook: brief?.entry_strategy ? firstSentence(brief.entry_strategy) : entryFallback,
                      content: brief?.entry_strategy
                        ? <span>{brief.entry_strategy}</span>
                        : <span style={{ color: "#475569" }}>{entryFallback}</span>,
                    },
                    {
                      icon: <Target size={16} style={{ color: "#A78BFA", flexShrink: 0 }} />,
                      label: "Positioning",
                      hook: brief?.positioning ?? positioningFallback,
                      content: brief?.positioning
                        ? <>{brief.positioning}{brief.suggested_entry_message && <><br /><br /><span style={{ color: "#64748B" }}>Suggested message: </span><em style={{ color: "#CBD5E1" }}>"{brief.suggested_entry_message}"</em></>}</>
                        : <span style={{ color: "#475569" }}>{positioningFallback}</span>,
                    },
                    {
                      icon: <MessageCircle size={16} style={{ color: "#F59E0B", flexShrink: 0 }} />,
                      label: "Outreach tone",
                      hook: brief?.outreach_tone ?? toneFallback,
                      content: brief?.outreach_tone
                        ? <>{brief.outreach_tone}{brief.avoid && <><br /><br /><span style={{ color: "#F87171" }}>Avoid: {brief.avoid}</span></>}</>
                        : <span style={{ color: "#475569" }}>{toneFallback}</span>,
                    },
                    {
                      icon: <Calendar size={16} style={{ color: "#4ADE80", flexShrink: 0 }} />,
                      label: "Best timing",
                      hook: brief?.best_timing ?? (entity.outreach_timing ?? "—"),
                      content: brief?.best_timing
                        ? <><span style={{ color: "#22c55e" }}>{brief.best_timing}</span>{brief.confidence_note && <><br /><br /><span style={{ color: "#475569" }}>{brief.confidence_note}</span></>}</>
                        : <span style={{ color: "#475569" }}>{entity.outreach_timing ?? "—"}</span>,
                    },
                  ];

                  return (
                    <div className="ci-glass-panel" style={{ borderRadius: 12, padding: 16 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                          <Briefcase size={14} color="#22D3EE" />
                          <p style={{ fontSize: 11, color: "#64748B", textTransform: "uppercase", letterSpacing: "0.08em" }}>Suggested Intervention</p>
                        </div>
                        {entity.intervention_brief?.pain_escalation_label && (
                          <span style={{ fontSize: 10, color: "#F59E0B", background: "rgba(245,158,11,0.1)", padding: "2px 7px", borderRadius: 4, fontWeight: 600 }}>
                            {entity.intervention_brief.pain_escalation_label}
                          </span>
                        )}
                      </div>

                      {sections.map((section, idx) => (
                        <div key={idx} style={{ borderBottom: idx < 3 ? "1px solid rgba(255,255,255,0.06)" : undefined }}>
                          <div
                            style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, padding: "12px 0", cursor: "pointer" }}
                            onClick={() => setOpenSection(openSection === idx ? null : idx)}
                          >
                            <div style={{ flex: 1 }}>
                              <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                                {section.icon}
                                <span style={{ fontSize: 11, textTransform: "uppercase" as const, letterSpacing: "0.08em", color: "#64748B" }}>{section.label}</span>
                              </div>
                              <p style={{ fontSize: 14, fontWeight: 500, color: "#E2E8F0", lineHeight: 1.4, margin: 0 }}>{section.hook}</p>
                            </div>
                            <ChevronDown
                              size={16}
                              style={{
                                color: "#64748B",
                                flexShrink: 0,
                                marginTop: 2,
                                transform: openSection === idx ? "rotate(180deg)" : "rotate(0deg)",
                                transition: "transform 0.25s ease",
                              }}
                            />
                          </div>
                          <div style={{ maxHeight: openSection === idx ? 400 : 0, overflow: "hidden", transition: "max-height 0.25s ease" }}>
                            <div style={{ paddingBottom: 12, borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: 10 }}>
                              <p style={{ fontSize: 13, color: "#94A3B8", lineHeight: 1.65, margin: 0 }}>{section.content}</p>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  );
                })()}
              </div>
            </div>
          )}

          {tab === "intel" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
              {/* KPI cards */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 12 }}>
                <KpiCard label="Distress Score" value={entity.overall_score?.toFixed(1)} accent="#94A3B8" />
                <KpiCard label="Opportunity Score" value={entity.v2_overall_score?.toFixed(1) ?? "—"} accent={tierColor(entity.v2_tier)} />
                <KpiCard label="Open Roles" value={entity.open_roles_estimate ?? "—"} accent={entity.is_hiring_aggressively ? "#4ADE80" : undefined} sub={entity.is_hiring_aggressively ? "Hiring aggressively" : undefined} />
                <KpiCard label="Company State" value={entity.company_state ?? "—"} />
              </div>

              {/* CEO & hiring */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div className="ci-glass-panel" style={{ borderRadius: 12, padding: 16 }}>
                  <p style={{ fontSize: 11, color: "#64748B", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 10 }}>Leadership</p>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                    <Briefcase size={14} color="#A78BFA" />
                    <span style={{ fontSize: 13, color: "#E2E8F0", fontWeight: 500 }}>{entity.ceo_name ?? "Unknown"}</span>
                  </div>
                  {entity.ceo_appointment_date && (
                    <p style={{ fontSize: 11, color: "#64748B", display: "flex", alignItems: "center", gap: 4 }}>
                      <Clock size={10} /> Appointed {entity.ceo_appointment_date}
                    </p>
                  )}
                </div>
                <div className="ci-glass-panel" style={{ borderRadius: 12, padding: 16 }}>
                  <p style={{ fontSize: 11, color: "#64748B", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 10 }}>Hiring Signals</p>
                  {hiringRoles.length ? (
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                      {hiringRoles.map((r, i) => (
                        <span key={i} style={{ fontSize: 11, background: "rgba(34,211,238,0.1)", color: "#22D3EE", padding: "2px 8px", borderRadius: 4 }}>
                          {r}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p style={{ fontSize: 12, color: "#64748B" }}>No specific roles detected.</p>
                  )}
                </div>
              </div>

              {/* Sentiment chart */}
              <div className="ci-glass-panel" style={{ borderRadius: 12, padding: 16 }}>
                <p style={{ fontSize: 11, color: "#64748B", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 12 }}>Sentiment Evolution (6 months)</p>
                <SentimentChart trend={entity.sentiment_trend} />
              </div>
            </div>
          )}

          {tab === "erp" && <ErpBriefTab entity={entity} />}
        </div>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function CompanyIntelligence() {
  const [sector, setSector] = useState<"all" | "brand" | "insurance">("all");
  const [interventionFilter, setInterventionFilter] = useState<string>("all");
  const [sortBy, setSortBy] = useState<"score" | "name">("score");
  const [selected, setSelected] = useState<CompanyIntelligence | null>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["intelligence"],
    queryFn: () => api.intelligenceOpportunities(),
    staleTime: 30000,
  });

  const filtered = useMemo(() => {
    if (!data) return [];
    let rows = [...data];
    if (sector !== "all") rows = rows.filter(r => r.entity_type === sector);
    if (interventionFilter !== "all") rows = rows.filter(r => r.intervention_level === interventionFilter);
    if (sortBy === "name") rows.sort((a, b) => a.entity_name.localeCompare(b.entity_name));
    else rows.sort((a, b) => (b.v2_overall_score ?? b.overall_score) - (a.v2_overall_score ?? a.overall_score));
    return rows;
  }, [data, sector, interventionFilter, sortBy]);

  const kpis = useMemo(() => {
    if (!data) return {
      total: 0, immediate: 0, hiring: 0, avgScore: 0,
      automotiveCount: 0, insuranceCount: 0, tnCount: 0,
      top3Immediate: [] as string[],
      strongCount: 0, moderateCount: 0, avoidCount: 0,
    };
    const immediate = data.filter(r => r.intervention_level === "Immediate Intervention");
    const hiring = data.filter(r => r.is_hiring_aggressively).length;
    const scores = data.map(r => r.v2_overall_score ?? r.overall_score).filter(s => s != null) as number[];
    const avgScore = scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : 0;
    const automotiveCount = data.filter(r => r.entity_type === "brand").length;
    const insuranceCount = data.filter(r => r.entity_type === "insurance").length;
    const tnCount = data.filter(r => r.region === "TN" || r.entity_name.includes("TN")).length;
    const top3Immediate = immediate.slice(0, 3).map(r => r.entity_name);
    const strongCount = data.filter(r => (r.v2_overall_score ?? r.overall_score) >= 65).length;
    const moderateCount = data.filter(r => { const s = r.v2_overall_score ?? r.overall_score; return s >= 40 && s < 65; }).length;
    const avoidCount = data.filter(r => r.intervention_level === "Ignore" || r.company_state === "Survival Mode").length;
    return {
      total: data.length, immediate: immediate.length, hiring, avgScore,
      automotiveCount, insuranceCount, tnCount,
      top3Immediate, strongCount, moderateCount, avoidCount,
    };
  }, [data]);

  if (isError) {
    return (
      <div style={{ padding: 40, textAlign: "center", color: "#F87171" }}>
        <AlertTriangle size={32} style={{ margin: "0 auto 12px" }} />
        <p>Failed to load company intelligence data.</p>
      </div>
    );
  }

  return (
    <>
      <style>{CI_STYLES}</style>

      {selected && <IntelligenceModal entity={selected} onClose={() => setSelected(null)} />}

      <div style={{ padding: "24px 32px", maxWidth: 1400, margin: "0 auto" }}>
        {/* KPI row */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
          {/* Card 1 — Market Radar */}
          <div className="ci-kpi-card rounded-xl p-4 flex flex-col gap-1.5 relative overflow-hidden">
            <div className="absolute left-0 top-0 bottom-0 w-[3px] bg-teal-500 rounded-l-xl" />
            <span className="text-[10px] font-medium uppercase tracking-widest text-[var(--color-text-tertiary)]">Market Radar</span>
            <div className="flex items-center gap-2">
              <Building2 size={18} className="text-teal-500 shrink-0" />
              <span className="text-3xl font-medium leading-none text-teal-500">{isLoading ? "—" : kpis.total}</span>
            </div>
            <span className="text-sm text-[var(--color-text-secondary)] leading-snug">companies under active intelligence surveillance</span>
            <span className="text-[11px] text-[var(--color-text-tertiary)] border-t border-[var(--color-border-tertiary)] pt-1.5 mt-1">
              {isLoading ? "—" : `${kpis.automotiveCount} automotive · ${kpis.insuranceCount} insurance · ${kpis.tnCount} TN market`}
            </span>
          </div>

          {/* Card 2 — Act Now */}
          <div className="ci-kpi-card rounded-xl p-4 flex flex-col gap-1.5 relative overflow-hidden">
            <div className="absolute left-0 top-0 bottom-0 w-[3px] bg-red-500 rounded-l-xl" />
            <span className="text-[10px] font-medium uppercase tracking-widest text-[var(--color-text-tertiary)]">Act Now</span>
            <div className="flex items-center gap-2">
              <Zap size={18} className="text-red-500 shrink-0" />
              <span className="text-3xl font-medium leading-none text-red-500">{isLoading ? "—" : kpis.immediate}</span>
            </div>
            <span className="text-sm text-[var(--color-text-secondary)] leading-snug">companies in the optimal outreach window right now</span>
            <span className="text-[11px] text-[var(--color-text-tertiary)] border-t border-[var(--color-border-tertiary)] pt-1.5 mt-1">
              {isLoading ? "—" : kpis.top3Immediate.length > 0 ? `${kpis.top3Immediate.join(" · ")} — window closes in days` : "No immediate targets"}
            </span>
          </div>

          {/* Card 3 — Growth Signal */}
          <div className="ci-kpi-card rounded-xl p-4 flex flex-col gap-1.5 relative overflow-hidden">
            <div className="absolute left-0 top-0 bottom-0 w-[3px] bg-amber-500 rounded-l-xl" />
            <span className="text-[10px] font-medium uppercase tracking-widest text-[var(--color-text-tertiary)]">Growth Signal</span>
            <div className="flex items-center gap-2">
              <Users size={18} className="text-amber-500 shrink-0" />
              <span className="text-3xl font-medium leading-none text-amber-500">{isLoading ? "—" : kpis.hiring}</span>
            </div>
            <span className="text-sm text-[var(--color-text-secondary)] leading-snug">companies hiring aggressively — pain is becoming visible</span>
            <span className="text-[11px] text-[var(--color-text-tertiary)] border-t border-[var(--color-border-tertiary)] pt-1.5 mt-1">
              Hiring surge = budget opening + operational pressure
            </span>
          </div>

          {/* Card 4 — Opportunity Health */}
          <div className="ci-kpi-card rounded-xl p-4 flex flex-col gap-1.5 relative overflow-hidden">
            <div className="absolute left-0 top-0 bottom-0 w-[3px] bg-purple-500 rounded-l-xl" />
            <span className="text-[10px] font-medium uppercase tracking-widest text-[var(--color-text-tertiary)]">Opportunity Health</span>
            <div className="flex items-center gap-2">
              <Activity size={18} className="text-purple-500 shrink-0" />
              <span className="text-3xl font-medium leading-none text-purple-500">{isLoading ? "—" : kpis.avgScore.toFixed(1)}</span>
            </div>
            <span className="text-sm text-[var(--color-text-secondary)] leading-snug">average opportunity score across all tracked entities</span>
            <span className="text-[11px] text-[var(--color-text-tertiary)] border-t border-[var(--color-border-tertiary)] pt-1.5 mt-1">
              {isLoading ? "—" : `${kpis.strongCount} strong ≥65 · ${kpis.moderateCount} moderate · ${kpis.avoidCount} avoid — Opportunity Score where available, Distress Score otherwise`}
            </span>
          </div>
        </div>

        {/* Filter bar */}
        <div style={{ display: "flex", gap: 10, marginBottom: 18, flexWrap: "wrap", alignItems: "center" }}>
          {/* Sector */}
          <div className="ci-glass-panel" style={{ display: "flex",  borderRadius: 8, overflow: "hidden" }}>
            {(["all", "brand", "insurance"] as const).map(s => (
              <button
                key={s}
                onClick={() => setSector(s)}
                style={{
                  padding: "6px 14px", fontSize: 12, fontWeight: 500, border: "none", cursor: "pointer",
                  background: sector === s ? "#1E293B" : "transparent",
                  color: sector === s ? "#F1F5F9" : "#64748B",
                  transition: "all 0.15s",
                }}
              >
                {s === "all" ? "All Sectors" : s === "brand" ? "Automotive" : "Insurance"}
              </button>
            ))}
          </div>

          {/* Intervention */}
          <select
            value={interventionFilter}
            onChange={e => setInterventionFilter(e.target.value)}
            className="ci-glass-panel" style={{ borderRadius: 8, color: "#94A3B8", padding: "6px 12px", fontSize: 12 }}
          >
            <option value="all">All Interventions</option>
            <option value="heavy">Heavy</option>
            <option value="medium">Medium</option>
            <option value="light">Light</option>
          </select>

          {/* Sort */}
          <select
            value={sortBy}
            onChange={e => setSortBy(e.target.value as "score" | "name")}
            className="ci-glass-panel" style={{ borderRadius: 8, color: "#94A3B8", padding: "6px 12px", fontSize: 12 }}
          >
            <option value="score">Sort: Score</option>
            <option value="name">Sort: Name</option>
          </select>

          <span style={{ fontSize: 12, color: "#64748B", marginLeft: "auto" }}>
            {isLoading ? "Loading..." : `${filtered.length} entities`}
          </span>
        </div>

        {/* Table */}
        <div className="ci-glass-panel" style={{ borderRadius: 14, overflow: "hidden", paddingBottom: 12 }}>
          <div style={{ overflowX: "auto" }}>
          {/* Header */}
          <div style={{
            display: "grid",
            gridTemplateColumns: "2.5fr 1.2fr 2.5fr 0.8fr 1fr 1fr 1.2fr 1fr 2.8fr 1fr 40px",
            minWidth: 1200,
            gap: 12,
            padding: "16px 24px",
            background: "transparent",
            borderBottom: "1px solid #1E293B",
            marginBottom: 8,
          }}>
            {["Company", "State", "Core Pain", "Trend", "Opp. Score", "Tier", "Action", "Timing", "Offer", "Confidence", ""].map((h, i) => (
              <span key={i} style={{ fontSize: 10, color: "#64748B", textTransform: "uppercase", letterSpacing: "0.08em", fontWeight: 600 }}>{h}</span>
            ))}
          </div>

          {/* Rows */}
          {isLoading ? (
            <div style={{ padding: 40, textAlign: "center", color: "#64748B", fontSize: 13 }}>Loading intelligence data…</div>
          ) : filtered.length === 0 ? (
            <div style={{ padding: 40, textAlign: "center", color: "#64748B", fontSize: 13 }}>No entities match the current filters.</div>
          ) : (
            filtered.map((r, index) => {
              const complaints = r.top_complaint_types ?? [];
              const topPain = complaints.length > 0 ? complaints[0] : tierPainLabel(r.v2_tier);
              const evidenceStrength = (r.v2_reasoning?.data_quality as { evidence_strength?: string } | undefined)?.evidence_strength;
              const confidencePct = evidenceStrengthPct(evidenceStrength);
              const offer = suggestedOfferLabel(r.company_state, complaints[0] ?? null);

              return (
                <div
                  key={r.entity_id}
                  className="ci-table-row"
                  onClick={() => setSelected(r)}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "2.5fr 1.2fr 2.5fr 0.8fr 1fr 1fr 1.2fr 1fr 2.8fr 1fr 40px",
                    minWidth: 1200,
                    gap: 12,
                    padding: "14px 16px",
                    margin: "0 8px 8px 8px",
                    
                    borderRadius: 10,
                    alignItems: "center",
                    animationDelay: `${index * 0.04}s`,
                  }}
                >
                  {/* Company */}
                  <div>
                    <p style={{ fontSize: 13, fontWeight: 600, color: "#E2E8F0", marginBottom: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {r.entity_name}
                    </p>
                    <p style={{ fontSize: 10, color: "#64748B" }}>{r.region ?? "—"} · {r.entity_type === "brand" ? "Auto" : "Ins."}</p>
                  </div>

                  {/* State */}
                  <span style={{ fontSize: 11, color: r.company_state ? "#94A3B8" : "#475569", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", paddingRight: 6 }}>
                    {r.company_state ?? "—"}
                  </span>

                  {/* Core pain — fallback to tier label if no complaints */}
                  <span style={{ fontSize: 12, color: complaints.length > 0 ? "#94A3B8" : "#64748B", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", paddingRight: 8, fontStyle: complaints.length > 0 ? "normal" : "italic" }}>
                    {topPain}
                  </span>

                  {/* Trend */}
                  <div style={{ display: "flex", alignItems: "center" }}>
                    {getTrendIcon(r.trend_direction ?? (r as unknown as { score_reasoning?: { trend?: { direction?: string } } }).score_reasoning?.trend?.direction)}
                  </div>

                  {/* Score */}
                  <span style={{ display: "flex", alignItems: "baseline", gap: 3 }}>
                    <span style={{ fontSize: 13, fontWeight: 700, color: tierColor(r.v2_tier) }}>
                      {r.v2_overall_score?.toFixed(1) ?? r.overall_score.toFixed(1)}
                    </span>
                    {r.v2_overall_score != null
                      ? <span className="text-[10px] text-purple-400 font-medium">V2</span>
                      : <span className="text-[10px] text-gray-500 font-medium">V1</span>
                    }
                  </span>

                  {/* Tier */}
                  {r.v2_tier ? (
                    <span style={{ fontSize: 10, fontWeight: 600, color: tierColor(r.v2_tier), background: tierBg(r.v2_tier), padding: "2px 6px", borderRadius: 4, display: "inline-block" }}>
                      {r.v2_tier.toUpperCase()}
                    </span>
                  ) : <span style={{ fontSize: 11, color: "#475569" }}>—</span>}

                  {/* Intervention level */}
                  <span style={{ fontSize: 11, fontWeight: 500, color: interventionColor(r.intervention_level) }}>
                    {r.intervention_level ?? "—"}
                  </span>

                  {/* Outreach timing */}
                  <span style={{ fontSize: 11, fontWeight: 500, color: timingColor(r.outreach_timing) }}>
                    {r.outreach_timing ?? "—"}
                  </span>

                  {/* Suggested offer */}
                  <span title={offer} style={{ fontSize: 11, color: "#64748B", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{offer}</span>

                  {/* Confidence — as % */}
                  <span style={{ fontSize: 12, fontWeight: 700, color: "#F1F5F9" }}>{confidencePct}</span>

                  {/* Chevron */}
                  <ChevronRight size={14} color="#334155" />
                </div>
              );
            })
          )}
          </div>{/* end scroll wrapper */}
        </div>
      </div>
    </>
  );
}
