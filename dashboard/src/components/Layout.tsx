import { NavLink, Outlet, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  Building2,
  TrendingUp,
  MessageSquare,
  Settings,
  Telescope,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import AskAiDrawer from "./AskAiDrawer";
import LiveIndicator from "./LiveIndicator";

const API = import.meta.env.VITE_API_URL || "";

const mainNav = [
  { to: "/", label: "Intelligence Brief", icon: LayoutDashboard },
  { to: "/company", label: "Company Radar", icon: Building2 },
  { to: "/field-intel", label: "Field Intel", icon: Telescope },
  { to: "/market", label: "Market Pulse", icon: TrendingUp },
  { to: "/analyst", label: "AI Analyst", icon: MessageSquare },
];

const PAGE_TITLES: Record<string, { title: string; subtitle: string }> = {
  "/": { title: "Intelligence Brief", subtitle: "Executive summary & key signals" },
  "/company": { title: "Company Radar", subtitle: "Track companies, clusters & ERP signals" },
  "/field-intel": { title: "Field Intel", subtitle: "Market news & pricing data for your sales & prospection calls" },
  "/market": { title: "Market Pulse", subtitle: "Operational health & top-level intelligence signals" },
  "/analyst": { title: "AI Analyst", subtitle: "Chat with your data using Claude AI" },
  "/admin": { title: "Admin", subtitle: "Operations, sources & system management" },
  "/opportunities": { title: "Market Opportunities", subtitle: "Sales intelligence signals & opportunity scoring" },
  "/ml-intelligence": { title: "Intelligence Segments", subtitle: "AI-driven clustering & ERP modernization signals" },
  "/brands": { title: "Brand Intelligence", subtitle: "Reputation trends, sentiment analysis & review insights" },
  "/insurance": { title: "Insurance Landscape", subtitle: "Insurance market analysis & competitive intelligence" },
  "/listings": { title: "Vehicle Market", subtitle: "Marketplace data, pricing & dealer insights" },
  "/pricing": { title: "Competitor Pricing", subtitle: "Insurance pricing snapshots & market positioning" },
  "/articles": { title: "Market Articles", subtitle: "Industry news, trend analysis & content intelligence" },
  "/operations": { title: "Operations Center", subtitle: "Pipeline health, data quality & source monitoring" },
  "/sources": { title: "Source Management", subtitle: "Manage scraping sources, keywords & data feeds" },
};

export default function Layout() {
  const location = useLocation();
  const path = location.pathname === "/" ? "/" : "/" + location.pathname.split("/")[1];
  const meta = PAGE_TITLES[path] ?? { title: "Platform", subtitle: "Market Intelligence Platform" };

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

  // Hide topbar on Intelligence Brief — it has its own header
  const hideTopbar = path === "/";

  return (
    <div
      className="flex h-screen overflow-hidden"
      style={{ backgroundColor: "#0A0F1E", color: "#F9FAFB", fontFamily: "'DM Sans', sans-serif" }}
    >
      {/* ─── Sidebar ─── */}
      <aside
        className="flex flex-col flex-shrink-0 overflow-y-auto"
        style={{ width: 220, backgroundColor: "#0A0F1E", borderRight: "1px solid #1F2937" }}
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
            <div style={{ color: "#6B7280", fontWeight: 400, fontSize: 11, marginTop: 3 }}>Market Intelligence</div>
          </div>
        </div>

        {/* Main nav */}
        <nav style={{ padding: "8px 12px", marginTop: 8, flex: 1 }}>
          {mainNav.map(({ to, label, icon: Icon }) => (
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
                  <span>{label}</span>
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
                <span>Admin</span>
              </div>
            )}
          </NavLink>
        </div>

        {/* Version footer */}
        <div style={{ padding: "16px 12px", borderTop: "1px solid #1F2937", fontSize: 10, color: "#374151" }}>
          v2.0 · Real data only
        </div>
      </aside>

      {/* ─── Main content ─── */}
      <div className="flex flex-col flex-1 overflow-hidden">
        {/* Topbar — hidden on Intelligence Brief */}
        {!hideTopbar && (
          <header
            className="flex-shrink-0 flex items-center justify-between sticky top-0 z-30"
            style={{ height: 56, backgroundColor: "#0A0F1E", borderBottom: "1px solid #1F2937", padding: "0 32px" }}
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
        <main className="flex-1 overflow-y-auto" style={{ backgroundColor: "#0A0F1E" }}>
          <Outlet />
        </main>
      </div>

      <AskAiDrawer />
    </div>
  );
}
