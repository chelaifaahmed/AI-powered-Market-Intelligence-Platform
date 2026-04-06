// API client for the Automotive Intelligence Platform
// Connects to FastAPI at the same origin (or proxied via Vite dev server)

const BASE = import.meta.env.VITE_API_URL || "";

async function post<T>(path: string, body: unknown): Promise<T> {
  const url = BASE + path;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

async function patch<T>(path: string, body: unknown): Promise<T> {
  const url = BASE + path;
  const res = await fetch(url, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

async function del(path: string): Promise<void> {
  const url = BASE + path;
  const res = await fetch(url, { method: "DELETE" });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text || res.statusText}`);
  }
}

async function get<T>(path: string, params?: Record<string, string | number | boolean | undefined>): Promise<T> {
  const url = new URL(BASE + path, window.location.origin);
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") {
        url.searchParams.set(k, String(v));
      }
    });
  }
  const res = await fetch(url.toString());
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

// --- Types ---

export interface Brand {
  id: string;
  name: string;
  country_of_origin: string | null;
  founded_year: number | null;
  is_active: boolean;
}

export interface CarModel {
  id: string;
  name: string;
  year: number | null;
  segment: string | null;
  body_type: string | null;
  engine_type: string | null;
  trim_level: string | null;
  transmission: string | null;
  drivetrain: string | null;
  horsepower_hp: number | null;
  torque_nm: number | null;
  battery_kwh: number | null;
  range_km: number | null;
  doors: number | null;
  seats: number | null;
  msrp_eur: number | null;
}

export interface CarModelDetail extends CarModel {
  brand_id: string;
  brand_name: string;
  review_count: number;
}

export interface CarReview {
  id: string;
  source_url: string;
  rating: number | null;
  review_title: string | null;
  review_text: string;
  author: string | null;
  review_date: string | null;
  pros: string | null;
  cons: string | null;
  variant_tested: string | null;
  scraped_at: string;
  data_origin: string;
}

export interface InsuranceReview {
  id: string;
  source_url: string;
  rating: number | null;
  review_title: string | null;
  review_text: string;
  author: string | null;
  review_date: string | null;
  scraped_at: string;
  data_origin: string;
}

export interface Listing {
  id: string;
  listing_url: string;
  dealer_name: string | null;
  mileage_km: number | null;
  listed_price: number | null;
  currency: string;
  city: string | null;
  country: string | null;
  listed_at: string | null;
  fuel_type: string | null;
  transmission: string | null;
  color: string | null;
  trim_level: string | null;
  listing_year: number | null;
  scraped_at: string;
  data_origin: string;
}

export interface Article {
  id: string;
  title: string;
  author: string | null;
  publication_date: string | null;
  body_text: string | null;
  source_url: string;
  category: string | null;
  region: string | null;
  scraped_at: string;
  data_origin: string;
}

export interface ArticleCategory {
  category: string;
  count: number;
}

export interface ListingBreakdown {
  by_fuel_type: SourceBreakdownItem[];
  by_transmission: SourceBreakdownItem[];
  by_color: SourceBreakdownItem[];
  by_country: SourceBreakdownItem[];
  by_brand: SourceBreakdownItem[];
  price_ranges: {
    min: number;
    max: number;
    median: number;
    avg: number;
    under_25k: number;
    "25k_50k": number;
    "50k_100k": number;
    over_100k: number;
  };
}

export interface CompetitorPricing {
  id: string;
  price: number;
  currency: string;
  coverage_type: string | null;
  region: string | null;
  snapshot_date: string;
  scraped_at: string;
}

export interface ReputationScore {
  period_date: string;
  avg_rating: number | null;
  avg_sentiment_score: number | null;
  review_count: number;
  data_origin: string;
  computed_at: string;
}

export interface SentimentTrend {
  period_date: string;
  positive_count: number;
  neutral_count: number;
  negative_count: number;
  avg_sentiment_score: number | null;
  data_origin: string;
  computed_at: string;
}

export interface PipelineRun {
  id: string;
  task_name: string;
  started_at: string | null;
  finished_at: string | null;
  status: string;
  records_scraped: number;
  records_stored: number;
  error_message: string | null;
  created_at: string;
}

export interface PipelineStepRun {
  id: string;
  pipeline_run_id: string | null;
  step_name: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
  records_seen: number;
  records_processed: number;
  records_skipped: number;
  records_failed: number;
  records_inserted: number;
  error_count: number;
  step_metadata: Record<string, unknown> | null;
  created_at: string;
}

export interface PipelineRunDetail extends PipelineRun {
  steps: PipelineStepRun[];
}

export interface QualityEntitySummary {
  entity_type: string;
  rejection_count: number;
  top_errors: string[];
}

export interface QualityMetrics {
  total_rejections: number;
  raw_pages_unparsed: number;
  raw_pages_parse_errors: number;
  car_review_nlp_coverage_pct: number;
  insurance_review_nlp_coverage_pct: number;
  by_entity_type: QualityEntitySummary[];
}

export interface Failure {
  source: string;
  severity: string;
  category: string | null;
  message: string;
  source_url: string | null;
  entity_type: string | null;
  occurred_at: string;
}

export interface SourceHealth {
  scraper_name: string;
  total_runs: number;
  successful_runs: number;
  failed_runs: number;
  last_run_status: string | null;
  last_run_at: string | null;
  last_success_at: string | null;
  avg_pages_fetched: number | null;
  avg_response_time_ms: number | null;
  success_rate: number | null;
  consecutive_failures: number;
}

export interface PagedResponse<T> {
  total: number;
  limit: number;
  offset: number;
  items: T[];
}

export interface PipelineStatus {
  raw_pages: { total: number; unparsed: number; parse_errors: number };
  nlp_coverage: {
    car_reviews: { total: number; nlp_processed: number; coverage_pct: number };
    insurance_reviews: { total: number; nlp_processed: number; coverage_pct: number };
  };
  data_quality: { total_rejections: number };
  pipeline_steps: Record<
    string,
    {
      status: string;
      last_run_at: string | null;
      records_processed: number;
      records_failed: number;
      duration_ms: number | null;
    }
  >;
}

export interface SourceBreakdownItem {
  source: string;
  count: number;
}

export interface BrandSummary {
  id: string;
  name: string;
  country_of_origin: string | null;
  founded_year: number | null;
  review_count: number;
  avg_rating: number | null;
  avg_sentiment: number | null;
  latest_period: string | null;
}

export interface ListingSummary {
  total: number;
  avg_price: number | null;
  avg_mileage: number | null;
  countries: number;
  by_country: SourceBreakdownItem[];
}

export interface PricingSummary {
  total: number;
  avg_price: number | null;
  by_coverage: SourceBreakdownItem[];
  by_region: SourceBreakdownItem[];
}

export interface ProvenanceSummary {
  car_reviews: Record<string, number>;
  insurance_reviews: Record<string, number>;
  car_listings: Record<string, number>;
  market_articles: Record<string, number>;
  competitor_pricings: Record<string, number>;
  nlp_models: Record<string, number>;
}

export interface DashboardSummary {
  total_car_reviews: number;
  total_insurance_reviews: number;
  total_listings: number;
  total_articles: number;
  total_competitors: number;
  total_brands: number;
  review_sources: SourceBreakdownItem[];
  pipeline_status: PipelineStatus;
  source_health: SourceHealth[];
  recent_failures: Failure[];
  provenance?: { real_articles: number; real_listings: number; real_reviews: number };
}

export interface SectorContext {
  sector: "insurance" | "automotive";
  sector_avg_score: number;
  sector_avg_negative_pct: number;
  performance_vs_sector: "above" | "average" | "below";
  percentile: number;
}

export interface OpportunitySignal {
  entity_name: string;
  entity_type: string;
  entity_id: string;
  region: string | null;
  overall_score: number;
  complaint_score: number;
  sentiment_drop_score: number;
  review_volume_score: number;
  signal_strength: "strong" | "moderate" | "weak";
  top_complaint_types: string[] | null;
  score_reasoning: {
    complaint: { score: number; reason: string };
    sentiment_trend: { score: number; reason: string };
    review_volume: { score: number; reason: string };
    sector_context?: SectorContext;
  };
  sector_percentile: number | null;
  sector_avg_score: number | null;
  computed_at: string;
}

export interface ClusterOut {
  cluster_id: number;
  cluster_label: string;
  erp_module: string;
  description: string | null;
  color_hex: string;
  company_count: number;
  avg_negative_pct: number | null;
  avg_review_count: number | null;
}

export interface ClusteredCompanyOut {
  company_id: string;
  company_name: string;
  sector: string;
  region: string | null;
  cluster_id: number;
  cluster_label: string;
  erp_module: string;
  color_hex: string | null;
}

export interface OpportunitySummaryTop {
  entity_name: string;
  entity_type: string;
  overall_score: number;
  region: string | null;
  top_complaint: string | null;
}

export interface OpportunitySummary {
  strong_signals: number;
  moderate_signals: number;
  weak_signals: number;
  top_opportunity: OpportunitySummaryTop | null;
  by_region: Record<string, number>;
}

export interface AnalystMessage {
  role: "user" | "assistant";
  content: string;
}

export interface AnalystChatResponse {
  reply: string;
  context_used: string[];
}

export interface SummarizeResponse {
  summary: string;
  generated_at: string;
}

export interface Source {
  id: string;
  name: string;
  base_url: string;
  source_type: string | null;
  reliability_score: number;
  is_active: boolean;
  region: string | null;
  keywords: string[] | null;
  last_scraped_at: string | null;
  total_records_scraped: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface SourceCreatePayload {
  name: string;
  base_url: string;
  source_type?: string;
  reliability_score?: number;
  is_active?: boolean;
  region?: string;
  keywords?: string[];
}

export interface SourcePatchPayload {
  name?: string;
  base_url?: string;
  source_type?: string;
  reliability_score?: number;
  is_active?: boolean;
  region?: string;
  keywords?: string[];
}

export type ScraperType = "reviews" | "listings" | "articles" | "all";

export interface TriggerResponse {
  run_id: string;
  status: string;
  scraper: string;
}

export interface PipelineRunStatus {
  run_id: string;
  status: string;
  scraper: string;
  records_scraped: number;
  records_stored: number;
  started_at: string | null;
  finished_at: string | null;
  duration_seconds: number | null;
  error_message: string | null;
}

export interface SearchKeyword {
  id: string;
  keyword: string;
  region: string | null;
  is_active: boolean;
  last_searched_at: string | null;
  results_count: number;
  created_at: string | null;
}

export interface InsuranceCompanyOut {
  id: string;
  name: string;
  country: string | null;
  website: string | null;
  founded_year: number | null;
  region: string | null;
  is_active: boolean;
  cluster_label: string | null;
  erp_module: string | null;
  review_count: number;
  avg_rating: number | null;
  negative_pct: number | null;
}

export interface InsuranceSentimentOut {
  company_id: string;
  company_name: string;
  total_reviews: number;
  positive: number;
  neutral: number;
  negative: number;
  avg_rating: number | null;
  top_topics: string[];
}

export interface InsuranceLandscape {
  total_companies: number;
  total_reviews: number;
  avg_rating: number | null;
  overall_negative_pct: number;
  companies: InsuranceCompanyOut[];
  sentiment_breakdown: InsuranceSentimentOut[];
}

export interface MlMetricsOut {
  model_name: string;
  silhouette_score: number | null;
  davies_bouldin_score: number | null;
  inertia: number | null;
  k_value: number;
  n_companies: number;
  quality_grade: string;
  cluster_stability_json: Record<string, number> | null;
  created_at: string;
}

export interface KeywordSearchResult {
  articles_found: number;
  articles_inserted: number;
  articles_duplicate: number;
  keywords_searched: number;
}

// --- API functions ---

export const api = {
  brands: () => get<Brand[]>("/api/brands"),
  brandModels: (id: string) => get<CarModel[]>(`/api/brands/${id}/models`),
  brandReputation: (id: string, origin?: string) =>
    get<ReputationScore[]>(`/api/brands/${id}/reputation`, { origin }),
  brandSentiment: (id: string, origin?: string) =>
    get<SentimentTrend[]>(`/api/brands/${id}/sentiment`, { origin }),

  carReviews: (p?: { limit?: number; offset?: number; brand?: string; origin?: string }) =>
    get<PagedResponse<CarReview>>("/api/reviews/car", p),
  insuranceReviews: (p?: { limit?: number; offset?: number }) =>
    get<PagedResponse<InsuranceReview>>("/api/reviews/insurance", p),

  listings: (p?: { limit?: number; offset?: number; brand?: string; origin?: string }) =>
    get<PagedResponse<Listing>>("/api/listings", p),

  articles: (p?: { limit?: number; offset?: number; category?: string; region?: string; origin?: string }) =>
    get<PagedResponse<Article>>("/api/articles", p),
  articleCategories: () => get<ArticleCategory[]>("/api/articles/categories"),

  models: (p?: { limit?: number; offset?: number; brand?: string; engine_type?: string; segment?: string; ev_only?: boolean }) =>
    get<PagedResponse<CarModelDetail>>("/api/models", p),

  competitors: (p?: { limit?: number; offset?: number; coverage_type?: string; region?: string }) =>
    get<PagedResponse<CompetitorPricing>>("/api/competitors", p),

  listingsBreakdown: () => get<ListingBreakdown>("/api/listings/breakdown"),

  pipelineRuns: (limit?: number) => get<PipelineRun[]>("/api/pipeline/runs", { limit }),
  pipelineRunDetail: (id: string) => get<PipelineRunDetail>(`/api/pipeline/runs/${id}`),
  pipelineStatus: () => get<PipelineStatus>("/api/pipeline/status"),
  pipelineQuality: () => get<QualityMetrics>("/api/pipeline/quality"),
  pipelineFailures: (p?: { limit?: number; offset?: number; source?: string }) =>
    get<PagedResponse<Failure>>("/api/pipeline/failures", p),

  sourcesHealth: () => get<SourceHealth[]>("/api/sources/health"),
  dashboardSummary: () => get<DashboardSummary>("/api/dashboard/summary"),
  dataProvenance: () => get<ProvenanceSummary>("/api/data/provenance"),
  brandsSummary: (origin?: string) => get<BrandSummary[]>("/api/brands/summary", { origin }),
  listingsSummary: () => get<ListingSummary>("/api/listings/summary"),
  competitorsSummary: () => get<PricingSummary>("/api/competitors/summary"),

  opportunities: (p?: { region?: string; entity_type?: string; min_score?: number }) =>
    get<OpportunitySignal[]>("/api/opportunities", p),
  opportunitySummary: () => get<OpportunitySummary>("/api/opportunities/summary"),

  insuranceLandscape: () => get<InsuranceLandscape>("/api/insurance/landscape"),

  mlClusters: () => get<ClusterOut[]>("/api/ml/clusters"),
  mlCompanies: () => get<ClusteredCompanyOut[]>("/api/ml/companies"),
  mlMetrics: () => get<MlMetricsOut>("/api/ml/metrics"),

  analystChat: (messages: AnalystMessage[]) =>
    post<AnalystChatResponse>("/api/analyst/chat", { messages }),

  analystSummarize: (type: string, context?: string) =>
    post<SummarizeResponse>("/api/analyst/summarize", { type, context: context ?? "" }),

  sources: () => get<Source[]>("/api/sources"),
  createSource: (payload: SourceCreatePayload) => post<Source>("/api/sources", payload),
  updateSource: (id: string, payload: SourcePatchPayload) => patch<Source>(`/api/sources/${id}`, payload),
  deleteSource: (id: string) => del(`/api/sources/${id}`),

  triggerPipeline: (scraper: ScraperType) =>
    post<TriggerResponse>("/api/pipeline/trigger", { scraper }),
  pipelineRunStatus: (runId: string) =>
    get<PipelineRunStatus>(`/api/pipeline/status/${runId}`),

  keywords: () => get<SearchKeyword[]>("/api/keywords"),
  createKeyword: (keyword: string, region?: string) =>
    post<SearchKeyword>("/api/keywords", { keyword, region }),
  deleteKeyword: (id: string) => del(`/api/keywords/${id}`),
  keywordSearchNow: () => post<KeywordSearchResult>("/api/keywords/search-now", {}),
};
