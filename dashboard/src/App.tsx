import { HashRouter, Route, Routes, Navigate } from "react-router-dom";
import Layout from "./components/Layout";
import WeeklyBrief from "./pages/WeeklyBrief";
import Overview from "./pages/Overview";
import Brands from "./pages/Brands";
import Listings from "./pages/Listings";
import Pricing from "./pages/Pricing";
import Articles from "./pages/Articles";
import Operations from "./pages/Operations";
import Opportunities from "./pages/Opportunities";
import Analyst from "./pages/Analyst";
import Sources from "./pages/Sources";
import InsuranceLandscape from "./pages/InsuranceLandscape";
import MLDashboard from "./pages/MLDashboard";
import CompanyRadar from "./pages/CompanyRadar";
import FieldIntel from "./pages/FieldIntel";
import Admin from "./pages/Admin";

export default function App() {
  return (
    <HashRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<WeeklyBrief />} />
          <Route path="company" element={<CompanyRadar />} />
          <Route path="field-intel" element={<FieldIntel />} />
          <Route path="market" element={<Overview />} />
          <Route path="analyst" element={<Analyst />} />
          <Route path="admin" element={<Admin />} />
          <Route path="opportunities" element={<Opportunities />} />
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
