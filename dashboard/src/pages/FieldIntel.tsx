import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ExternalLink, Newspaper, MapPin, Car, Globe, Search, X, BookOpen } from "lucide-react";
import { api } from "../api/client";
import type { Article, Listing } from "../api/client";

const API_BASE = import.meta.env.VITE_API_URL || "";

const API = import.meta.env.VITE_API_URL || "";

// ─── Types ──────────────────────────────────────────────────────────────────

interface ArticleSummaryData {
  article_id: string;
  title: string;
  summary: string;
  source_url: string;
  publication_date: string | null;
  source_name: string | null;
}

// ─── Helpers ────────────────────────────────────────────────────────────────

/** Render **bold** markdown spans as <strong> elements */
function renderBold(text: string): React.ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={i} style={{ color: "#F9FAFB", fontWeight: 700 }}>{part.slice(2, -2)}</strong>;
    }
    return <span key={i}>{part}</span>;
  });
}

function fmtPrice(price: number | null, currency: string) {
  if (price == null) return "—";
  if (currency === "TND") return `${Math.round(price).toLocaleString("fr-TN")} TND`;
  return `€${Math.round(price).toLocaleString("en-EU")}`;
}

function fmtDate(d: string | null) {
  if (!d) return "";
  try {
    return new Date(d).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
  } catch {
    return d;
  }
}

function getDomain(url: string) {
  try { return new URL(url).hostname.replace("www.", ""); } catch { return url; }
}

/** Extract clean brand label from DB name.
 *  "SATA (Toyota TN)" → "Toyota"
 *  "Ennakl (Volkswagen/Audi TN)" → "Volkswagen"
 *  "Chery (TN)" → "Chery"
 *  "BMW" → "BMW"
 */
function cleanBrand(raw: string | null): string {
  if (!raw) return "—";
  const m = raw.match(/^(.+?)\s*\(([^)]+)\)$/);
  if (m) {
    const prefix = m[1].trim();                            // dealer name: "SATA", "Ennakl", "Chery"
    const inside = m[2].replace(/\s*TN$/, "").split("/")[0].trim(); // car make: "Toyota", "Volkswagen", ""
    return inside || prefix;                               // prefer make from inside; fallback to prefix
  }
  return raw;
}

/** Extract trim spec from automobile.tn URL: /fr/neuf/toyota/yaris-cross/1.5-l-cvt-2023 → "1.5L CVT 2023" */
function extractTrim(url: string): string | null {
  try {
    const parts = new URL(url).pathname.split("/").filter(Boolean);
    // automobile.tn: fr / neuf / brand / model / trim
    const neuIdx = parts.indexOf("neuf");
    if (neuIdx >= 0 && parts.length > neuIdx + 3) {
      return parts[neuIdx + 3]
        .replace(/-/g, " ")
        .replace(/\b(\d+)l\b/gi, "$1L")
        .replace(/\b\w/g, (c) => c.toUpperCase());
    }
    return null;
  } catch {
    return null;
  }
}

// Known promotional prefixes to strip from model names
const _PROMO_PREFIXES = /^(Offre\s[\w\s]*?\s|Nouveau\s|Nouvelle\s|Promo\s(flash\s)?|Promo\s[\w]+\s)/i;
// Known brand names that may bleed into the model string
const _BRAND_INFIX = /^(Toyota|Volkswagen|VW|BMW|Mercedes|Renault|Peugeot|Citroën|Citroen|Kia|Hyundai|Chery|Dacia|Fiat|Audi|Seat|Skoda|Ford|Honda|Nissan|MG|BYD|Changan|Geely)\s+/i;

/** Clean model name: strip promotional text and repeated brand name.
 *  "Promo Chery Tiggo 7 Pro" → "Tiggo 7 Pro"
 *  "Offre 110 ans BMW Série 1" → "Série 1"
 *  "Nouveau Chery Tiggo 7 PHEV" → "Tiggo 7 PHEV"
 *  "Yaris Hybride" → "Yaris Hybride"
 */
function cleanModel(raw: string | null): string {
  if (!raw) return "—";
  let s = raw.trim();
  s = s.replace(_PROMO_PREFIXES, "");   // remove promo prefix
  s = s.replace(_BRAND_INFIX, "");       // remove repeated brand name
  return s.trim() || raw.trim();
}

/** Derive a short sales-angle label from the article title using keyword matching.
 *  Returns a label + accent color, or null if the article has no relevance to
 *  TEAMWILL's context (cars, insurance, ERP, economy, fuel). */
function getSalesAngle(title: string): { label: string; color: string } | null {
  const t = title.toLowerCase();

  // Fuel & energy — highest priority (war/politics only relevant if connected here)
  if (/oil\b|p[eé]trole|crude|opec|fuel\b|carburant|essence\b|diesel\b|gas price|prix.*(gaz|essenc|carb)|energy crisis|[eé]nergie/.test(t))
    return { label: "Fuel & energy costs", color: "#F59E0B" };

  // EV / green mobility
  if (/electric vehicle|\bev\b|plug.in|hybrid|hybride|tesla|battery.*car|recharge|borne.*recharge|zero.emission|v[eé]hicule [eé]lectrique/.test(t))
    return { label: "EV transition", color: "#10B981" };

  // Insurance — broad
  if (/insurance|assurance|sinistre|claim\b|underwriting|reinsur|r[eé]assur|premium.*insur|insur.*premium|prime.*assur|assur.*prime|liability.*insur|motor.*insur|auto.*insur|assurance.*auto|p\/c insurance|property casualty|actuar|courtier|risk.*insur/.test(t))
    return { label: "Insurance market", color: "#818CF8" };

  // ERP / information systems / management software
  if (/\berp\b|odoo|oddo|\balfa\b|\bmiles\b|\bsap\b|oracle.*erp|dynamics.*365|logiciel de gestion|syst[eè]me d.information|enterprise resource|progiciel|information management|gestion de l.information|digital transformation|transformation digitale|legacy system|syst[eè]me obsol/.test(t))
    return { label: "ERP & digitisation", color: "#A78BFA" };

  // Customer dissatisfaction / experience
  if (/customer satisfaction|satisfaction client|insatisfaction|complaint|r[eé]clamation|customer service|service client|avis client|nps\b|customer experience|exp[eé]rience client|poor service|mauvais service|after.?sales/.test(t))
    return { label: "Customer experience", color: "#F43F5E" };

  // Engine / mechanical / recall
  if (/engine\b|moteur\b|recall\b|rappel constructeur|gearbox|transmission\b|turbo\b|breakdown|panne\b|d[eé]faut m[eé]can|mechanical failure|p[eè]ces d[eé]tach[eé]es|spare parts|r[eé]paration auto/.test(t))
    return { label: "Engine & reliability", color: "#FB923C" };

  // Trade / tariffs / supply chain
  if (/tariff|tarif douanier|trade war|guerre commerciale|supply chain|import.*auto|export.*auto|customs duty|p[eé]nurie|shortage.*part|component.*short/.test(t))
    return { label: "Trade & supply chain", color: "#EF4444" };

  // Pricing pressure / inflation
  if (/inflation|hausse des prix|price.*rise|rising cost|co[uû]t.*augment|prix.*voiture|car.*price|vehicle.*price|prix.*carburant|fuel.*cost|repair.*cost|co[uû]t.*r[eé]paration/.test(t))
    return { label: "Pricing pressure", color: "#F97316" };

  // Car brands / auto sector
  if (/\bcar\b|\bcars\b|\bauto\b|vehicle|voiture|automobile|dealer\b|dealership|concessionnaire|stellantis|renault|peugeot|volkswagen|\bvw\b|hyundai|\bkia\b|toyota|mercedes|\bbmw\b|\bford\b|citro[eë]n|dacia|chery|\bmg\b|\bbyd\b|audi|volvo|porsche|honda|nissan|opel|ennakl|stafim|sata/.test(t))
    return { label: "Auto sector", color: "#3B82F6" };

  // Digital / AI / tech (industry-relevant)
  if (/\bai\b|artificial intelligence|intelligence artificielle|\bml\b|machine learning|automation|automatisation|digital.*insur|insur.*digital|insurtech|fintech|telematics|t[eé]l[eé]matique|connected car|voiture connect[eé]e|adas|autonomous/.test(t))
    return { label: "Tech & innovation", color: "#22D3EE" };

  // Economic outlook / finance
  if (/[eé]conomie|economic outlook|march[eé].*auto|auto.*march[eé]|financial.*result|r[eé]sultat.*financ|croissance|recession|r[eé]cession|gdp|pib\b|investissement|investment.*auto|banque centrale|interest rate|taux directeur|dinar|budget.*transport|fiscal.*auto/.test(t))
    return { label: "Economic outlook", color: "#34D399" };

  // Tunisian industry specifics
  if (/tunisi|industrie.*auto.*tun|tun.*auto|march[eé].*tun|assurance.*tun|tun.*assurance|bct\b|biat\b|attijari|zone franche|ide\b/.test(t))
    return { label: "Tunisian market", color: "#FBBF24" };

  // Managerial / operational problems (for ERP sales angle)
  if (/management problem|operational.*ineffici|bottleneck|legacy.*system|retard num[eé]rique|digital gap|expert opinion|industry report|[eé]tude de march[eé]|rapport sectoriel|analyst.*forecast|market outlook|prevision|perspective.*march[eé]/.test(t))
    return { label: "Industry outlook", color: "#94A3B8" };

  return null;
}

function getCategoryColor(cat: string | null): string {
  const c = (cat || "").toLowerCase();
  if (c.includes("insurance")) return "#6366f1";
  if (c.includes("ev") || c.includes("electric")) return "#10B981";
  if (c.includes("market") || c.includes("keyword")) return "#F59E0B";
  if (c.includes("technology")) return "#3B82F6";
  if (c.includes("regulation")) return "#EF4444";
  return "#6B7280";
}

function getRegionBg(region: string | null): string {
  const r = (region || "").toUpperCase();
  if (r === "TN") return { bg: "rgba(251,191,36,0.12)", color: "#FBBF24", label: "TN" } as never;
  if (r === "EU") return { bg: "rgba(99,102,241,0.12)", color: "#818CF8", label: "EU" } as never;
  return { bg: "rgba(107,114,128,0.12)", color: "#9CA3AF", label: region || "—" } as never;
}

const regionBadge = (region: string | null) => {
  const r = (region || "").toUpperCase();
  if (r === "TN") return { bg: "rgba(251,191,36,0.12)", color: "#FBBF24", label: "TN" };
  if (r === "EU") return { bg: "rgba(99,102,241,0.12)", color: "#818CF8", label: "EU" };
  return { bg: "rgba(107,114,128,0.12)", color: "#9CA3AF", label: region || "Global" };
};

// ─── Sub-components ─────────────────────────────────────────────────────────

function StatPill({ label, value, color }: { label: string; value: number | string; color: string }) {
  return (
    <div style={{
      background: "#111827", border: "1px solid #1F2937", borderRadius: 10,
      padding: "14px 20px", display: "flex", flexDirection: "column", gap: 4,
    }}>
      <span style={{ fontSize: 22, fontWeight: 700, color }}>{value}</span>
      <span style={{ fontSize: 12, color: "#6B7280", fontWeight: 500 }}>{label}</span>
    </div>
  );
}

function TabBar({
  tabs, active, onChange,
}: {
  tabs: { key: string; label: string }[];
  active: string;
  onChange: (k: string) => void;
}) {
  return (
    <div style={{ display: "flex", gap: 4, background: "#111827", borderRadius: 8, padding: 4 }}>
      {tabs.map((t) => (
        <button
          key={t.key}
          onClick={() => onChange(t.key)}
          style={{
            padding: "6px 14px", borderRadius: 6, fontSize: 12, fontWeight: 600,
            border: "none", cursor: "pointer", transition: "all 150ms ease",
            background: active === t.key ? "#1F2937" : "transparent",
            color: active === t.key ? "#F9FAFB" : "#6B7280",
          }}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

function SectionHeader({ icon: Icon, title, sub }: { icon: React.ElementType; title: string; sub: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
      <div style={{
        width: 32, height: 32, borderRadius: 8, background: "rgba(99,102,241,0.15)",
        display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
      }}>
        <Icon size={16} style={{ color: "#6366f1" }} />
      </div>
      <div>
        <div style={{ fontSize: 14, fontWeight: 700, color: "#F9FAFB" }}>{title}</div>
        <div style={{ fontSize: 11, color: "#6B7280", marginTop: 1 }}>{sub}</div>
      </div>
    </div>
  );
}

// ─── Article card ────────────────────────────────────────────────────────────

function ArticleCard({ article, onClick }: { article: Article; onClick: () => void }) {
  const rb = regionBadge(article.region);
  const catColor = getCategoryColor(article.category);
  const angle = getSalesAngle(article.title);
  return (
    <div
      style={{
        background: "#111827", border: "1px solid #1F2937", borderRadius: 10,
        padding: "14px 16px", marginBottom: 8, transition: "border-color 150ms ease, background 150ms ease",
        cursor: "pointer",
      }}
      onClick={onClick}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = "#6366f1";
        e.currentTarget.style.background = "#161D2E";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = "#1F2937";
        e.currentTarget.style.background = "#111827";
      }}
    >
      {/* Top row: category + region + date */}
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8, flexWrap: "wrap" }}>
        {article.category && (
          <span style={{
            fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 20,
            background: `${catColor}18`, color: catColor, letterSpacing: "0.3px",
            textTransform: "uppercase",
          }}>
            {article.category}
          </span>
        )}
        <span style={{
          fontSize: 10, fontWeight: 600, padding: "2px 8px", borderRadius: 20,
          background: rb.bg, color: rb.color,
        }}>
          {rb.label}
        </span>
        <span style={{ fontSize: 11, color: "#4B5563", marginLeft: "auto" }}>
          {fmtDate(article.publication_date || article.scraped_at)}
        </span>
      </div>

      {/* Title */}
      <div style={{
        fontSize: 13, fontWeight: 600, color: "#E5E7EB", lineHeight: 1.5, marginBottom: 6,
      }}>
        {article.title}
      </div>

      {/* Sales angle pill */}
      {angle && (
        <div style={{ marginBottom: 8 }}>
          <span style={{
            fontSize: 10, fontWeight: 600, padding: "2px 8px", borderRadius: 20,
            background: `${angle.color}18`, color: angle.color,
            border: `1px solid ${angle.color}30`,
          }}>
            ↳ {angle.label}
          </span>
        </div>
      )}

      {/* Source + read icon */}
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <Globe size={11} style={{ color: "#4B5563" }} />
        <span style={{ fontSize: 11, color: "#4B5563" }}>{getDomain(article.source_url)}</span>
        <BookOpen size={11} style={{ color: "#6366f1", marginLeft: "auto" }} />
      </div>
    </div>
  );
}

// ─── Listing card ────────────────────────────────────────────────────────────

function ListingCard({ listing }: { listing: Listing }) {
  const isTN = listing.currency === "TND";
  const accentColor = isTN ? "#FBBF24" : "#6366f1";

  const brand = cleanBrand(listing.brand_name);
  const model = cleanModel(listing.model_name);
  const trim  = extractTrim(listing.listing_url);

  // Full label: "Toyota · Yaris Cross Hybride" — trim shown separately
  const fullName = model !== "—" ? `${brand} · ${model}` : brand;

  return (
    <a href={listing.listing_url} target="_blank" rel="noreferrer" style={{ textDecoration: "none", display: "block" }}>
      <div
        style={{
          background: "#111827", border: "1px solid #1F2937", borderRadius: 10,
          padding: "12px 14px", marginBottom: 8, transition: "border-color 150ms ease",
        }}
        onMouseEnter={(e) => { e.currentTarget.style.borderColor = accentColor + "60"; }}
        onMouseLeave={(e) => { e.currentTarget.style.borderColor = "#1F2937"; }}
      >
        {/* Top row: brand · model + price */}
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 10, marginBottom: 6 }}>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{
              fontSize: 13, fontWeight: 700, color: "#E5E7EB",
              whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
            }}>
              {fullName}
            </div>
            {trim && (
              <div style={{ fontSize: 11, color: "#6B7280", marginTop: 2 }}>{trim}</div>
            )}
          </div>
          <div style={{
            background: `${accentColor}15`, border: `1px solid ${accentColor}30`,
            borderRadius: 6, padding: "4px 10px", flexShrink: 0, textAlign: "right",
          }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: accentColor, lineHeight: 1 }}>
              {fmtPrice(listing.listed_price, listing.currency)}
            </div>
          </div>
        </div>

        {/* Bottom row: meta tags */}
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          {listing.country && (
            <span style={{ fontSize: 10, color: "#4B5563", display: "flex", alignItems: "center", gap: 3 }}>
              <MapPin size={9} />
              {listing.country}
            </span>
          )}
          {listing.mileage_km != null && (
            <span style={{ fontSize: 10, color: "#4B5563" }}>{listing.mileage_km.toLocaleString()} km</span>
          )}
          {listing.fuel_type && (
            <span style={{ fontSize: 10, color: "#4B5563" }}>{listing.fuel_type}</span>
          )}
          {listing.transmission && (
            <span style={{ fontSize: 10, color: "#4B5563" }}>{listing.transmission}</span>
          )}
          <ExternalLink size={10} style={{ color: "#374151", marginLeft: "auto" }} />
        </div>
      </div>
    </a>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

const ARTICLE_TABS = [
  { key: "all",       label: "All" },
  { key: "auto",      label: "Auto & EV" },
  { key: "insurance", label: "Insurance" },
  { key: "tn",        label: "Tunisia" },
  { key: "eu",        label: "Europe" },
  { key: "erp",       label: "ERP Systems" },
];

const LISTING_TABS = [
  { key: "all", label: "All" },
  { key: "TND", label: "Tunisia (TND)" },
  { key: "EUR", label: "Europe (EUR)" },
];

const PAGE = 12;

type SortMode = "newest" | "price_asc" | "price_desc";

export default function FieldIntel() {
  const [articleTab, setArticleTab] = useState("all");
  const [listingTab, setListingTab] = useState("all");
  const [articlePage, setArticlePage] = useState(0);
  const [listingPage, setListingPage] = useState(0);
  const [listingSearch, setListingSearch] = useState("");
  const [listingSort, setListingSort] = useState<SortMode>("newest");
  const [articleModal, setArticleModal] = useState<{ article: Article } | null>(null);

  // Derive article query params from active tab
  // relevant_only=true filters out off-topic articles (war, weather, politics)
  // keeping only those with automotive/insurance/economy keywords in the title
  const articleParams = (() => {
    if (articleTab === "insurance") return { category: "insurance", relevant_only: true };
    if (articleTab === "auto")      return { categories: "Automotive,automotive,EV,Market,Fleet,Keyword Search", relevant_only: true };
    if (articleTab === "tn")        return { region: "TN", relevant_only: true };
    if (articleTab === "eu")        return { region: "EU", relevant_only: true };
    if (articleTab === "erp")       return { search: "ERP" };
    return {};
  })();

  // Articles query
  const { data: artData, isLoading: artLoading } = useQuery({
    queryKey: ["field-articles", articleTab, articlePage],
    queryFn: () => api.articles({
      limit: PAGE,
      offset: articlePage * PAGE,
      origin: "scraped",
      ...articleParams,
    }),
    staleTime: 30000,
  });

  // Article summary query
  const { data: articleSummary, isLoading: summaryLoading, error: summaryError } = useQuery<ArticleSummaryData>({
    queryKey: ["article-summary", articleModal?.article.id],
    queryFn: () =>
      fetch(`${API_BASE}/api/article/${articleModal!.article.id}/summary`).then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      }),
    enabled: !!articleModal,
    staleTime: 300000,
  });

  // Listings query
  const { data: lstData, isLoading: lstLoading } = useQuery({
    queryKey: ["field-listings", listingTab, listingPage, listingSearch, listingSort],
    queryFn: () => {
      const params = new URLSearchParams({
        limit: String(PAGE),
        offset: String(listingPage * PAGE),
        origin: "scraped",
      });
      if (listingTab !== "all") params.set("currency", listingTab);
      if (listingSearch.trim()) params.set("search", listingSearch.trim());
      if (listingSort !== "newest") params.set("sort", listingSort);
      return fetch(`${API}/api/listings?${params}`).then((r) => r.json());
    },
    staleTime: 30000,
  });

  // Summary stats
  const { data: artCategories } = useQuery({
    queryKey: ["art-categories"],
    queryFn: () => api.articleCategories(),
    staleTime: 60000,
  });

  const { data: lstSummary } = useQuery({
    queryKey: ["listings-summary"],
    queryFn: () => api.listingsSummary(),
    staleTime: 60000,
  });

  // Secondary client-side filter: remove articles with no recognisable sales angle
  // (backend relevant_only handles the bulk; this removes edge-case false positives)
  const allArticles: Article[] = artData?.items ?? [];
  const articles: Article[] = articleTab === "all"
    ? allArticles
    : allArticles.filter(a => getSalesAngle(a.title) !== null);
  const totalArticles = artData?.total ?? 0;
  const listings: Listing[] = lstData?.items ?? [];
  const totalListings = lstData?.total ?? 0;

  const tnListings = lstSummary?.by_country?.find((c: { source: string; count: number }) => c.source === "TN")?.count ?? 0;
  const insuranceArticles = artCategories?.find((c) => c.category?.toLowerCase() === "insurance")?.count ?? 0;

  return (
    <div style={{ padding: "28px 32px", minHeight: "100vh", backgroundColor: "#0A0F1E" }}>

      {/* ── Stats bar ───────────────────────────────────────────────────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 12, marginBottom: 28 }}>
        <StatPill label="Market Articles" value={lstSummary ? totalArticles || "—" : "—"} color="#6366f1" />
        <StatPill label="Insurance Articles" value={insuranceArticles || "—"} color="#818CF8" />
      </div>

      {/* ── Single-column layout ───────────────────────────────────────────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 24, alignItems: "start" }}>

        {/* ── LEFT: Market News ───────────────────────────────────────────── */}
        <div>
          <div style={{
            background: "#0D1424", border: "1px solid #1F2937", borderRadius: 14, padding: "20px 20px 16px",
          }}>
            <SectionHeader
              icon={Newspaper}
              title="Market Intelligence Feed"
              sub="Industry news relevant to your prospection — click any article to read the source"
            />

            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
              <TabBar tabs={ARTICLE_TABS} active={articleTab} onChange={(k) => { setArticleTab(k); setArticlePage(0); }} />
              <span style={{ fontSize: 11, color: "#4B5563" }}>
                {totalArticles} article{totalArticles !== 1 ? "s" : ""}
              </span>
            </div>

            {/* Sales tip banner */}
            {articleTab === "insurance" && (
              <div style={{
                background: "rgba(99,102,241,0.08)", border: "1px solid rgba(99,102,241,0.2)",
                borderRadius: 8, padding: "10px 14px", marginBottom: 12,
                fontSize: 12, color: "#A5B4FC", lineHeight: 1.5,
              }}>
                <strong>Sales tip:</strong> Use these articles as conversation starters.
                Mention a recent trend when cold-calling insurance companies — it shows market awareness.
              </div>
            )}
            {articleTab === "tn" && (
              <div style={{
                background: "rgba(251,191,36,0.08)", border: "1px solid rgba(251,191,36,0.2)",
                borderRadius: 8, padding: "10px 14px", marginBottom: 12,
                fontSize: 12, color: "#FDE68A", lineHeight: 1.5,
              }}>
                <strong>Tunisia focus:</strong> Atlas Magazine + Business News TN —
                ideal briefing material before any call with a Tunisian insurer or dealer.
              </div>
            )}
            {articleTab === "eu" && (
              <div style={{
                background: "rgba(99,102,241,0.08)", border: "1px solid rgba(99,102,241,0.2)",
                borderRadius: 8, padding: "10px 14px", marginBottom: 12,
                fontSize: 12, color: "#A5B4FC", lineHeight: 1.5,
              }}>
                <strong>Europe focus:</strong> Automotive and insurance market news from EU sources —
                benchmark what European competitors are doing before positioning TEAMWILL's solutions.
              </div>
            )}
            {articleTab === "auto" && (
              <div style={{
                background: "rgba(16,185,129,0.08)", border: "1px solid rgba(16,185,129,0.2)",
                borderRadius: 8, padding: "10px 14px", marginBottom: 12,
                fontSize: 12, color: "#6EE7B7", lineHeight: 1.5,
              }}>
                <strong>Auto & EV:</strong> Market movements, EV launches, and fleet news —
                use these to speak credibly about the product landscape when prospecting dealers.
              </div>
            )}
            {articleTab === "erp" && (
              <div style={{
                background: "rgba(245,158,11,0.08)", border: "1px solid rgba(245,158,11,0.2)",
                borderRadius: 8, padding: "10px 14px", marginBottom: 12,
                fontSize: 12, color: "#FDE68A", lineHeight: 1.5,
              }}>
                <strong>ERP Systems:</strong> Industry trends in enterprise software adoption —
                use these articles to open conversations about digital transformation with prospects still on legacy systems.
              </div>
            )}

            {/* Article list */}
            {artLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <div key={i} style={{ background: "#111827", borderRadius: 10, height: 80, marginBottom: 8, opacity: 0.5,
                  animation: "pulse 1.5s ease-in-out infinite" }} />
              ))
            ) : articles.length === 0 ? (
              <div style={{ textAlign: "center", padding: "40px 0", color: "#4B5563", fontSize: 13 }}>
                No articles found for this filter.
              </div>
            ) : (
              articles.map((a) => <ArticleCard key={a.id} article={a} onClick={() => setArticleModal({ article: a })} />)
            )}

            {/* Pagination */}
            {totalArticles > PAGE && (
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 12, paddingTop: 12, borderTop: "1px solid #1F2937" }}>
                <button
                  onClick={() => setArticlePage((p) => Math.max(0, p - 1))}
                  disabled={articlePage === 0}
                  style={{
                    fontSize: 12, color: articlePage === 0 ? "#374151" : "#6366f1",
                    background: "none", border: "none", cursor: articlePage === 0 ? "default" : "pointer",
                  }}
                >
                  ← Previous
                </button>
                <span style={{ fontSize: 11, color: "#4B5563" }}>
                  {articlePage * PAGE + 1}–{Math.min((articlePage + 1) * PAGE, totalArticles)} of {totalArticles}
                </span>
                <button
                  onClick={() => setArticlePage((p) => p + 1)}
                  disabled={(articlePage + 1) * PAGE >= totalArticles}
                  style={{
                    fontSize: 12,
                    color: (articlePage + 1) * PAGE >= totalArticles ? "#374151" : "#6366f1",
                    background: "none", border: "none",
                    cursor: (articlePage + 1) * PAGE >= totalArticles ? "default" : "pointer",
                  }}
                >
                  Next →
                </button>
              </div>
            )}
          </div>
        </div>

        {/* ── RIGHT: Pricing Reference (Masked) ────────────────────────────────────── */}
        {false && (
        <div style={{ position: "sticky", top: 16 }}>
          <div style={{
            background: "#0D1424", border: "1px solid #1F2937", borderRadius: 14, padding: "20px 20px 16px",
          }}>
            <SectionHeader
              icon={Car}
              title="Pricing Reference"
              sub="Live market prices — use these when discussing market positioning with prospects"
            />

            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
              <TabBar tabs={LISTING_TABS} active={listingTab} onChange={(k) => { setListingTab(k); setListingPage(0); }} />
            </div>

            {/* Search + Sort controls */}
            <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
              {/* Search */}
              <div style={{ position: "relative", flex: 1 }}>
                <Search size={12} style={{
                  position: "absolute", left: 9, top: "50%", transform: "translateY(-50%)",
                  color: "#4B5563", pointerEvents: "none",
                }} />
                <input
                  type="text"
                  placeholder="Search brand or model…"
                  value={listingSearch}
                  onChange={(e) => { setListingSearch(e.target.value); setListingPage(0); }}
                  style={{
                    width: "100%", boxSizing: "border-box",
                    background: "#111827", border: "1px solid #1F2937", borderRadius: 7,
                    padding: "6px 10px 6px 28px", fontSize: 12, color: "#E5E7EB",
                    outline: "none",
                  }}
                  onFocus={(e) => { e.currentTarget.style.borderColor = "#6366f1"; }}
                  onBlur={(e) => { e.currentTarget.style.borderColor = "#1F2937"; }}
                />
              </div>
              {/* Sort */}
              <div style={{ display: "flex", gap: 4, background: "#111827", border: "1px solid #1F2937", borderRadius: 7, padding: 3, flexShrink: 0 }}>
                {(["newest", "price_asc", "price_desc"] as SortMode[]).map((mode) => {
                  const labels: Record<SortMode, string> = { newest: "Latest", price_asc: "Price ↑", price_desc: "Price ↓" };
                  const titles: Record<SortMode, string> = { newest: "Newest first", price_asc: "Price: low → high", price_desc: "Price: high → low" };
                  const active = listingSort === mode;
                  return (
                    <button
                      key={mode}
                      title={titles[mode]}
                      onClick={() => { setListingSort(mode); setListingPage(0); }}
                      style={{
                        padding: "4px 8px", borderRadius: 5, fontSize: 11, fontWeight: 600,
                        border: "none", cursor: "pointer", transition: "all 150ms ease",
                        background: active ? "#1F2937" : "transparent",
                        color: active ? (mode === "price_desc" ? "#6366f1" : mode === "price_asc" ? "#10B981" : "#F9FAFB") : "#6B7280",
                      }}
                    >
                      {labels[mode]}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Context banner */}
            {listingTab === "TND" && (
              <div style={{
                background: "rgba(251,191,36,0.08)", border: "1px solid rgba(251,191,36,0.2)",
                borderRadius: 8, padding: "10px 14px", marginBottom: 12,
                fontSize: 11, color: "#FDE68A", lineHeight: 1.5,
              }}>
                New car prices from <strong>automobile.tn</strong> — official dealer prices in Tunisia.
                Useful when discussing the local automotive market with Tunisian clients.
              </div>
            )}
            {listingTab === "EUR" && (
              <div style={{
                background: "rgba(99,102,241,0.08)", border: "1px solid rgba(99,102,241,0.2)",
                borderRadius: 8, padding: "10px 14px", marginBottom: 12,
                fontSize: 11, color: "#A5B4FC", lineHeight: 1.5,
              }}>
                Used car listings from <strong>AutoScout24</strong> — EU market pricing intelligence.
              </div>
            )}

            {/* Listing count */}
            <div style={{ fontSize: 11, color: "#4B5563", marginBottom: 10 }}>
              {totalListings} listing{totalListings !== 1 ? "s" : ""}
            </div>

            {/* Listing cards */}
            {lstLoading ? (
              Array.from({ length: 6 }).map((_, i) => (
                <div key={i} style={{ background: "#111827", borderRadius: 10, height: 60, marginBottom: 8, opacity: 0.5 }} />
              ))
            ) : listings.length === 0 ? (
              <div style={{ textAlign: "center", padding: "32px 0", color: "#4B5563", fontSize: 13 }}>
                No listings for this filter.
              </div>
            ) : (
              listings.map((l) => <ListingCard key={l.id} listing={l} />)
            )}

            {/* Pagination */}
            {totalListings > PAGE && (
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 12, paddingTop: 12, borderTop: "1px solid #1F2937" }}>
                <button
                  onClick={() => setListingPage((p) => Math.max(0, p - 1))}
                  disabled={listingPage === 0}
                  style={{
                    fontSize: 12, color: listingPage === 0 ? "#374151" : "#6366f1",
                    background: "none", border: "none", cursor: listingPage === 0 ? "default" : "pointer",
                  }}
                >
                  ← Prev
                </button>
                <span style={{ fontSize: 11, color: "#4B5563" }}>
                  {listingPage * PAGE + 1}–{Math.min((listingPage + 1) * PAGE, totalListings)} of {totalListings}
                </span>
                <button
                  onClick={() => setListingPage((p) => p + 1)}
                  disabled={(listingPage + 1) * PAGE >= totalListings}
                  style={{
                    fontSize: 12,
                    color: (listingPage + 1) * PAGE >= totalListings ? "#374151" : "#6366f1",
                    background: "none", border: "none",
                    cursor: (listingPage + 1) * PAGE >= totalListings ? "default" : "pointer",
                  }}
                >
                  Next →
                </button>
              </div>
            )}
          </div>
        </div>
        )}

      </div>

      {/* ── Article Summary Modal ──────────────────────────────────────────── */}
      {articleModal && (
        <div
          onClick={(e) => { if (e.target === e.currentTarget) setArticleModal(null); }}
          style={{
            position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)",
            backdropFilter: "blur(4px)", display: "flex", alignItems: "center",
            justifyContent: "center", zIndex: 1000, padding: 24,
          }}
        >
          <div style={{
            background: "#0D1117", border: "1px solid #1F2937", borderRadius: 14,
            maxWidth: 600, width: "100%", padding: 28, position: "relative",
            animation: "fi-modal-in 220ms ease-out",
            maxHeight: "90vh", overflowY: "auto",
          }}>
            <style>{`@keyframes fi-modal-in { from { opacity:0; transform:scale(0.97) translateY(8px); } to { opacity:1; transform:scale(1) translateY(0); } }`}</style>

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
                <div style={{ fontSize: 14, fontWeight: 700, color: "#F9FAFB", lineHeight: 1.45 }}>
                  {articleModal.article.title}
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6, flexWrap: "wrap" }}>
                  {articleModal.article.publication_date && (
                    <span style={{ fontSize: 11, color: "#4B5563" }}>
                      {new Date(articleModal.article.publication_date).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })}
                    </span>
                  )}
                  <span style={{ fontSize: 11, color: "#4B5563" }}>
                    {getDomain(articleModal.article.source_url)}
                  </span>
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
            <div style={{ height: 1, background: "#1F2937", marginBottom: 18 }} />

            {/* Summary */}
            {summaryLoading && (
              <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#6B7280", fontSize: 13, padding: "12px 0" }}>
                <style>{`@keyframes fi-pulse { 0%,100%{opacity:0.3} 50%{opacity:1} }`}</style>
                {[0, 0.2, 0.4].map((delay, i) => (
                  <div key={i} style={{
                    width: 6, height: 6, borderRadius: "50%", background: "#6366f1",
                    animation: `fi-pulse 1.2s ease-in-out ${delay}s infinite`,
                  }} />
                ))}
                <span>Generating intelligence brief…</span>
              </div>
            )}
            {summaryError && (
              <div style={{ fontSize: 13, color: "#EF4444", padding: "8px 0" }}>
                Could not generate summary. Ensure GROQ_API_KEY is configured.
              </div>
            )}
            {articleSummary && !summaryLoading && (
              <div style={{
                fontSize: 14, lineHeight: 1.8, color: "#D1D5DB",
                borderLeft: "3px solid #6366f1", paddingLeft: 16,
              }}>
                {articleSummary.summary.split(/\n+/).filter(Boolean).map((para, i) => (
                  <p key={i} style={{ margin: i === 0 ? "0 0 10px" : "0", color: i === 0 ? "#A5B4FC" : "#D1D5DB" }}>
                    {renderBold(para)}
                  </p>
                ))}
              </div>
            )}

            {/* CTA */}
            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 22 }}>
              <a
                href={articleModal.article.source_url}
                target="_blank"
                rel="noreferrer"
                style={{
                  display: "flex", alignItems: "center", gap: 8,
                  background: "#6366f1", color: "#fff", border: "none", borderRadius: 8,
                  padding: "10px 18px", fontSize: 13, fontWeight: 600,
                  cursor: "pointer", textDecoration: "none",
                  transition: "background 150ms ease",
                }}
                onMouseEnter={e => { (e.currentTarget as HTMLAnchorElement).style.background = "#4F46E5"; }}
                onMouseLeave={e => { (e.currentTarget as HTMLAnchorElement).style.background = "#6366f1"; }}
              >
                <ExternalLink size={14} />
                Visit website
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
