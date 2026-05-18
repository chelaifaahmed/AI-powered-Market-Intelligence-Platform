import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  ScatterChart, Scatter, XAxis, YAxis, ZAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
  ReferenceArea, BarChart, Bar, Legend, LabelList, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar
} from "recharts";
import { Target, Users, Shield, Zap, AlertTriangle, Building, Globe, CheckCircle2, ChevronRight, Briefcase, Activity, BarChart2, Layers } from "lucide-react";

const API = import.meta.env.VITE_API_URL || "";

// Colors
const TIER_COLORS: Record<string, string> = {
  "Tier 1 Global": "#6366F1", // Indigo
  "Tier 2 Regional": "#F59E0B", // Amber
  "Tier 3 Local/Boutique": "#10B981", // Emerald
  "Niche Specialist": "#EC4899", // Pink
};

const CATEGORICAL_COLORS = ["#38BDF8", "#A78BFA", "#F472B6", "#FBBF24", "#FB923C", "#F87171", "#94A3B8", "#E879F9", "#4ADE80", "#2DD4BF"];

// Radar Data (Original)
const radarData = [
  { subject: "Automotive/Lease Fit", teamwill: 10, marketAvg: 6 },
  { subject: "Insurance Core Fit", teamwill: 8, marketAvg: 7 },
  { subject: "Enterprise Scale", teamwill: 8, marketAvg: 9 },
  { subject: "SME Suitability", teamwill: 7, marketAvg: 6 },
  { subject: "MENA/Africa Adoption", teamwill: 9, marketAvg: 4 },
];

// Tooltips
const ERPScatterTooltip = ({ active, payload }: any) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div style={{ background: "rgba(15,23,42,0.95)", border: `1px solid ${data.is_teamwill_certified ? '#10B981' : 'rgba(255,255,255,0.2)'}`, borderRadius: "12px", padding: "16px", minWidth: "220px", backdropFilter: "blur(12px)", boxShadow: "0 10px 25px rgba(0,0,0,0.5)" }}>
        <h4 style={{ color: "#F9FAFB", margin: "0 0 8px 0", fontSize: "16px", fontWeight: "bold", display: "flex", alignItems: "center", gap: "6px" }}>
          {data.is_teamwill_certified && <CheckCircle2 size={16} color="#10B981" />}
          {data.erp_name}
        </h4>
        <p style={{ color: "#9CA3AF", fontSize: "12px", margin: "0 0 4px 0" }}><strong>Vendor:</strong> {data.vendor}</p>
        <p style={{ color: "#9CA3AF", fontSize: "12px", margin: "0 0 4px 0" }}><strong>Auto Fit:</strong> {data.automotive_fit_score}/10</p>
        <p style={{ color: "#9CA3AF", fontSize: "12px", margin: "0 0 4px 0" }}><strong>Insurance Fit:</strong> {data.insurance_fit_score}/10</p>
        {data.is_teamwill_certified && (
          <div style={{ marginTop: "12px", padding: "6px 10px", background: "rgba(16,185,129,0.2)", borderRadius: "6px", color: "#6EE7B7", fontSize: "11px", fontWeight: "bold" }}>
            ⭐ Certified Teamwill Partner
          </div>
        )}
      </div>
    );
  }
  return null;
};

const CompScatterTooltip = ({ active, payload }: any) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    if (data.is_teamwill) {
      return (
        <div style={{ background: "rgba(15,23,42,0.95)", border: "1px solid #818CF8", borderRadius: "12px", padding: "16px", minWidth: "240px", backdropFilter: "blur(12px)", boxShadow: "0 10px 25px rgba(0,0,0,0.5), 0 0 15px rgba(99,102,241,0.3)" }}>
          <h4 style={{ color: "#F9FAFB", margin: "0 0 8px 0", fontSize: "16px", fontWeight: "bold", display: "flex", alignItems: "center", gap: "6px" }}>
            <Zap size={16} color="#818CF8" /> TEAMWILL
          </h4>
          <p style={{ color: "#9CA3AF", fontSize: "12px", margin: "0 0 4px 0" }}><strong>Revenue:</strong> €100M+</p>
          <p style={{ color: "#9CA3AF", fontSize: "12px", margin: "0 0 4px 0" }}><strong>Focus:</strong> 100% Asset & Credit Finance</p>
        </div>
      );
    }

    return (
      <div style={{ background: "rgba(15,23,42,0.95)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "12px", padding: "16px", minWidth: "260px", backdropFilter: "blur(12px)", boxShadow: "0 10px 25px rgba(0,0,0,0.5)" }}>
        <h4 style={{ color: "#F9FAFB", margin: "0 0 8px 0", fontSize: "16px", fontWeight: "bold" }}>{data.company_name}</h4>
        <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "12px" }}>
          <span style={{ padding: "3px 10px", background: "rgba(255,255,255,0.1)", borderRadius: "12px", fontSize: "10px", color: "#CBD5E1", fontWeight: "bold", textTransform: "uppercase" }}>{data.competitor_tier}</span>
          {data.is_high_threat && <span style={{ padding: "3px 10px", background: "rgba(239,68,68,0.2)", borderRadius: "12px", fontSize: "10px", color: "#FCA5A5", fontWeight: "bold", textTransform: "uppercase" }}>High Threat</span>}
        </div>
        <p style={{ color: "#9CA3AF", fontSize: "12px", margin: "0 0 6px 0" }}><strong style={{ color: "#D1D5DB" }}>HQ:</strong> {data.headquarters_city}, {data.headquarters_country}</p>
        <p style={{ color: "#9CA3AF", fontSize: "12px", margin: "0 0 6px 0" }}><strong style={{ color: "#D1D5DB" }}>Est. Revenue:</strong> ${data.estimated_revenue_usd_millions}M</p>
        <p style={{ color: "#9CA3AF", fontSize: "12px", margin: "0 0 12px 0" }}><strong style={{ color: "#D1D5DB" }}>Overlap Score:</strong> {data.overlap_with_teamwill_score}/5</p>
        <div style={{ background: "rgba(0,0,0,0.4)", padding: "12px", borderRadius: "8px", borderLeft: `2px solid ${data.is_high_threat ? "#EF4444" : "#818CF8"}` }}>
          <p style={{ color: "#E2E8F0", fontSize: "12px", margin: 0, fontStyle: "italic", lineHeight: "1.5" }}>"{data.overlap_rationale}"</p>
        </div>
      </div>
    );
  }
  return null;
};

export default function MarketPositioning() {
  const { t } = useTranslation();
  const [selectedCompetitor, setSelectedCompetitor] = useState<string>("Wavestone");
  const [targetIndustry, setTargetIndustry] = useState<string>("Automotive Captive (e.g. Sofico/Miles)");
  const [activeFilter, setActiveFilter] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["deal-intelligence"],
    queryFn: () => fetch(`${API}/api/deal-intelligence`).then(r => r.json()),
  });

  const compList = data?.competitors || [];
  const erpList = data?.erp_solutions || [];
  const regionalData = data?.regional_saturation || [];

  // Filter Competitors based on active Defend Zone click
  const filteredCompetitors = useMemo(() => {
    if (!activeFilter) return compList;
    const targets = activeFilter.split(',');
    return compList.filter((c: any) => targets.some(t => c.company_name.toLowerCase().includes(t.toLowerCase())));
  }, [activeFilter, compList]);

  if (isLoading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100vh", color: "#94A3B8" }}>
        Loading Deal Intelligence...
      </div>
    );
  }

  const highThreats = compList.filter((c: any) => c.is_high_threat).length;

  // Process Competitor Scale Scatter
  const scaleScatterData = [
    ...compList.map((c: any) => ({
      ...c,
      is_teamwill: false,
      estimated_revenue_usd_millions: Number(c.estimated_revenue_usd_millions) || 50,
      z: Number(c.estimated_revenue_usd_millions) || 50
    })),
    {
      company_name: "TEAMWILL",
      is_teamwill: true,
      domain_focus_score: 10,
      estimated_revenue_usd_millions: 110,
      z: 110,
      competitor_tier: "Teamwill",
      overlap_rationale: "Our Domain"
    }
  ];

  // Process ERP data for the Scatter Quadrant
  const industryFitData = erpList.map((erp: any, index: number) => ({
    ...erp,
    automotive_fit_score: Number(erp.automotive_fit_score) || 0,
    insurance_fit_score: Number(erp.insurance_fit_score) || 0,
    z: erp.is_teamwill_certified ? 200 : 80,
    color: erp.is_teamwill_certified ? "#10B981" : CATEGORICAL_COLORS[index % CATEGORICAL_COLORS.length]
  }));

  // Process ERP data for White-Space Matrix
  const whiteSpaceData = erpList.map((erp: any, index: number) => ({
    ...erp,
    competitor_partnership_count: Number(erp.competitor_partnership_count) || 0,
    alignment_score: erp.is_teamwill_certified ? 9 : (Number(erp.automotive_fit_score) || 3),
    color: erp.is_teamwill_certified ? (erp.competitor_partnership_count > 3 ? "#F87171" : "#38BDF8") : CATEGORICAL_COLORS[index % CATEGORICAL_COLORS.length]
  }));


  const currentCompData = compList.find((c: any) => c.company_name === selectedCompetitor) || compList[0];

  // Battlecard Logic
  const getDifferentiatorStrategy = (comp: any) => {
    if (!comp) return "Select a competitor.";
    const tier = comp.competitor_tier;
    
    let strategy = "";
    if (tier === "Tier 1 Global") {
      strategy = `**Laser Focus Argument:** Emphasize Teamwill's 100% dedication to the credit/asset finance chain. Unlike ${comp.company_name}, we don't treat asset finance as a small sub-practice; it is our entire business. They bring generalists; we bring certified experts.\n\n**The Cost-Quality Arbitrage:** Counter ${comp.company_name}'s high European day-rates by bidding with our Tunisian delivery center—providing European quality at nearshore cost optimization.`;
    } else if (tier === "Niche Specialist") {
      strategy = `**Independent Integrator Argument:** Leverage our capability as an independent end-to-end integrator. While ${comp.company_name} may push a single product ecosystem, we ensure the client isn't locked into a single tech stack and offer unbiased advisory across multiple platforms (Alfa, Solifi, Cassiopae, Miles).`;
    } else if (tier === "Tier 2 Regional") {
      strategy = `**Scale & Deep Expertise:** We offer the agility of a regional player but with deep, specialized vertical expertise that ${comp.company_name} lacks in the automotive/insurance niche. Highlight our proven MENA/Africa footprint and existing frameworks.`;
    } else {
      strategy = `**Premium Delivery Quality:** Emphasize our robust governance and track record with global Tier-1 banks, proving we can deliver at a scale and quality that ${comp.company_name} cannot match.`;
    }
    return strategy;
  };

  const renderMarkdownText = (text: string) => {
    const parts = text.split(/(\*\*.*?\*\*)/g);
    return parts.map((part, i) => {
      if (part.startsWith("**") && part.endsWith("**")) {
        return <strong key={i} style={{ color: "#F9FAFB" }}>{part.slice(2, -2)}</strong>;
      }
      return <span key={i}>{part}</span>;
    });
  };

  return (
    <div style={{ padding: "32px", minHeight: "100vh", animation: "intelFadeUp 0.8s cubic-bezier(0.16, 1, 0.3, 1)" }}>
      <style>{`
        @keyframes intelFadeUp {
          from { opacity: 0; transform: translateY(20px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes targetPulse {
          0% { stroke-width: 2; stroke-opacity: 1; }
          100% { stroke-width: 15; stroke-opacity: 0; }
        }
        .pulsing-target {
          animation: targetPulse 2s infinite ease-out;
        }
        .glass-panel {
          background: rgba(15,23,42,0.6);
          backdrop-filter: blur(12px);
          border: 1px solid rgba(255,255,255,0.08);
          border-radius: 20px;
          transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        .glass-panel:hover {
          border-color: rgba(255,255,255,0.2);
          box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }
        .gradient-text {
          background: linear-gradient(to right, #818CF8, #34D399);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
        }
        .filter-btn {
          cursor: pointer;
          transition: all 0.2s;
        }
        .filter-btn:hover {
          transform: translateY(-2px);
          filter: brightness(1.2);
        }
        .action-list li {
          display: flex;
          align-items: flex-start;
          gap: 12px;
        }
      `}</style>

      {/* HEADER & KPI */}
      <div style={{ marginBottom: "32px", display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
            <Target size={18} color="#818CF8" />
            <span style={{ fontSize: "14px", color: "#9CA3AF", fontWeight: 600, textTransform: "uppercase", letterSpacing: "1px" }}>Executive Cockpit</span>
          </div>
          <h1 style={{ fontSize: "36px", fontWeight: 800, color: "#F9FAFB", margin: 0, letterSpacing: "-1px" }}>
            {t("header.title", "Market Intelligence Platform")}
          </h1>
          <p style={{ color: "#94A3B8", marginTop: "8px", fontSize: "16px", maxWidth: "600px" }}>
            {t("header.subtitle", "Market Positioning & Deal Intelligence")}
          </p>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "20px", marginBottom: "40px" }}>
        <div className="glass-panel" style={{ padding: "24px", display: "flex", alignItems: "center", gap: "16px" }}>
          <div style={{ background: "rgba(99,102,241,0.15)", padding: "12px", borderRadius: "12px" }}><Building color="#818CF8" size={24} /></div>
          <div>
            <div style={{ fontSize: "13px", color: "#9CA3AF", fontWeight: 600, textTransform: "uppercase" }}>Teamwill Market Bracket</div>
            <div style={{ fontSize: "20px", color: "#F9FAFB", fontWeight: 700, marginTop: "4px" }}>€100M | 800+ Experts</div>
          </div>
        </div>
        <div className="glass-panel" style={{ padding: "24px", display: "flex", alignItems: "center", gap: "16px" }}>
          <div style={{ background: "rgba(16,185,129,0.15)", padding: "12px", borderRadius: "12px" }}><Users color="#34D399" size={24} /></div>
          <div>
            <div style={{ fontSize: "13px", color: "#9CA3AF", fontWeight: 600, textTransform: "uppercase" }}>{t("dashboard.kpi_competitors", "Total Tracked Competitors")}</div>
            <div style={{ fontSize: "24px", color: "#F9FAFB", fontWeight: 800, marginTop: "4px" }}>{compList.length}</div>
          </div>
        </div>
        <div className="glass-panel" style={{ padding: "24px", display: "flex", alignItems: "center", gap: "16px", border: "1px solid rgba(239,68,68,0.3)", background: "rgba(239,68,68,0.05)" }}>
          <div style={{ background: "rgba(239,68,68,0.2)", padding: "12px", borderRadius: "12px" }}><AlertTriangle color="#F87171" size={24} /></div>
          <div>
            <div style={{ fontSize: "13px", color: "#FCA5A5", fontWeight: 600, textTransform: "uppercase" }}>{t("dashboard.kpi_threats", "High-Overlap Threats")}</div>
            <div style={{ fontSize: "24px", color: "#F9FAFB", fontWeight: 800, marginTop: "4px" }}>{highThreats} Direct Threats</div>
          </div>
        </div>
      </div>

      {/* ==================================================================================== */}
      {/* OBJECTIVE 1: Market Scale & Competitor Positioning (ORIGINAL GRAPHS INCLUDED)        */}
      {/* ==================================================================================== */}
      <h2 style={{ margin: "0 0 20px 0", fontSize: "24px", color: "#F9FAFB", display: "flex", alignItems: "center", gap: "8px", borderBottom: "1px solid rgba(255,255,255,0.1)", paddingBottom: "12px" }}>
        <Layers size={24} color="#818CF8" /> Objective 1: Market Scale & Competitor Positioning
      </h2>

      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "24px", marginBottom: "40px" }}>
        
        {/* ORIGINAL: Interactive Positioning Matrix */}
        <div className="glass-panel" style={{ padding: "24px" }}>
          <h3 style={{ margin: "0 0 4px 0", fontSize: "18px", color: "#F9FAFB" }}>{t("dashboard.matrix_title", "Interactive Positioning Matrix")}</h3>
          <p style={{ margin: "0 0 24px 0", fontSize: "13px", color: "#9CA3AF" }}>Domain Specialization vs Market Scale (Revenue USD)</p>
          
          <div style={{ width: "100%", height: "400px" }}>
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis 
                  type="number" dataKey="domain_focus_score" name="Focus" domain={[0, 11]} stroke="#475569" 
                  tick={{ fill: "#94A3B8", fontSize: 12 }}
                  tickFormatter={(val) => {
                    if (val === 2) return "Broad/Global";
                    if (val === 5) return "Regional";
                    if (val === 10) return "100% Specialized";
                    return "";
                  }}
                />
                <YAxis 
                  type="number" dataKey="estimated_revenue_usd_millions" name="Revenue" scale="log" domain={[10, 100000]} stroke="#475569"
                  tick={{ fill: "#94A3B8", fontSize: 12 }} tickFormatter={(val) => `$${val}M`}
                />
                <ZAxis type="number" dataKey="z" range={[100, 1000]} name="Scale" />
                <Tooltip content={<CompScatterTooltip />} cursor={{ strokeDasharray: '3 3' }} />
                
                <Scatter name="Competitors" data={scaleScatterData}>
                  {scaleScatterData.map((entry, index) => (
                    <Cell 
                      key={`cell-${index}`} 
                      fill={entry.is_teamwill ? "#818CF8" : (TIER_COLORS[entry.competitor_tier] || "#94A3B8")} 
                      fillOpacity={entry.is_teamwill ? 1 : 0.8}
                      stroke={entry.is_teamwill ? "#FFFFFF" : "rgba(255,255,255,0.2)"}
                      strokeWidth={entry.is_teamwill ? 3 : 1}
                      style={{ cursor: "pointer" }}
                    />
                  ))}
                </Scatter>
              </ScatterChart>
            </ResponsiveContainer>
          </div>
          
          <div style={{ display: "flex", gap: "16px", marginTop: "16px", justifyContent: "center", flexWrap: "wrap" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}><span style={{ width: 12, height: 12, borderRadius: "50%", background: "#818CF8", border: "2px solid #FFF" }}></span><span style={{ fontSize: 12, color: "#D1D5DB" }}>Teamwill (Anchor)</span></div>
            {Object.entries(TIER_COLORS).map(([tier, color]) => (
              <div key={tier} style={{ display: "flex", alignItems: "center", gap: "6px" }}><span style={{ width: 10, height: 10, borderRadius: "50%", background: color, opacity: 0.8 }}></span><span style={{ fontSize: 12, color: "#D1D5DB" }}>{tier}</span></div>
            ))}
          </div>
        </div>

        {/* COMPETITOR GRID TABLE */}
        <div className="glass-panel" style={{ padding: "24px", display: "flex", flexDirection: "column" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
            <h3 style={{ margin: 0, fontSize: "18px", color: "#F9FAFB", display: "flex", alignItems: "center", gap: "8px" }}>
              <Users size={18} color="#A5B4FC" /> Competitor Threat Grid
            </h3>
            {activeFilter && (
              <button onClick={() => setActiveFilter(null)} style={{ padding: "4px 12px", background: "rgba(239,68,68,0.2)", color: "#FCA5A5", border: "1px solid rgba(239,68,68,0.3)", borderRadius: "6px", fontSize: "12px", cursor: "pointer" }}>
                Clear Filter
              </button>
            )}
          </div>
          
          <div style={{ flex: 1, overflowY: "auto", maxHeight: "380px", paddingRight: "8px" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid #334155" }}>
                  <th style={{ padding: "12px 8px", color: "#94A3B8", fontSize: "12px", fontWeight: 600 }}>Company</th>
                  <th style={{ padding: "12px 8px", color: "#94A3B8", fontSize: "12px", fontWeight: 600 }}>HQ</th>
                  <th style={{ padding: "12px 8px", color: "#94A3B8", fontSize: "12px", fontWeight: 600 }}>Overlap</th>
                </tr>
              </thead>
              <tbody>
                {filteredCompetitors.map((comp: any) => (
                  <tr key={comp.company_name} style={{ borderBottom: "1px solid rgba(255,255,255,0.05)", transition: "background 0.2s", cursor: "pointer" }} onClick={() => setSelectedCompetitor(comp.company_name)} onMouseOver={(e) => e.currentTarget.style.background = "rgba(255,255,255,0.03)"} onMouseOut={(e) => e.currentTarget.style.background = "transparent"}>
                    <td style={{ padding: "12px 8px", color: "#F1F5F9", fontSize: "14px", fontWeight: 500 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                        <span style={{ width: 8, height: 8, borderRadius: "50%", background: TIER_COLORS[comp.competitor_tier] || "#94A3B8" }}></span>
                        {comp.company_name}
                      </div>
                    </td>
                    <td style={{ padding: "12px 8px", color: "#9CA3AF", fontSize: "13px" }}>{comp.headquarters_country}</td>
                    <td style={{ padding: "12px 8px" }}>
                      <span style={{ padding: "2px 8px", background: comp.is_high_threat ? "rgba(239,68,68,0.2)" : "rgba(16,185,129,0.2)", color: comp.is_high_threat ? "#FCA5A5" : "#6EE7B7", borderRadius: "10px", fontSize: "12px", fontWeight: "bold" }}>
                        {comp.overlap_with_teamwill_score}/5
                      </span>
                    </td>
                  </tr>
                ))}
                {filteredCompetitors.length === 0 && (
                  <tr>
                    <td colSpan={3} style={{ padding: "24px", textAlign: "center", color: "#64748B" }}>No competitors found for this filter.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* ORIGINAL: Deal-Win Battlecard Engine */}
      <div className="glass-panel" style={{ padding: "32px", borderTop: "4px solid #818CF8", marginBottom: "50px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "24px" }}>
          <div style={{ background: "#818CF8", padding: "8px", borderRadius: "10px" }}><Shield color="#FFF" size={20} /></div>
          <div>
            <h3 style={{ margin: 0, fontSize: "20px", color: "#F9FAFB" }}>"Deal-Win" Battlecard Engine 🏆</h3>
            <p style={{ margin: "4px 0 0 0", fontSize: "14px", color: "#9CA3AF" }}>Tactical bidding calculator for competitive deals</p>
          </div>
        </div>

        <div style={{ display: "flex", gap: "24px", marginBottom: "32px", flexWrap: "wrap" }}>
          <div style={{ flex: "1 1 300px" }}>
            <label style={{ display: "block", fontSize: "13px", color: "#94A3B8", marginBottom: "8px", fontWeight: 600 }}>Select Competitor We Are Bidding Against</label>
            <select 
              value={selectedCompetitor}
              onChange={(e) => setSelectedCompetitor(e.target.value)}
              style={{ width: "100%", padding: "12px 16px", borderRadius: "8px", background: "rgba(15,23,42,0.8)", border: "1px solid #475569", color: "#F1F5F9", fontSize: "15px", outline: "none", cursor: "pointer" }}
            >
              {compList.map((c: any) => (
                <option key={c.id || c.company_name} value={c.company_name}>{c.company_name} ({c.competitor_tier})</option>
              ))}
            </select>
          </div>
          <div style={{ flex: "1 1 300px" }}>
            <label style={{ display: "block", fontSize: "13px", color: "#94A3B8", marginBottom: "8px", fontWeight: 600 }}>Target Client Industry / Core System</label>
            <select 
              value={targetIndustry}
              onChange={(e) => setTargetIndustry(e.target.value)}
              style={{ width: "100%", padding: "12px 16px", borderRadius: "8px", background: "rgba(15,23,42,0.8)", border: "1px solid #475569", color: "#F1F5F9", fontSize: "15px", outline: "none", cursor: "pointer" }}
            >
              <option>Automotive Captive (e.g. Sofico/Miles)</option>
              <option>Corporate Lending / Equipment Finance</option>
              <option>Banking Software Modernization</option>
              <option>SAP Finance Backbone Integration</option>
            </select>
          </div>
        </div>

        {currentCompData && (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "32px", background: "rgba(0,0,0,0.2)", borderRadius: "16px", padding: "24px", border: "1px solid rgba(255,255,255,0.05)" }}>
            
            {/* Left: Competitor Profiling */}
            <div>
              <h4 style={{ margin: "0 0 16px 0", fontSize: "16px", color: "#CBD5E1", display: "flex", alignItems: "center", gap: "8px" }}>
                <Globe size={16} /> Competitor Profiling
              </h4>
              <div style={{ background: "rgba(255,255,255,0.03)", borderRadius: "8px", padding: "16px", marginBottom: "16px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
                  <span style={{ color: "#9CA3AF", fontSize: "13px" }}>Scale / Revenue</span>
                  <span style={{ color: "#F9FAFB", fontWeight: 600 }}>${currentCompData.estimated_revenue_usd_millions}M</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
                  <span style={{ color: "#9CA3AF", fontSize: "13px" }}>Geographic Presence</span>
                  <span style={{ color: "#F9FAFB", fontWeight: 600, textAlign: "right", maxWidth: "60%" }}>{currentCompData.geographic_presence || "Global"}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "#9CA3AF", fontSize: "13px" }}>Tier</span>
                  <span style={{ color: TIER_COLORS[currentCompData.competitor_tier] || "#F9FAFB", fontWeight: 600 }}>{currentCompData.competitor_tier}</span>
                </div>
              </div>
              <div style={{ marginBottom: "16px" }}>
                <h5 style={{ fontSize: "12px", color: "#94A3B8", textTransform: "uppercase", marginBottom: "6px" }}>Recent Activity (News)</h5>
                <p style={{ margin: 0, fontSize: "14px", color: "#E2E8F0", lineHeight: "1.5", padding: "12px", background: "rgba(255,255,255,0.03)", borderRadius: "8px" }}>
                  "{currentCompData.recent_news_headline || 'No recent strategic moves detected.'}"
                </p>
              </div>
              <div>
                <h5 style={{ fontSize: "12px", color: "#FCA5A5", textTransform: "uppercase", marginBottom: "6px" }}>Why they threaten us (Overlap)</h5>
                <p style={{ margin: 0, fontSize: "14px", color: "#E2E8F0", lineHeight: "1.5", padding: "12px", background: "rgba(239,68,68,0.1)", borderLeft: "2px solid #EF4444", borderRadius: "0 8px 8px 0" }}>
                  {currentCompData.overlap_rationale}
                </p>
              </div>
            </div>

            {/* Right: Differentiator Strategy */}
            <div>
              <h4 style={{ margin: "0 0 16px 0", fontSize: "16px", color: "#34D399", display: "flex", alignItems: "center", gap: "8px" }}>
                <CheckCircle2 size={16} /> How to Win the Deal (Strategy)
              </h4>
              <div style={{ background: "rgba(16,185,129,0.05)", border: "1px solid rgba(16,185,129,0.2)", borderRadius: "12px", padding: "20px" }}>
                <p style={{ color: "#10B981", fontSize: "12px", textTransform: "uppercase", fontWeight: 700, margin: "0 0 12px 0" }}>Talk Track for Management</p>
                <div style={{ fontSize: "15px", color: "#E2E8F0", lineHeight: "1.7", whiteSpace: "pre-wrap" }}>
                  {renderMarkdownText(getDifferentiatorStrategy(currentCompData))}
                </div>
                <div style={{ marginTop: "24px", paddingTop: "16px", borderTop: "1px solid rgba(255,255,255,0.1)" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#A5B4FC", fontSize: "13px", fontWeight: 600 }}>
                    <ChevronRight size={14} /> Recommended Action:
                  </div>
                  <p style={{ margin: "4px 0 0 22px", fontSize: "14px", color: "#9CA3AF", lineHeight: "1.5" }}>
                    Print this battlecard 10 minutes before the pitch. Rehearse the Laser Focus argument to instantly frame {currentCompData.company_name} as a generalist.
                  </p>
                </div>
              </div>
            </div>

          </div>
        )}
      </div>

      {/* ==================================================================================== */}
      {/* OBJECTIVE 2: Tech Specialization & ERP White-Space (NEW GRAPHS)                      */}
      {/* ==================================================================================== */}
      <h2 style={{ margin: "0 0 20px 0", fontSize: "24px", color: "#F9FAFB", display: "flex", alignItems: "center", gap: "8px", borderBottom: "1px solid rgba(255,255,255,0.1)", paddingBottom: "12px" }}>
        <Zap size={24} color="#34D399" /> Objective 2: Tech Specialization & Core Ecosystems
      </h2>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "24px", marginBottom: "24px" }}>
        
        {/* NEW: Industry Fit Quadrant */}
        <div className="glass-panel" style={{ padding: "24px", position: "relative" }}>
          <h3 style={{ margin: "0 0 4px 0", fontSize: "18px", color: "#F9FAFB", display: "flex", alignItems: "center", gap: "8px" }}>
            <Activity size={18} color="#818CF8" /> Industry Fit Quadrant (Unfair Advantage)
          </h3>
          <p style={{ margin: "0 0 24px 0", fontSize: "13px", color: "#9CA3AF" }}>Automotive vs Insurance Specialization. Teamwill Certified ERPs pulse.</p>
          
          <div style={{ width: "100%", height: "350px" }}>
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis type="number" dataKey="automotive_fit_score" name="Auto Fit" domain={[0, 10]} stroke="#475569" tick={{ fill: "#94A3B8", fontSize: 11 }} />
                <YAxis type="number" dataKey="insurance_fit_score" name="Insurance Fit" domain={[0, 10]} stroke="#475569" tick={{ fill: "#94A3B8", fontSize: 11 }} />
                <ZAxis type="number" dataKey="z" range={[80, 250]} />
                <Tooltip content={<ERPScatterTooltip />} cursor={{ strokeDasharray: '3 3' }} />
                
                <ReferenceArea x1={0} x2={5} y1={5} y2={10} fill="rgba(99,102,241,0.08)" /> 
                <ReferenceArea x1={5} x2={10} y1={0} y2={5} fill="rgba(16,185,129,0.08)" /> 
                <ReferenceArea x1={5} x2={10} y1={5} y2={10} fill="rgba(245,158,11,0.08)" /> 
                <ReferenceArea x1={0} x2={5} y1={0} y2={5} fill="rgba(255,255,255,0.02)" /> 

                <text x="25%" y="25%" fill="#818CF8" fontSize={12} fontWeight={600} textAnchor="middle" opacity={0.6}>Insurance Specialists</text>
                <text x="75%" y="75%" fill="#10B981" fontSize={12} fontWeight={600} textAnchor="middle" opacity={0.6}>Automotive Specialists</text>
                <text x="75%" y="25%" fill="#F59E0B" fontSize={12} fontWeight={600} textAnchor="middle" opacity={0.6}>Dual-Strong</text>
                <text x="25%" y="75%" fill="#94A3B8" fontSize={12} fontWeight={600} textAnchor="middle" opacity={0.6}>General Purpose</text>

                <Scatter name="ERPs" data={industryFitData}>
                  {industryFitData.map((entry: any, index: number) => (
                    <Cell 
                      key={`cell-${index}`} 
                      fill={entry.color} 
                      fillOpacity={0.9}
                      stroke={entry.is_teamwill_certified ? "#FFFFFF" : "rgba(0,0,0,0.5)"}
                      strokeWidth={entry.is_teamwill_certified ? 2 : 1}
                      className={entry.is_teamwill_certified ? "pulsing-target" : ""}
                    />
                  ))}
                </Scatter>
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* ORIGINAL: ERP & Competency Radar */}
        <div className="glass-panel" style={{ padding: "24px", display: "flex", flexDirection: "column" }}>
          <h3 style={{ margin: "0 0 4px 0", fontSize: "18px", color: "#F9FAFB" }}>ERP & Competency Radar</h3>
          <p style={{ margin: "0 0 16px 0", fontSize: "13px", color: "#9CA3AF" }}>Teamwill Advantage vs Market Average</p>
          
          <div style={{ flex: 1, width: "100%", minHeight: "280px" }}>
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart cx="50%" cy="50%" outerRadius="70%" data={radarData}>
                <PolarGrid stroke="rgba(255,255,255,0.1)" />
                <PolarAngleAxis dataKey="subject" tick={{ fill: "#CBD5E1", fontSize: 11 }} />
                <PolarRadiusAxis angle={30} domain={[0, 10]} tick={false} axisLine={false} />
                <Radar name="Teamwill Envelope" dataKey="teamwill" stroke="#818CF8" fill="#818CF8" fillOpacity={0.4} strokeWidth={2} />
                <Radar name="Competitor Avg" dataKey="marketAvg" stroke="#F59E0B" fill="#F59E0B" fillOpacity={0.2} strokeWidth={2} strokeDasharray="4 4" />
                <Legend wrapperStyle={{ fontSize: 12, paddingTop: 10 }} />
              </RadarChart>
            </ResponsiveContainer>
          </div>
          <div style={{ background: "rgba(99,102,241,0.1)", borderRadius: "8px", padding: "12px", border: "1px solid rgba(99,102,241,0.2)" }}>
            <p style={{ margin: 0, fontSize: "12px", color: "#A5B4FC", lineHeight: "1.5" }}>
              <strong>Value Pitch:</strong> Leverage our 10/10 Automotive Lease & Finance integration (e.g. Sofico Miles) to highlight the technical gap in generic Tier 1 integrator proposals.
            </p>
          </div>
        </div>

      </div>

      {/* NEW: Tech White-Space Analyzer */}
      <div className="glass-panel" style={{ padding: "24px", marginBottom: "50px" }}>
        <h3 style={{ margin: "0 0 4px 0", fontSize: "18px", color: "#F9FAFB", display: "flex", alignItems: "center", gap: "8px" }}>
          <Zap size={18} color="#F59E0B" /> Tech White-Space vs. Red-Ocean Matrix
        </h3>
        <p style={{ margin: "0 0 24px 0", fontSize: "13px", color: "#9CA3AF" }}>Market Crowding vs Teamwill Core Alignment. Spot platforms where Teamwill is certified but competitor partnership counts are exceptionally low.</p>
        
        <div style={{ width: "100%", height: "350px" }}>
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis type="number" dataKey="competitor_partnership_count" name="Competitor Crowding" domain={[0, 10]} stroke="#475569" tick={{ fill: "#94A3B8", fontSize: 11 }} />
              <YAxis type="number" dataKey="alignment_score" name="Alignment" domain={[0, 10]} stroke="#475569" tick={false} />
              <ZAxis type="number" dataKey="z" range={[80, 200]} />
              <Tooltip cursor={{ strokeDasharray: '3 3' }} content={({ active, payload }) => {
                if (active && payload && payload.length) {
                  const d = payload[0].payload;
                  return (
                    <div style={{ background: "rgba(15,23,42,0.9)", padding: "10px", borderRadius: "8px", border: "1px solid #475569", color: "#F9FAFB", minWidth: "150px" }}>
                      <strong style={{ display: "flex", alignItems: "center", gap: "6px", color: d.color }}>
                        <span style={{ width: 10, height: 10, borderRadius: "50%", background: d.color, display: "inline-block" }}></span>
                        {d.erp_name}
                      </strong>
                      <div style={{ marginTop: "6px", fontSize: 12, color: "#9CA3AF" }}>Competitors: {d.competitor_partnership_count}</div>
                      <div style={{ marginTop: "4px", fontSize: 12, color: d.is_teamwill_certified ? "#10B981" : "#EF4444" }}>{d.is_teamwill_certified ? "Teamwill Certified" : "Not Certified"}</div>
                    </div>
                  );
                }
                return null;
              }} />
              
              <ReferenceArea x1={4} x2={10} y1={5} y2={10} fill="rgba(239,68,68,0.1)" />
              <ReferenceArea x1={0} x2={4} y1={5} y2={10} fill="rgba(56,189,248,0.1)" />

              <text x="80%" y="25%" fill="#EF4444" fontSize={14} fontWeight={700} textAnchor="middle" opacity={0.6}>Red Ocean</text>
              <text x="20%" y="25%" fill="#38BDF8" fontSize={14} fontWeight={700} textAnchor="middle" opacity={0.6}>White Space</text>

              <Scatter name="White Space" data={whiteSpaceData}>
                {whiteSpaceData.map((entry: any, index: number) => (
                  <Cell 
                    key={`cell-${index}`} 
                    fill={entry.color} 
                    stroke="rgba(0,0,0,0.5)"
                    strokeWidth={1}
                  />
                ))}
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ==================================================================================== */}
      {/* OBJECTIVE 3: Defensive Strategy & Regional Playbook (NEW GRAPHS)                     */}
      {/* ==================================================================================== */}
      <h2 style={{ margin: "0 0 20px 0", fontSize: "24px", color: "#F9FAFB", display: "flex", alignItems: "center", gap: "8px", borderBottom: "1px solid rgba(255,255,255,0.1)", paddingBottom: "12px" }}>
        <Globe size={24} color="#38BDF8" /> Objective 3: Defensive Strategy & Regional Playbook
      </h2>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: "24px", marginBottom: "24px" }}>
        
        {/* NEW: Regional Defensive Saturation */}
        <div className="glass-panel" style={{ padding: "24px" }}>
          <h3 style={{ margin: "0 0 4px 0", fontSize: "18px", color: "#F9FAFB", display: "flex", alignItems: "center", gap: "8px" }}>
            <Globe size={18} color="#38BDF8" /> Regional Defensive Saturation
          </h3>
          <p style={{ margin: "0 0 24px 0", fontSize: "13px", color: "#9CA3AF" }}>Competitor density in Teamwill strongholds.</p>
          
          <div style={{ width: "100%", height: "280px" }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart layout="vertical" data={regionalData} margin={{ top: 0, right: 30, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} stroke="rgba(255,255,255,0.05)" />
                <XAxis type="number" stroke="#475569" tick={{ fill: "#94A3B8", fontSize: 11 }} />
                <YAxis dataKey="country" type="category" stroke="#475569" tick={{ fill: "#F9FAFB", fontSize: 12, fontWeight: 500 }} width={70} />
                <Tooltip cursor={{fill: "rgba(255,255,255,0.05)"}} contentStyle={{ background: "rgba(15,23,42,0.9)", border: "1px solid #475569", borderRadius: "8px" }} />
                <Bar dataKey="density" radius={[0, 4, 4, 0]} barSize={24}>
                  {regionalData.map((entry: any, index: number) => {
                    const isHub = entry.country === "Tunisia" || entry.country === "France";
                    return (
                      <Cell key={`cell-${index}`} fill={isHub ? "#34D399" : "#6366F1"} />
                    );
                  })}
                  <LabelList dataKey="density" position="right" fill="#F1F5F9" fontSize={12} fontWeight={600} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* NEW: Strategic Action Command Hub */}
        <div className="glass-panel" style={{ padding: "24px" }}>
          <h3 style={{ margin: "0 0 16px 0", fontSize: "18px", color: "#F9FAFB", display: "flex", alignItems: "center", gap: "8px" }}>
            <Target size={18} color="#F1F5F9" /> Strategic Action Command Hub
          </h3>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "16px" }}>
            
            {/* DEFEND ZONE */}
            <div style={{ borderTop: "4px solid #EF4444", background: "rgba(239,68,68,0.05)", borderRadius: "0 0 12px 12px", padding: "16px", display: "flex", flexDirection: "column" }}>
              <div style={{ marginBottom: "16px" }}>
                <h4 style={{ color: "#FCA5A5", margin: "0 0 4px 0", display: "flex", alignItems: "center", gap: "6px", textTransform: "uppercase", fontSize: "14px", fontWeight: 700 }}>
                  <Shield size={16} /> Defend Zone
                </h4>
                <p style={{ margin: 0, fontSize: "12px", color: "#9CA3AF", lineHeight: "1.4" }}>
                  Protect core markets where high-threat generalists attempt to undercut margins.
                </p>
              </div>
              <ul className="action-list" style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: "12px", flex: 1 }}>
                <li className="filter-btn" onClick={() => { setActiveFilter("Wavestone,Talan,Sia"); window.scrollTo({ top: 300, behavior: 'smooth' }); }} style={{ background: "rgba(0,0,0,0.2)", padding: "12px", borderRadius: "8px", borderLeft: "2px solid #EF4444" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "8px" }}>
                    <span style={{ fontSize: "13px", fontWeight: 700, color: "#F9FAFB" }}>France Banking Core</span>
                  </div>
                  <div style={{ display: "grid", gap: "6px", fontSize: "12px" }}>
                    <div style={{ display: "flex", gap: "6px" }}><span style={{ color: "#94A3B8", minWidth: "60px" }}>Risk:</span> <span style={{ color: "#CBD5E1" }}>High attrition to Wavestone & Talan.</span></div>
                    <div style={{ display: "flex", gap: "6px" }}><span style={{ color: "#94A3B8", minWidth: "60px" }}>Action:</span> <span style={{ color: "#FCA5A5", fontWeight: 500 }}>Deploy senior domain architects immediately.</span></div>
                  </div>
                </li>
                <li className="filter-btn" onClick={() => { setActiveFilter("BFI,WEVIOO,Proxym"); window.scrollTo({ top: 300, behavior: 'smooth' }); }} style={{ background: "rgba(0,0,0,0.2)", padding: "12px", borderRadius: "8px", borderLeft: "2px solid #EF4444" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "8px" }}>
                    <span style={{ fontSize: "13px", fontWeight: 700, color: "#F9FAFB" }}>Tunisia Delivery Margins</span>
                  </div>
                  <div style={{ display: "grid", gap: "6px", fontSize: "12px" }}>
                    <div style={{ display: "flex", gap: "6px" }}><span style={{ color: "#94A3B8", minWidth: "60px" }}>Risk:</span> <span style={{ color: "#CBD5E1" }}>Localized pressure from BFI & WEVIOO.</span></div>
                    <div style={{ display: "flex", gap: "6px" }}><span style={{ color: "#94A3B8", minWidth: "60px" }}>Action:</span> <span style={{ color: "#FCA5A5", fontWeight: 500 }}>Emphasize global tier-1 governance standards.</span></div>
                  </div>
                </li>
                <li className="filter-btn" onClick={() => { setActiveFilter("Linedata"); window.scrollTo({ top: 300, behavior: 'smooth' }); }} style={{ background: "rgba(0,0,0,0.2)", padding: "12px", borderRadius: "8px", borderLeft: "2px solid #EF4444" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "8px" }}>
                    <span style={{ fontSize: "13px", fontWeight: 700, color: "#F9FAFB" }}>Auto Finance Accounts</span>
                  </div>
                  <div style={{ display: "grid", gap: "6px", fontSize: "12px" }}>
                    <div style={{ display: "flex", gap: "6px" }}><span style={{ color: "#94A3B8", minWidth: "60px" }}>Risk:</span> <span style={{ color: "#CBD5E1" }}>Linedata aggressively targeting renewals.</span></div>
                    <div style={{ display: "flex", gap: "6px" }}><span style={{ color: "#94A3B8", minWidth: "60px" }}>Action:</span> <span style={{ color: "#FCA5A5", fontWeight: 500 }}>Lock in clients via specialized module upgrades.</span></div>
                  </div>
                </li>
              </ul>
            </div>

            {/* INVEST ZONE */}
            <div style={{ borderTop: "4px solid #3B82F6", background: "rgba(59,130,246,0.05)", borderRadius: "0 0 12px 12px", padding: "16px", display: "flex", flexDirection: "column" }}>
              <div style={{ marginBottom: "16px" }}>
                <h4 style={{ color: "#93C5FD", margin: "0 0 4px 0", display: "flex", alignItems: "center", gap: "6px", textTransform: "uppercase", fontSize: "14px", fontWeight: 700 }}>
                  <BarChart2 size={16} /> Invest Zone
                </h4>
                <p style={{ margin: 0, fontSize: "12px", color: "#9CA3AF", lineHeight: "1.4" }}>
                  Allocate capital to deeply specialized tech ecosystems mapping into our "White Space".
                </p>
              </div>
              <ul className="action-list" style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: "12px", flex: 1 }}>
                <li style={{ background: "rgba(0,0,0,0.2)", padding: "12px", borderRadius: "8px", borderLeft: "2px solid #3B82F6" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "8px" }}>
                    <span style={{ fontSize: "13px", fontWeight: 700, color: "#F9FAFB" }}>Sofico Miles Practice</span>
                  </div>
                  <div style={{ display: "grid", gap: "6px", fontSize: "12px" }}>
                    <div style={{ display: "flex", gap: "6px" }}><span style={{ color: "#94A3B8", minWidth: "60px" }}>Logic:</span> <span style={{ color: "#CBD5E1" }}>High certification exclusivity / low crowding.</span></div>
                    <div style={{ display: "flex", gap: "6px" }}><span style={{ color: "#94A3B8", minWidth: "60px" }}>Action:</span> <span style={{ color: "#93C5FD", fontWeight: 500 }}>Scale engineering recruitment by +20%.</span></div>
                  </div>
                </li>
                <li style={{ background: "rgba(0,0,0,0.2)", padding: "12px", borderRadius: "8px", borderLeft: "2px solid #3B82F6" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "8px" }}>
                    <span style={{ fontSize: "13px", fontWeight: 700, color: "#F9FAFB" }}>Dynamics 365 F&O</span>
                  </div>
                  <div style={{ display: "grid", gap: "6px", fontSize: "12px" }}>
                    <div style={{ display: "flex", gap: "6px" }}><span style={{ color: "#94A3B8", minWidth: "60px" }}>Logic:</span> <span style={{ color: "#CBD5E1" }}>Fastest growing mid-market ERP.</span></div>
                    <div style={{ display: "flex", gap: "6px" }}><span style={{ color: "#94A3B8", minWidth: "60px" }}>Action:</span> <span style={{ color: "#93C5FD", fontWeight: 500 }}>Build dedicated competency center.</span></div>
                  </div>
                </li>
              </ul>
            </div>

            {/* EXPAND ZONE */}
            <div style={{ borderTop: "4px solid #10B981", background: "rgba(16,185,129,0.05)", borderRadius: "0 0 12px 12px", padding: "16px", display: "flex", flexDirection: "column" }}>
              <div style={{ marginBottom: "16px" }}>
                <h4 style={{ color: "#6EE7B7", margin: "0 0 4px 0", display: "flex", alignItems: "center", gap: "6px", textTransform: "uppercase", fontSize: "14px", fontWeight: 700 }}>
                  <Globe size={16} /> Expand Zone
                </h4>
                <p style={{ margin: 0, fontSize: "12px", color: "#9CA3AF", lineHeight: "1.4" }}>
                  Target blue-ocean geographic regions & untouched segments with low resistance.
                </p>
              </div>
              <ul className="action-list" style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: "12px", flex: 1 }}>
                <li style={{ background: "rgba(0,0,0,0.2)", padding: "12px", borderRadius: "8px", borderLeft: "2px solid #10B981" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "8px" }}>
                    <span style={{ fontSize: "13px", fontWeight: 700, color: "#F9FAFB" }}>GCC Automotive Captives</span>
                  </div>
                  <div style={{ display: "grid", gap: "6px", fontSize: "12px" }}>
                    <div style={{ display: "flex", gap: "6px" }}><span style={{ color: "#94A3B8", minWidth: "60px" }}>Driver:</span> <span style={{ color: "#CBD5E1" }}>Untapped market with budget surpluses.</span></div>
                    <div style={{ display: "flex", gap: "6px" }}><span style={{ color: "#94A3B8", minWidth: "60px" }}>Action:</span> <span style={{ color: "#6EE7B7", fontWeight: 500 }}>Launch specialized Gulf expansion team.</span></div>
                  </div>
                </li>
                <li style={{ background: "rgba(0,0,0,0.2)", padding: "12px", borderRadius: "8px", borderLeft: "2px solid #10B981" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "8px" }}>
                    <span style={{ fontSize: "13px", fontWeight: 700, color: "#F9FAFB" }}>Africa SME Lending</span>
                  </div>
                  <div style={{ display: "grid", gap: "6px", fontSize: "12px" }}>
                    <div style={{ display: "flex", gap: "6px" }}><span style={{ color: "#94A3B8", minWidth: "60px" }}>Driver:</span> <span style={{ color: "#CBD5E1" }}>Open-source ERP adoption scaling rapidly.</span></div>
                    <div style={{ display: "flex", gap: "6px" }}><span style={{ color: "#94A3B8", minWidth: "60px" }}>Action:</span> <span style={{ color: "#6EE7B7", fontWeight: 500 }}>Leverage ERPNext / Cegid alliances.</span></div>
                  </div>
                </li>
              </ul>
            </div>

          </div>
        </div>
      </div>

    </div>
  );
}
