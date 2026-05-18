import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { Brain, Target, Activity, MapPin, Bot, ArrowRight, Zap, Flame, Sparkles } from "lucide-react";

// ── Styles ────────────────────────────────────────────────────────────────────

const STYLES = `
  @keyframes nb-fadeUp {
    from { opacity: 0; transform: translateY(30px) scale(0.95); }
    to   { opacity: 1; transform: translateY(0) scale(1); }
  }
  @keyframes nb-pulse {
    0%, 100% { opacity: 1; filter: drop-shadow(0 0 8px rgba(74,222,128,0.8)); }
    50%       { opacity: 0.5; filter: drop-shadow(0 0 2px rgba(74,222,128,0.3)); }
  }
  @keyframes nb-ticker {
    from { transform: translateX(0); }
    to   { transform: translateX(-50%); }
  }
  @keyframes spin3d {
    0% { transform: rotateX(0deg) rotateY(0deg); }
    100% { transform: rotateX(360deg) rotateY(360deg); }
  }
  @keyframes float {
    0%, 100% { transform: translateY(0px); }
    50% { transform: translateY(-10px); }
  }
  @keyframes glow-shift {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
  }
  
  .nb-fade-up  { animation: nb-fadeUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) both; }
  .nb-live-dot { animation: nb-pulse 2s infinite; display: block; width: 10px; height: 10px; border-radius: 50%; background: #4ADE80; box-shadow: 0 0 10px #4ADE80; }
  .nb-ticker   { animation: nb-ticker 45s linear infinite; display: flex; width: max-content; }
  
  .nb-card { 
    transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275); 
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
  }
  .nb-card:hover { 
    transform: translateY(-8px) scale(1.02) rotateX(2deg) rotateY(-2deg); 
    box-shadow: 0 20px 40px rgba(0,0,0,0.4), 0 0 20px rgba(127,119,221,0.3);
  }
  
  .nb-story-row { 
    transition: all 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94); 
    backdrop-filter: blur(12px);
  }
  .nb-story-row:hover { 
    transform: translateX(10px) scale(1.01); 
    border-color: rgba(255,255,255,0.3) !important; 
    background: rgba(30,41,59,0.9) !important;
    box-shadow: -5px 5px 15px rgba(0,0,0,0.2);
  }
  
  .nb-nav-tile  { 
    transition: all 0.3s ease; 
    cursor: pointer; 
    backdrop-filter: blur(12px);
  }
  .nb-nav-tile:hover { 
    transform: translateY(-5px) scale(1.05); 
    background: rgba(30,41,59,0.95) !important;
    border-color: rgba(167,139,250,0.4) !important;
    box-shadow: 0 10px 25px rgba(167,139,250,0.15);
  }
  
  .nb-skel { background: linear-gradient(90deg, rgba(30,41,59,0.5) 25%, rgba(51,65,85,0.5) 50%, rgba(30,41,59,0.5) 75%); animation: nb-pulse 1.5s infinite; border-radius: 16px; }

  .text-glow {
    text-shadow: 0 0 20px rgba(255,255,255,0.3);
  }
  
  .gradient-text {
    background: linear-gradient(270deg, #A78BFA, #60A5FA, #34D399, #A78BFA);
    background-size: 300% 300%;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    animation: glow-shift 6s ease infinite;
  }
`;

// ── Helpers ───────────────────────────────────────────────────────────────────

function daysSince(dateStr: string | null): number | null {
  if (!dateStr) return null;
  return Math.floor((Date.now() - new Date(dateStr).getTime()) / 86_400_000);
}

function scoreColor(score: number): string {
  if (score >= 75) return "#1D9E75";
  if (score >= 60) return "#E24B4A";
  return "#7F77DD";
}

function signalColor(type: string | null): { fg: string; bg: string } {
  switch (type) {
    case "leadership_change":     return { fg: "#A78BFA", bg: "rgba(167,139,250,0.15)" };
    case "hiring_signal":         return { fg: "#F59E0B", bg: "rgba(245,158,11,0.12)" };
    case "digital_initiative":    return { fg: "#60A5FA", bg: "rgba(96,165,250,0.12)" };
    case "strategy_announcement": return { fg: "#4ADE80", bg: "rgba(74,222,128,0.12)" };
    case "risk_signal":           return { fg: "#F87171", bg: "rgba(248,113,113,0.12)" };
    case "partnership":           return { fg: "#2DD4BF", bg: "rgba(45,212,191,0.12)" };
    default:                      return { fg: "#94A3B8", bg: "rgba(148,163,184,0.1)" };
  }
}

function Tag({ label, fg, bg }: { label: string; fg: string; bg: string }) {
  return (
    <span style={{ borderRadius: 20, padding: "4px 10px", fontSize: 11, color: fg, background: bg, fontWeight: 500, whiteSpace: "nowrap" as const }}>
      {label}
    </span>
  );
}

function ScoreRing({ score, color }: { score: number; color: string }) {
  const CIRC = 169.65;
  const offset = CIRC * (1 - score / 100);
  return (
    <svg width="64" height="64" viewBox="0 0 64 64" style={{ transform: "rotate(-90deg)", flexShrink: 0 }}>
      <circle cx="32" cy="32" r="27" fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth="5" />
      <circle cx="32" cy="32" r="27" fill="none" stroke={color} strokeWidth="5"
        strokeDasharray={CIRC} strokeDashoffset={offset} strokeLinecap="round" />
      <text x="32" y="32" textAnchor="middle" dominantBaseline="central"
        style={{ transform: "rotate(90deg)", transformOrigin: "32px 32px" }}
        fill={color} fontSize="14" fontWeight="500">
        {Math.round(score)}
      </text>
    </svg>
  );
}

function Cube({ score }: { score: number }) {
  const face: React.CSSProperties = {
    position: "absolute", width: 64, height: 64,
    display: "flex", alignItems: "center", justifyContent: "center",
    background: "rgba(127,119,221,0.15)", border: "2px solid rgba(127,119,221,0.8)", 
    color: "#E2E8F0", fontSize: 14, fontWeight: 800, borderRadius: 8, 
    backfaceVisibility: "hidden", backdropFilter: "blur(4px)",
    boxShadow: "inset 0 0 15px rgba(127,119,221,0.4), 0 0 10px rgba(127,119,221,0.2)"
  };
  const faces = [
    { text: String(Math.round(score)),  t: "rotateY(0deg)    translateZ(32px)" },
    { text: "🚀",                       t: "rotateY(90deg)   translateZ(32px)" },
    { text: "VIBE",                     t: "rotateY(180deg)  translateZ(32px)" },
    { text: "OPP",                      t: "rotateY(270deg)  translateZ(32px)" },
    { text: "ERP",                      t: "rotateX(90deg)   translateZ(32px)" },
    { text: "✨",                       t: "rotateX(-90deg)  translateZ(32px)" },
  ];
  return (
    <div style={{ perspective: 800, animation: "float 4s ease-in-out infinite" }}>
      <div style={{ width: 64, height: 64, position: "relative", transformStyle: "preserve-3d", animation: "spin3d 8s cubic-bezier(0.4, 0, 0.2, 1) infinite" }}>
        {faces.map((f, i) => (
          <div key={i} style={{ ...face, transform: f.t }}>{f.text}</div>
        ))}
      </div>
    </div>
  );
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function NarrativeBrief() {
  const navigate = useNavigate();

  const { data, isLoading, isError } = useQuery({
    queryKey: ["intelligence"],
    queryFn: api.intelligenceOpportunities,
    staleTime: 30000,
  });

  const { data: summary } = useQuery({
    queryKey: ["dashboardSummary"],
    queryFn: api.dashboardSummary,
    staleTime: 30000,
  });

  const computed = useMemo(() => {
    if (!data) return null;

    const immediate = [...data]
      .filter(e => e.intervention_level === "Immediate Intervention")
      .sort((a, b) => (b.v2_overall_score ?? b.overall_score) - (a.v2_overall_score ?? a.overall_score));

    const hiringCount = data.filter(e => e.is_hiring_aggressively).length;
    const strongCount = data.filter(e => (e.v2_overall_score ?? e.overall_score) >= 65).length;
    const topPick = immediate[0] ?? null;
    const storyCards = immediate.slice(1, 4);

    type TickerItem = { signal_type: string | null; headline: string | null; entity_name: string };
    const allSignals: TickerItem[] = [];
    for (const e of data) {
      for (const s of e.recent_signals) {
        if (s.headline) allSignals.push({ signal_type: s.signal_type, headline: s.headline, entity_name: e.entity_name });
      }
    }
    allSignals.sort((a, b) => 0); // preserve API order (already newest-first per entity)
    const tickerItems = allSignals.slice(0, 8);

    return { immediate, hiringCount, strongCount, topPick, storyCards, tickerItems };
  }, [data]);

  const todayLabel = new Date().toLocaleDateString("en-US", {
    weekday: "short", month: "short", day: "numeric", year: "numeric",
  });

  const totalCount = data?.length ?? 76;

  return (
    <div style={{ padding: "28px 40px", maxWidth: 1300, margin: "0 auto", display: "flex", flexDirection: "column", gap: 32 }}>
      <style>{STYLES}</style>

      {/* ── Loading skeleton ────────────────────────────────────────────── */}
      {isLoading && (
        <>
          <div className="nb-skel" style={{ height: 120 }} />
          <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 16 }}>
            <div className="nb-skel" style={{ height: 280 }} />
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {[0, 1, 2].map(i => <div key={i} className="nb-skel" style={{ height: 80 }} />)}
            </div>
          </div>
          <div className="nb-skel" style={{ height: 44 }} />
          <div style={{ display: "grid", gridTemplateColumns: "repeat(5,1fr)", gap: 12 }}>
            {[0,1,2,3,4].map(i => <div key={i} className="nb-skel" style={{ height: 90 }} />)}
          </div>
        </>
      )}

      {/* ── Error ───────────────────────────────────────────────────────── */}
      {isError && (
        <div style={{ padding: 40, textAlign: "center", color: "#F87171" }}>
          <p style={{ fontSize: 14 }}>Failed to load intelligence data. Check the API server.</p>
        </div>
      )}

      {/* ── Main content ────────────────────────────────────────────────── */}
      {!isLoading && !isError && computed && (() => {
        const { immediate, hiringCount, strongCount, topPick, storyCards, tickerItems } = computed;

        return (
          <>
            {/* ── Section 1: Hero ──────────────────────────────────────── */}
            <section 
              className="nb-fade-up" 
              style={{ 
                animationDelay: "0s", 
                padding: "40px", 
                borderRadius: "24px", 
                position: "relative", 
                overflow: "hidden",
                border: "1px solid rgba(255,255,255,0.08)",
                boxShadow: "0 25px 50px -12px rgba(0,0,0,0.5)"
              }}
            >
              {/* Abstract 3D Cyber Fluid Mesh Background */}
              <div style={{
                position: "absolute",
                top: 0, left: 0, right: 0, bottom: 0,
                backgroundImage: "url(/bg_fluid.png)",
                backgroundSize: "cover",
                backgroundPosition: "center",
                opacity: 0.35,
                zIndex: 0,
                mixBlendMode: "screen",
                filter: "brightness(1.2) contrast(1.1)"
              }} />
              <div style={{
                position: "absolute",
                top: 0, left: 0, right: 0, bottom: 0,
                background: "linear-gradient(to right, rgba(10,15,30,0.9) 0%, rgba(10,15,30,0.4) 100%)",
                zIndex: 0
              }} />

              <div style={{ position: "relative", zIndex: 1 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 20 }}>
                  <span className="nb-live-dot" />
                  <span style={{ fontSize: 13, color: "#94A3B8", fontWeight: 600, letterSpacing: "0.05em", textTransform: "uppercase" }}>
                    Vibe Check · {todayLabel} · {totalCount} Targets
                  </span>
                </div>

                <h1 className="text-glow" style={{ fontSize: 42, fontWeight: 700, color: "#F1F5F9", lineHeight: 1.15, marginBottom: 18, letterSpacing: "-1px" }}>
                  <span className="gradient-text">{immediate.length} companies</span> are about to <br/>pop off in their optimal window.
                </h1>

                <p style={{ fontSize: 16, color: "#CBD5E1", lineHeight: 1.7, maxWidth: 650, fontWeight: 400 }}>
                  {immediate[0] && (
                    <>Fresh blood at the top: <span style={{ color: "#fff", fontWeight: 600 }}>{immediate[0].entity_name}</span> has a new CEO — the window is closing fast.{" "}</>
                  )}
                  {immediate[1] && (
                    <><span style={{ color: "#fff", fontWeight: 600 }}>{immediate[1].entity_name}</span> is aggressively scaling ({immediate[1].open_roles_estimate ?? "massive hiring"}).{" "}</>
                  )}
                  {immediate[2] && (
                    <><span style={{ color: "#fff", fontWeight: 600 }}>{immediate[2].entity_name}</span> just shipped AI features.{" "}</>
                  )}
                  <br/><span style={{ color: "#34D399", fontWeight: 600, display: "inline-flex", alignItems: "center", gap: 6, marginTop: 8 }}><Flame size={18} /> {hiringCount} companies are ready to talk.</span>
                </p>
              </div>
            </section>

            {/* ── Section 2: Featured band ─────────────────────────────── */}
            <section
              className="nb-fade-up"
              style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 20, animationDelay: "0.1s" }}
            >
              {/* LEFT — top pick */}
              {topPick ? (
                <div
                  className="nb-card"
                  style={{
                    background: "rgba(15,23,42,0.6)",
                    border: "1px solid rgba(175,169,236,0.3)",
                    borderRadius: 24, padding: 36, position: "relative", overflow: "hidden",
                  }}
                >
                  <div style={{
                    position: "absolute",
                    top: 0, left: 0, right: 0, bottom: 0,
                    backgroundImage: "url(/bg_topo.png)",
                    backgroundSize: "cover",
                    backgroundPosition: "center",
                    opacity: 0.15,
                    zIndex: 0,
                    mixBlendMode: "screen",
                  }} />
                  <div style={{ position: "relative", zIndex: 1 }}>
                    <div style={{ position: "absolute", top: 10, right: 10 }}>
                      <Cube score={topPick.v2_overall_score ?? topPick.overall_score} />
                    </div>

                    <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12, color: "#AFA9EC", textTransform: "uppercase", letterSpacing: "0.15em", fontWeight: 700, background: "rgba(175,169,236,0.15)", padding: "4px 12px", borderRadius: 20 }}>
                      <Zap size={14} fill="#AFA9EC" /> Top Alpha Pick
                    </span>

                    <h2 style={{ fontSize: 32, fontWeight: 700, color: "#F1F5F9", margin: "16px 0 16px", paddingRight: 90, lineHeight: 1.15, textShadow: "0 2px 10px rgba(0,0,0,0.5)" }}>
                      {topPick.entity_name}
                    </h2>

                  <p style={{ fontSize: 15, color: "#94A3B8", lineHeight: 1.7, marginBottom: 28 }}>
                    {topPick.ceo_name
                      ? <>The CEO hot seat just changed. <span style={{ color: "#E2E8F0", fontWeight: 500 }}>{topPick.ceo_name}</span> is {daysSince(topPick.ceo_appointment_date) ?? "?"} days in. The time to pitch is literally right now.{" "}</>
                      : topPick.recent_signals[0]?.headline
                        ? <><span style={{ color: "#E2E8F0", fontWeight: 500 }}>Spill:</span> {topPick.recent_signals[0].headline}.{" "}</>
                        : null
                    }
                    {topPick.top_complaint_types?.[0] && (
                      <>Also, <span style={{ color: "#F87171", fontWeight: 500 }}>{topPick.top_complaint_types[0]}</span> is causing massive friction in their dealer network.</>
                    )}
                  </p>

                  <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 32 }}>
                    {topPick.top_complaint_types?.[0] && (
                      <Tag label={topPick.top_complaint_types[0].slice(0, 22)} fg="#FCA5A5" bg="rgba(248,113,113,0.15)" />
                    )}
                    {topPick.top_complaint_types?.[1] && (
                      <Tag label={topPick.top_complaint_types[1].slice(0, 22)} fg="#FCD34D" bg="rgba(245,158,11,0.15)" />
                    )}
                    {topPick.ceo_appointment_date && (
                      <Tag
                        label={`Fresh CEO Drop · ${new Date(topPick.ceo_appointment_date).toLocaleDateString("en-US", { month: "short", year: "numeric" })}`}
                        fg="#C4B5FD" bg="rgba(167,139,250,0.2)"
                      />
                    )}
                    <Tag label={`Recovery Check ${Math.round(topPick.v2_recovery_score ?? 0)}%`} fg="#86EFAC" bg="rgba(74,222,128,0.15)" />
                  </div>

                  <div style={{ display: "flex", gap: 12 }}>
                    <button
                      onClick={() => navigate("/company-intelligence")}
                      style={{
                        background: "linear-gradient(135deg, #7F77DD, #A78BFA)", border: "none", borderRadius: 12,
                        padding: "12px 24px", fontSize: 14, fontWeight: 700, color: "#fff", cursor: "pointer",
                        transition: "all 0.3s ease", boxShadow: "0 4px 15px rgba(127,119,221,0.4)",
                        display: "flex", alignItems: "center", gap: 8
                      }}
                      onMouseEnter={e => { e.currentTarget.style.transform = "translateY(-2px)"; e.currentTarget.style.boxShadow = "0 8px 25px rgba(127,119,221,0.6)"; }}
                      onMouseLeave={e => { e.currentTarget.style.transform = "translateY(0)"; e.currentTarget.style.boxShadow = "0 4px 15px rgba(127,119,221,0.4)"; }}
                    >
                      <Zap size={16} fill="white" /> Enter Briefing
                    </button>
                    <button
                      onClick={() => navigate("/company-intelligence")}
                      style={{
                        background: "rgba(175,169,236,0.1)", border: "1px solid rgba(175,169,236,0.4)",
                        borderRadius: 12, padding: "12px 24px", fontSize: 14, fontWeight: 600,
                        color: "#E2E8F0", cursor: "pointer", transition: "all 0.3s ease",
                        backdropFilter: "blur(10px)"
                      }}
                      onMouseEnter={e => { e.currentTarget.style.background = "rgba(175,169,236,0.2)"; e.currentTarget.style.borderColor = "#AFA9EC"; }}
                      onMouseLeave={e => { e.currentTarget.style.background = "rgba(175,169,236,0.1)"; e.currentTarget.style.borderColor = "rgba(175,169,236,0.4)"; }}
                    >
                      Full Dossier
                    </button>
                  </div>
                  </div>
                </div>
              ) : (
                <div style={{
                  background: "rgba(15,23,42,0.6)", border: "1px solid rgba(255,255,255,0.06)",
                  borderRadius: 20, padding: 28, display: "flex", alignItems: "center", justifyContent: "center",
                }}>
                  <p style={{ color: "#475569", fontSize: 14 }}>No immediate targets.</p>
                </div>
              )}

              {/* RIGHT — 3 story rows + see all */}
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {storyCards.map((e, i) => {
                  const score = e.v2_overall_score ?? e.overall_score;
                  const color = scoreColor(score);
                  const hook = e.recent_signals[0]?.headline ?? e.key_hiring_roles ?? e.company_state ?? "—";
                  return (
                    <div
                      key={i}
                      className="nb-story-row"
                      onClick={() => navigate("/company-intelligence")}
                      style={{
                        background: "rgba(15,23,42,0.45)",
                        border: "1px solid rgba(255,255,255,0.08)",
                        borderRadius: 16, padding: "16px 20px",
                        display: "flex", alignItems: "center", gap: 16, cursor: "pointer",
                        position: "relative", overflow: "hidden"
                      }}
                    >
                      <div style={{
                        position: "absolute", left: 0, top: 0, bottom: 0, width: "4px",
                        background: color, boxShadow: `0 0 10px ${color}`
                      }} />
                      <ScoreRing score={score} color={color} />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <p style={{ fontSize: 16, fontWeight: 700, color: "#F1F5F9", marginBottom: 4 }}>{e.entity_name}</p>
                        <p style={{ fontSize: 13, color: "#94A3B8", marginBottom: 10, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {String(hook).slice(0, 75)}
                        </p>
                        <div style={{ display: "flex", gap: 8 }}>
                          {e.company_state && (
                            <Tag label={e.company_state.slice(0, 20)} fg="#CBD5E1" bg="rgba(203,213,225,0.15)" />
                          )}
                          {e.outreach_timing && (
                            <Tag label={e.outreach_timing} fg="#86EFAC" bg="rgba(74,222,128,0.15)" />
                          )}
                        </div>
                      </div>
                      <ArrowRight size={18} style={{ color: "#64748B", flexShrink: 0 }} />
                    </div>
                  );
                })}

                {storyCards.length === 0 && (
                  <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
                    <p style={{ color: "#334155", fontSize: 13 }}>No additional targets.</p>
                  </div>
                )}

                <button
                  onClick={() => navigate("/company-intelligence")}
                  style={{
                    background: "rgba(255,255,255,0.03)", border: "1px dashed rgba(255,255,255,0.15)",
                    borderRadius: 12, padding: "12px 16px", fontSize: 14, fontWeight: 600,
                    color: "#94A3B8", cursor: "pointer", marginTop: 8,
                    transition: "all 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94)",
                  }}
                  onMouseEnter={e => { e.currentTarget.style.color = "#F1F5F9"; e.currentTarget.style.borderColor = "rgba(167,139,250,0.6)"; e.currentTarget.style.background = "rgba(167,139,250,0.1)"; e.currentTarget.style.transform = "translateY(-2px)"; }}
                  onMouseLeave={e => { e.currentTarget.style.color = "#94A3B8"; e.currentTarget.style.borderColor = "rgba(255,255,255,0.15)"; e.currentTarget.style.background = "rgba(255,255,255,0.03)"; e.currentTarget.style.transform = "translateY(0)"; }}
                >
                  Explore all {totalCount} radar hits ⚡
                </button>
              </div>
            </section>

            {/* ── Section 3: Ticker ────────────────────────────────────── */}
            {tickerItems.length > 0 && (
              <section
                className="nb-fade-up"
                style={{
                  borderTop: "1px solid rgba(255,255,255,0.06)",
                  borderBottom: "1px solid rgba(255,255,255,0.06)",
                  padding: "12px 0", overflow: "hidden", animationDelay: "0.35s",
                }}
              >
                <div className="nb-ticker">
                  {[...tickerItems, ...tickerItems].map((s, i) => {
                    const { fg, bg } = signalColor(s.signal_type);
                    const line = s.headline?.slice(0, 60) ?? "";
                    return (
                      <span key={i} style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "0 24px" }}>
                        <span style={{ fontSize: 11, fontWeight: 600, color: fg, background: bg, borderRadius: 20, padding: "3px 8px", flexShrink: 0 }}>
                          {s.entity_name}
                        </span>
                        <span style={{ fontSize: 12, color: "#64748B" }}>{line}</span>
                        <span style={{ color: "#1E293B", fontSize: 16, fontWeight: 300, flexShrink: 0 }}>·</span>
                      </span>
                    );
                  })}
                </div>
              </section>
            )}

            {/* ── Section 4: Nav shelf ─────────────────────────────────── */}
            <section
              className="nb-fade-up"
              style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 12, animationDelay: "0.45s" }}
            >
              {[
                {
                  icon: <Brain size={26} style={{ color: "#A78BFA", filter: "drop-shadow(0 0 8px rgba(167,139,250,0.6))" }} />,
                  label: "Prospect Strategy",
                  sub: `${immediate.length} hot targets`,
                  path: "/company-intelligence",
                },
                {
                  icon: <Target size={26} style={{ color: "#4ADE80", filter: "drop-shadow(0 0 8px rgba(74,222,128,0.6))" }} />,
                  label: "Companies in Crisis",
                  sub: `${strongCount} high match`,
                  path: "/company",
                },
                {
                  icon: <Activity size={26} style={{ color: "#F59E0B", filter: "drop-shadow(0 0 8px rgba(245,158,11,0.6))" }} />,
                  label: "Sources & Connections",
                  sub: `${(summary?.total_articles ?? 0).toLocaleString()} signals`,
                  path: "/market",
                },
                {
                  icon: <MapPin size={26} style={{ color: "#FB7185", filter: "drop-shadow(0 0 8px rgba(251,113,133,0.6))" }} />,
                  label: "Trends & Forums",
                  sub: "Global view",
                  path: "/field-intel",
                },
                {
                  icon: <Sparkles size={26} style={{ color: "#60A5FA", filter: "drop-shadow(0 0 8px rgba(96,165,250,0.6))" }} />,
                  label: "AI Analyst",
                  sub: "Spill the tea",
                  path: "/analyst",
                },
              ].map((tile, i) => (
                <div
                  key={i}
                  className="nb-nav-tile nb-card"
                  onClick={() => navigate(tile.path)}
                  style={{
                    background: "rgba(15,23,42,0.8)",
                    border: "1px solid rgba(255,255,255,0.06)",
                    borderRadius: 16, padding: "18px 16px",
                    display: "flex", flexDirection: "column", gap: 10, alignItems: "flex-start",
                  }}
                >
                  {tile.icon}
                  <div>
                    <p style={{ fontSize: 13, fontWeight: 600, color: "#E2E8F0", marginBottom: 3 }}>{tile.label}</p>
                    <p style={{ fontSize: 12, color: "#475569" }}>{tile.sub}</p>
                  </div>
                </div>
              ))}
            </section>
          </>
        );
      })()}
    </div>
  );
}
