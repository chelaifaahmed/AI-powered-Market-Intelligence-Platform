import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  LayoutDashboard,
  BookOpen,
  Building2,
  TrendingUp,
  MessageSquare,
  Settings,
  Telescope,
  Target,
  Brain,
  Flame,
  Globe,
  ChevronDown,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import AskAiDrawer from "./AskAiDrawer";
import LiveIndicator from "./LiveIndicator";

const API = import.meta.env.VITE_API_URL || "";

const mainNav = [
  { to: "/accueil", label: "Alpha Drop", icon: Flame, key: "alpha_drop" },
  { to: "/company-intelligence", label: "Prospect Strategy", icon: Brain, key: "prospect_strategy" },
  { to: "/company", label: "Distress Radar", icon: Building2, key: "distress_radar" },
  { to: "/field-intel", label: "Field Intel", icon: Telescope, key: "field_intel" },
  { to: "/deal-intelligence", label: "Deal Intelligence", icon: Target, key: "deal_intel" },
  { to: "/market", label: "Scraping Stats", icon: TrendingUp, key: "scraping_stats" },
  { to: "/analyst", label: "AI Analyst", icon: MessageSquare, key: "ai_analyst" },
];

const PAGE_TITLES: Record<string, { title: string; subtitle: string }> = {
  "/accueil": { title: "Alpha Drop", subtitle: "Vibe check · Real-time tea · Alpha signals" },
  "/company": { title: "Distress Radar", subtitle: "Track companies, clusters & ERP signals" },
  "/company-intelligence": { title: "Prospect Strategy", subtitle: "Entity state, hiring signals, intervention depth & outreach timing" },
  "/field-intel": { title: "Field Intel", subtitle: "Market news & pricing data for your sales & prospection calls" },
  "/deal-intelligence": { title: "Market Positioning & Deal Intelligence", subtitle: "Strategic Deal-Win Architecture" },
  "/market": { title: "Scraping Stats", subtitle: "Operational health & top-level intelligence signals" },
  "/analyst": { title: "AI Analyst", subtitle: "Chat with your data using Claude AI" },
  "/admin": { title: "Admin", subtitle: "Operations, sources & system management" },
  "/opportunities": { title: "Market Opportunities", subtitle: "Sales intelligence signals & opportunity scoring" },
  "/opportunities-v2": { title: "Opportunity Radar", subtitle: "Four-axis V2 model: Pain · Recovery · ERP Fit · Reachability" },
  "/ml-intelligence": { title: "Intelligence Segments", subtitle: "AI-driven clustering & ERP modernization signals" },
  "/brands": { title: "Brand Intelligence", subtitle: "Reputation trends, sentiment analysis & review insights" },
  "/insurance": { title: "Insurance Landscape", subtitle: "Insurance market analysis & competitive intelligence" },
  "/listings": { title: "Vehicle Market", subtitle: "Marketplace data, pricing & dealer insights" },
  "/pricing": { title: "Competitor Pricing", subtitle: "Insurance pricing snapshots & market positioning" },
  "/articles": { title: "Market Articles", subtitle: "Industry news, trend analysis & content intelligence" },
  "/operations": { title: "Operations Center", subtitle: "Pipeline health, data quality & source monitoring" },
  "/sources": { title: "Source Management", subtitle: "Manage scraping sources, keywords & data feeds" },
};

function LanguageSwitcher() {
  const { i18n, t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);

  const toggleLang = (lang: string) => {
    i18n.changeLanguage(lang);
    setIsOpen(false);
  };

  return (
    <div style={{ position: "relative" }}>
      <button 
        onClick={() => setIsOpen(!isOpen)}
        style={{ display: "flex", alignItems: "center", gap: "6px", padding: "6px 12px", borderRadius: "8px", border: "1px solid #334155", background: "transparent", color: "#9CA3AF", fontSize: "13px", fontWeight: 500, cursor: "pointer", transition: "all 0.2s" }}
        onMouseEnter={(e) => e.currentTarget.style.background = "rgba(255,255,255,0.05)"}
        onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
      >
        <Globe size={14} />
        {(i18n.language || "en").toUpperCase()}
        <ChevronDown size={14} />
      </button>
      {isOpen && (
        <div style={{ position: "absolute", right: 0, top: "100%", marginTop: "8px", width: "120px", background: "#1E293B", border: "1px solid #334155", borderRadius: "8px", overflow: "hidden", zIndex: 50, boxShadow: "0 10px 15px -3px rgba(0, 0, 0, 0.5)" }}>
          <button 
            onClick={() => toggleLang('en')}
            style={{ width: "100%", textAlign: "left", padding: "10px 12px", fontSize: "13px", color: "#E2E8F0", background: "transparent", border: "none", cursor: "pointer", transition: "background 0.2s" }}
            onMouseEnter={(e) => e.currentTarget.style.background = "#334155"}
            onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
          >
            {t("header.en", "English")}
          </button>
          <button 
            onClick={() => toggleLang('fr')}
            style={{ width: "100%", textAlign: "left", padding: "10px 12px", fontSize: "13px", color: "#E2E8F0", background: "transparent", border: "none", cursor: "pointer", transition: "background 0.2s" }}
            onMouseEnter={(e) => e.currentTarget.style.background = "#334155"}
            onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
          >
            {t("header.fr", "Français")}
          </button>
        </div>
      )}
    </div>
  );
}

export default function Layout() {
  const { t } = useTranslation();
  const location = useLocation();
  const path = location.pathname === "/" ? "/" : "/" + location.pathname.split("/")[1];
  
  const getMeta = (p: string) => {
    const keyMap: Record<string, string> = {
      "/accueil": "accueil",
      "/company": "company",
      "/company-intelligence": "company-intelligence",
      "/field-intel": "field-intel",
      "/deal-intelligence": "deal-intelligence",
      "/market": "market",
      "/analyst": "analyst",
      "/admin": "admin",
    };
    const key = keyMap[p];
    if (key) {
      return {
        title: t(`pages.${key}.title`, PAGE_TITLES[p]?.title),
        subtitle: t(`pages.${key}.subtitle`, PAGE_TITLES[p]?.subtitle)
      };
    }
    return PAGE_TITLES[p] ?? { title: t("header.title", "Platform"), subtitle: t("header.subtitle", "Market Opportunities & Prospection Platform") };
  };

  const meta = getMeta(path);

  const { data: oppSummary } = useQuery({
    queryKey: ["opp-summary-badge"],
    queryFn: () => fetch(`${API}/api/opportunities/summary`).then((r) => r.json()),
    staleTime: 30000,
    retry: 1,
  });

  const signalCount =
    oppSummary?.strong_signals != null && oppSummary?.moderate_signals != null
      ? oppSummary.strong_signals + oppSummary.moderate_signals
      : null;

  // Hide topbar on Alpha Drop and AI Analyst pages for a cleaner full-screen experience
  const hideTopbar = path === "/accueil" || path === "/analyst";

  return (
    <div
      className="flex h-screen overflow-hidden"
      style={{ background: "radial-gradient(circle at top right, #1E293B 0%, #0F172A 40%, #020617 100%)", color: "#F9FAFB", fontFamily: "'DM Sans', sans-serif" }}
    >
      {/* ─── Sidebar ─── */}
      <aside
        className="flex flex-col flex-shrink-0 overflow-y-auto"
        style={{ width: 220, background: "rgba(15,23,42,0.4)", backdropFilter: "blur(12px)", borderRight: "1px solid rgba(255,255,255,0.05)" }}
      >
        {/* Brand */}
        <div className="flex items-center" style={{ padding: "24px 20px 20px", gap: 10 }}>
          <img 
            src="/ui/team2.png" 
            alt="Teamwill Logo" 
            style={{ width: 42, height: 42, borderRadius: 8, objectFit: "cover" }} 
          />
          <div>
            <div style={{ color: "#F9FAFB", fontWeight: 600, fontSize: 13, lineHeight: 1 }}>TEAMWILL</div>
            <div style={{ color: "#6B7280", fontWeight: 400, fontSize: 11, marginTop: 3 }}>{t("nav.market_intel", "Market Intelligence")}</div>
          </div>
        </div>

        {/* Main nav */}
        <nav style={{ padding: "8px 12px", marginTop: 8, flex: 1 }}>
          {mainNav.map(({ to, label, icon: Icon, key }) => (
            <NavLink key={to} to={to} end={to === "/"} style={{ textDecoration: "none" }}>
              {({ isActive }) => (
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    padding: "10px 12px",
                    borderRadius: 8,
                    fontSize: 13,
                    fontWeight: 500,
                    color: isActive ? "#F9FAFB" : "#9CA3AF",
                    backgroundColor: isActive ? "#1F2937" : "transparent",
                    cursor: "pointer",
                    marginBottom: 2,
                    transition: "all 150ms ease",
                  }}
                  onMouseEnter={(e) => {
                    if (!isActive) {
                      e.currentTarget.style.backgroundColor = "rgba(31,41,55,0.5)";
                      e.currentTarget.style.color = "#D1D5DB";
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!isActive) {
                      e.currentTarget.style.backgroundColor = "transparent";
                      e.currentTarget.style.color = "#9CA3AF";
                    }
                  }}
                >
                  <Icon size={16} style={{ color: isActive ? "#6366f1" : "inherit" }} strokeWidth={2} />
                  <span>{t(`nav.${key}`, label)}</span>
                </div>
              )}
            </NavLink>
          ))}
        </nav>

        {/* Admin link (bottom) */}
        <div style={{ padding: "0 12px 8px" }}>
          <NavLink to="/admin" style={{ textDecoration: "none" }}>
            {({ isActive }) => (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "10px 12px",
                  borderRadius: 8,
                  fontSize: 12,
                  fontWeight: 500,
                  color: isActive ? "#F9FAFB" : "#6B7280",
                  backgroundColor: isActive ? "#1F2937" : "transparent",
                  cursor: "pointer",
                  transition: "all 150ms ease",
                }}
                onMouseEnter={(e) => {
                  if (!isActive) {
                    e.currentTarget.style.backgroundColor = "rgba(31,41,55,0.5)";
                    e.currentTarget.style.color = "#D1D5DB";
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isActive) {
                    e.currentTarget.style.backgroundColor = "transparent";
                    e.currentTarget.style.color = "#6B7280";
                  }
                }}
              >
                <Settings size={14} style={{ color: isActive ? "#6366f1" : "inherit" }} strokeWidth={2} />
                <span>{t("nav.admin", "Admin")}</span>
              </div>
            )}
          </NavLink>
        </div>

        {/* User Auth Section */}
        <div style={{ padding: "8px 12px", borderTop: "1px solid rgba(255,255,255,0.05)" }}>
          {localStorage.getItem('access_token') ? (
            <div style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.05)", borderRadius: "8px", padding: "8px 10px", display: "flex", flexDirection: "column", gap: "6px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <div style={{ width: "24px", height: "24px", borderRadius: "50%", background: "linear-gradient(135deg, #6366F1 0%, #EC4899 100%)", display: "flex", alignItems: "center", justifyItems: "center", justifyContent: "center", fontSize: "10px", fontWeight: "bold", color: "#FFF" }}>
                  {(localStorage.getItem('user_name') || "U")[0].toUpperCase()}
                </div>
                <div style={{ display: "flex", flexDirection: "column", overflow: "hidden" }}>
                  <span style={{ fontSize: "12px", fontWeight: 600, color: "#F9FAFB", textOverflow: "ellipsis", overflow: "hidden", whiteSpace: "nowrap" }}>
                    {localStorage.getItem('user_name') || "User"}
                  </span>
                  <span style={{ fontSize: "9px", color: "#10B981" }}>Verified Account</span>
                </div>
              </div>
              <button 
                onClick={() => {
                  localStorage.removeItem('access_token');
                  localStorage.removeItem('user_name');
                  window.location.reload();
                }}
                style={{ width: "100%", padding: "4px", fontSize: "11px", color: "#EF4444", background: "rgba(239, 68, 68, 0.05)", border: "1px solid rgba(239, 68, 68, 0.1)", borderRadius: "4px", cursor: "pointer", transition: "background 0.2s" }}
                onMouseEnter={(e) => e.currentTarget.style.background = "rgba(239, 68, 68, 0.15)"}
                onMouseLeave={(e) => e.currentTarget.style.background = "rgba(239, 68, 68, 0.05)"}
              >
                Sign Out
              </button>
            </div>
          ) : (
            <NavLink to="/auth" style={{ textDecoration: "none" }}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "10px 12px",
                  borderRadius: 8,
                  fontSize: 12,
                  fontWeight: 500,
                  color: "#38BDF8",
                  backgroundColor: "rgba(56, 189, 248, 0.05)",
                  border: "1px solid rgba(56, 189, 248, 0.1)",
                  cursor: "pointer",
                  transition: "all 150ms ease",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = "rgba(56, 189, 248, 0.15)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = "rgba(56, 189, 248, 0.05)";
                }}
              >
                <div style={{ width: 14, height: 14, borderRadius: "50%", border: "2px solid #38BDF8", display: "inline-block" }} />
                <span>Sign In / Register</span>
              </div>
            </NavLink>
          )}
        </div>

        {/* Version footer */}
        <div style={{ padding: "16px 12px", borderTop: "1px solid #1F2937", fontSize: 10, color: "#374151" }}>
          {t("nav.version", "v2.0 · Real data only")}
        </div>
      </aside>

      {/* ─── Main content ─── */}
      <div className="flex flex-col flex-1 overflow-hidden">
        {/* Topbar — hidden on Intelligence Brief */}
        {!hideTopbar && (
          <header
            className="flex-shrink-0 flex items-center justify-between sticky top-0 z-30"
            style={{ height: 56, background: "rgba(15,23,42,0.4)", backdropFilter: "blur(12px)", borderBottom: "1px solid rgba(255,255,255,0.05)", padding: "0 32px" }}
          >
            <div>
              <h1 style={{ fontSize: 16, fontWeight: 600, color: "#F9FAFB", lineHeight: 1.3 }}>{meta.title}</h1>
              <p style={{ fontSize: 12, fontWeight: 400, color: "#6B7280", marginTop: 2 }}>{meta.subtitle}</p>
            </div>
            <div className="flex items-center" style={{ gap: 16 }}>
              <LiveIndicator />
              <span
                className="inline-flex items-center"
                style={{
                  gap: 6, fontSize: 11, fontWeight: 500, padding: "3px 10px",
                  borderRadius: 20, backgroundColor: "#451a03", color: "#F59E0B", border: "1px solid #92400e",
                }}
              >
                <span style={{ width: 6, height: 6, borderRadius: "50%", backgroundColor: "#F59E0B", display: "inline-block" }} />
                {signalCount != null ? `${signalCount} signals` : "—"}
              </span>
              <LanguageSwitcher />
              <a
                href="/docs"
                target="_blank"
                rel="noreferrer"
                style={{ fontSize: 12, color: "#6B7280", textDecoration: "none", transition: "color 150ms" }}
                onMouseEnter={(e) => { e.currentTarget.style.color = "#9CA3AF"; }}
                onMouseLeave={(e) => { e.currentTarget.style.color = "#6B7280"; }}
              >
                API Docs
              </a>
              <span style={{ fontSize: 12, color: "#6B7280" }}>
                {new Date().toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })}
              </span>
            </div>
          </header>
        )}

        {/* Page content */}
        <main className="flex-1 overflow-y-auto" style={{ background: "transparent" }}>
          <Outlet />
        </main>
      </div>

      {path !== "/field-intel" && path !== "/analyst" && <AskAiDrawer />}
    </div>
  );
}
