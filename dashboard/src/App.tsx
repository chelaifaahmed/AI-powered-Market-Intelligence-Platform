import { HashRouter, Route, Routes, Navigate } from "react-router-dom";
import Layout from "./components/Layout";
import Auth from "./pages/Auth";
import WeeklyBrief from "./pages/WeeklyBrief";
import NarrativeBrief from "./pages/NarrativeBrief";
import Overview from "./pages/Overview";
import Brands from "./pages/Brands";
import Listings from "./pages/Listings";
import Pricing from "./pages/Pricing";
import Articles from "./pages/Articles";
import Operations from "./pages/Operations";
import Opportunities from "./pages/Opportunities";
import OpportunitiesV2 from "./pages/OpportunitiesV2";
import Analyst from "./pages/Analyst";
import Sources from "./pages/Sources";
import InsuranceLandscape from "./pages/InsuranceLandscape";
import MLDashboard from "./pages/MLDashboard";
import CompanyRadar from "./pages/CompanyRadar";
import CompanyIntelligence from "./pages/CompanyIntelligence";
import FieldIntel from "./pages/FieldIntel";
import MarketPositioning from "./pages/MarketPositioning";
import Admin from "./pages/Admin";

// ─── Auth Guard ───────────────────────────────────────────────────────────────
// Redirects unauthenticated users to /auth. Token is set by the login endpoint.
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem("access_token");
  if (!token) {
    return <Navigate to="/auth" replace />;
  }
  return <>{children}</>;
}

export default function App() {
  return (
    <HashRouter>
      <Routes>
        {/* Public: Auth page */}
        <Route path="/auth" element={<Auth />} />

        {/* Protected: entire dashboard requires a valid token */}
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Navigate to="/accueil" replace />} />
          <Route path="accueil" element={<NarrativeBrief />} />
          <Route path="company" element={<CompanyRadar />} />
          <Route path="field-intel" element={<FieldIntel />} />
          <Route path="deal-intelligence" element={<MarketPositioning />} />
          <Route path="market" element={<Overview />} />
          <Route path="analyst" element={<Analyst />} />
          <Route path="admin" element={<Admin />} />
          <Route path="opportunities" element={<Opportunities />} />
          <Route path="opportunities-v2" element={<OpportunitiesV2 />} />
          <Route path="company-intelligence" element={<CompanyIntelligence />} />
          <Route path="ml-intelligence" element={<MLDashboard />} />
          <Route path="brands" element={<Brands />} />
          <Route path="insurance" element={<InsuranceLandscape />} />
          <Route path="listings" element={<Listings />} />
          <Route path="pricing" element={<Pricing />} />
          <Route path="articles" element={<Articles />} />
          <Route path="operations" element={<Operations />} />
          <Route path="sources" element={<Sources />} />
          <Route path="overview" element={<Navigate to="/market" replace />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </HashRouter>
  );
}

