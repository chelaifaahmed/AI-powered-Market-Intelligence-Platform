"""
api/main.py
-----------
FastAPI application for the Automotive Market Intelligence Platform.

Endpoints
---------
GET /                             — welcome + link to docs
GET /health                       — database connectivity check

GET /api/brands                   — list all car brands
GET /api/brands/{id}/models       — models for a brand
GET /api/brands/{id}/reputation   — monthly reputation scores (analytics)
GET /api/brands/{id}/sentiment    — monthly sentiment trends (analytics)

GET /api/reviews/car              — paginated car reviews (newest first)
GET /api/reviews/insurance        — paginated insurance reviews (newest first)

GET /api/listings                 — paginated marketplace car listings
GET /api/articles                 — paginated market-trend articles
GET /api/competitors              — competitor pricing snapshots

GET /api/pipeline/runs            — recent pipeline run audit log

Usage
-----
    # From project root:
    python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import re
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Ensure project root is importable
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

from sqlalchemy import func, text, or_

from database.connection import get_db_session, health_check
from database.models import (
    BrandReputationScore,
    CarBrand,
    CarListing,
    CarModel,
    CarReview,
    CarReviewNlp,
    CompetitorPricing,
    DataQualityLog,
    InsuranceCompany,
    InsuranceReview,
    InsuranceReviewNlp,
    MarketTrendArticle,
    PipelineRun,
    PipelineStepRun,
    RawPage,
    ScraperHealthMetric,
    ScrapingError,
    ScrapingRun,
    ScrapingTask,
    SentimentTrend,
    OpportunitySignal,
    ReviewSource,
    SearchKeyword,
    MlClusterMetadata,
    MlModelMetric,
)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

from contextlib import asynccontextmanager

@asynccontextmanager
async def _lifespan(_):
    """
    Warm up the RAG models at startup so the first request is instant.
    Both models are ~500 MB total; loading takes ~20 s on first run,
    then they stay in memory for the lifetime of the process.
    """
    import threading

    def _preload():
        try:
            _get_rag_embedder()
            _get_cross_encoder()
            print("[RAG] Models preloaded and ready.")
        except Exception as exc:
            print(f"[RAG] Preload warning (non-fatal): {exc}")

    # Set NO_RAG_PRELOAD=1 to skip model loading (useful when torch DLL crashes on startup)
    if not os.environ.get("NO_RAG_PRELOAD"):
        threading.Thread(target=_preload, daemon=True).start()
    else:
        print("[RAG] Preload skipped (NO_RAG_PRELOAD=1). Models will load on first use.")
    yield


app = FastAPI(
    title="Automotive Market Intelligence API",
    description=(
        "REST API exposing scraped and enriched data from the "
        "Automotive Market Intelligence Platform. Browse brands, reviews, "
        "car listings, insurance data, and analytics."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

from api.auth import router as auth_router
app.include_router(auth_router, prefix="/api")

# ---------------------------------------------------------------------------
# Dashboard static files (Phase 11)
# Mount the Vite build output so the SPA is served at /ui/
# ---------------------------------------------------------------------------
_DASHBOARD_DIST = os.path.join(_PROJECT_ROOT, "dashboard", "dist")
if os.path.isdir(_DASHBOARD_DIST):
    app.mount("/ui", StaticFiles(directory=_DASHBOARD_DIST, html=True), name="ui")


# ---------------------------------------------------------------------------
# Response schemas (Pydantic v2)
# ---------------------------------------------------------------------------

class BrandOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    country_of_origin: Optional[str]
    founded_year: Optional[int]
    is_active: bool


class CarModelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    year: Optional[int]
    segment: Optional[str]
    body_type: Optional[str]
    engine_type: Optional[str]
    trim_level: Optional[str]
    transmission: Optional[str]
    drivetrain: Optional[str]
    horsepower_hp: Optional[int]
    torque_nm: Optional[int]
    battery_kwh: Optional[float]
    range_km: Optional[int]
    doors: Optional[int]
    seats: Optional[int]
    msrp_eur: Optional[float]


class CarReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    source_url: str
    rating: Optional[float]
    review_title: Optional[str]
    review_text: str
    author: Optional[str]
    review_date: Optional[date]
    pros: Optional[str]
    cons: Optional[str]
    variant_tested: Optional[str]
    scraped_at: datetime
    data_origin: str = "reference"


class InsuranceReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    source_url: str
    rating: Optional[float]
    review_title: Optional[str]
    review_text: str
    author: Optional[str]
    review_date: Optional[date]
    scraped_at: datetime
    data_origin: str = "reference"


class ListingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    listing_url: str
    dealer_name: Optional[str]
    mileage_km: Optional[int]
    listed_price: Optional[float]
    currency: str
    city: Optional[str]
    country: Optional[str]
    listed_at: Optional[date]
    fuel_type: Optional[str]
    transmission: Optional[str]
    color: Optional[str]
    trim_level: Optional[str]
    listing_year: Optional[int]
    scraped_at: datetime
    data_origin: str = "reference"
    brand_name: Optional[str] = None
    model_name: Optional[str] = None


_CATEGORY_LABELS: dict[str, str] = {
    "forum": "Forums & Reddit",
    "erp": "ERP & Enterprise",
    "startup": "Startups & VC",
    "finance": "Finance & Fintech",
    "consulting": "Consulting",
    "data": "Data & AI",
    "management": "Management",
    "automotive": "Automotive",
    "insurance": "Insurance",
    "market": "Market Intelligence",
    "tunisia": "Tunisia",
}


class ArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    title: str
    author: Optional[str] = None
    publication_date: Optional[date] = None
    body_text: Optional[str] = None
    source_url: str
    category: Optional[str] = None
    region: Optional[str] = None
    scraped_at: datetime
    data_origin: str = "reference"
    tags: List[str] = Field(default_factory=list)
    # computed
    days_ago: Optional[int] = None
    is_new: bool = False
    category_label: str = "General"
    forum_subcategory: Optional[str] = None

    @field_validator("tags", mode="before")
    @classmethod
    def _coerce_tags(cls, v: object) -> List[str]:
        if v is None:
            return []
        return list(v)

    @model_validator(mode="after")
    def _compute_derived(self) -> "ArticleOut":
        if self.publication_date:
            self.days_ago = (date.today() - self.publication_date).days
            self.is_new = self.days_ago <= 30
        self.category_label = _CATEGORY_LABELS.get((self.category or "").lower(), "General")
        if (self.category or "").lower() == "forum" and self.tags:
            self.forum_subcategory = self.tags[0]
        return self


class CompetitorPricingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    price: float
    currency: str
    coverage_type: Optional[str]
    region: Optional[str]
    snapshot_date: date
    scraped_at: datetime
    data_origin: str = "reference"


class ReputationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    period_date: date
    avg_rating: Optional[float]
    avg_sentiment_score: Optional[float]
    review_count: int
    data_origin: str = "all"
    computed_at: datetime


class SentimentTrendOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    period_date: date
    positive_count: int
    neutral_count: int
    negative_count: int
    avg_sentiment_score: Optional[float]
    data_origin: str = "all"
    computed_at: datetime


class PipelineRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    task_name: str
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    status: str
    records_scraped: int
    records_stored: int
    error_message: Optional[str]
    created_at: datetime


class PagedResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[Any]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


@app.get("/health", tags=["system"], summary="Database health check")
def health():
    ok = health_check()
    if not ok:
        raise HTTPException(status_code=503, detail="Database unreachable")
    return {"status": "healthy", "database": "connected"}


# ---- Brands ---------------------------------------------------------------

@app.get("/api/brands", response_model=List[BrandOut], tags=["brands"])
def list_brands(active_only: bool = Query(False, description="Return only active brands")):
    """List all car brands."""
    with get_db_session() as session:
        q = session.query(CarBrand)
        if active_only:
            q = q.filter(CarBrand.is_active.is_(True))
        return [BrandOut.model_validate(b) for b in q.order_by(CarBrand.name).all()]


@app.get("/api/brands/{brand_id}/models", response_model=List[CarModelOut], tags=["brands"])
def list_brand_models(brand_id: UUID):
    """List all car models for a specific brand."""
    with get_db_session() as session:
        brand = session.get(CarBrand, brand_id)
        if not brand:
            raise HTTPException(status_code=404, detail="Brand not found")
        models = (
            session.query(CarModel)
            .filter(CarModel.brand_id == brand_id)
            .order_by(CarModel.name, CarModel.year)
            .all()
        )
        return [CarModelOut.model_validate(m) for m in models]


@app.get("/api/brands/{brand_id}/reputation", response_model=List[ReputationOut], tags=["analytics"])
def brand_reputation(
    brand_id: UUID,
    origin: Optional[str] = Query("scraped", description="Provenance filter: all | reference | scraped"),
):
    """Monthly brand reputation scores filtered by data origin. Defaults to scraped (live) only."""
    with get_db_session() as session:
        brand = session.get(CarBrand, brand_id)
        if not brand:
            raise HTTPException(status_code=404, detail="Brand not found")
        q = (
            session.query(BrandReputationScore)
            .filter(BrandReputationScore.brand_id == brand_id)
        )
        if origin:
            q = q.filter(BrandReputationScore.data_origin == origin)
        rows = q.order_by(BrandReputationScore.period_date.desc()).all()
        return [ReputationOut.model_validate(r) for r in rows]


@app.get("/api/brands/{brand_id}/sentiment", response_model=List[SentimentTrendOut], tags=["analytics"])
def brand_sentiment(
    brand_id: UUID,
    origin: Optional[str] = Query("scraped", description="Provenance filter: all | reference | scraped"),
):
    """Monthly sentiment trend filtered by data origin. Defaults to scraped (live) only."""
    with get_db_session() as session:
        brand = session.get(CarBrand, brand_id)
        if not brand:
            raise HTTPException(status_code=404, detail="Brand not found")
        q = (
            session.query(SentimentTrend)
            .filter(SentimentTrend.brand_id == brand_id)
        )
        if origin:
            q = q.filter(SentimentTrend.data_origin == origin)
        rows = q.order_by(SentimentTrend.period_date.desc()).all()
        return [SentimentTrendOut.model_validate(r) for r in rows]


# ---- Reviews --------------------------------------------------------------

@app.get("/api/reviews/car", response_model=PagedResponse, tags=["reviews"])
def list_car_reviews(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    brand: Optional[str] = Query(None, description="Filter by brand name (case-insensitive)"),
    origin: Optional[str] = Query(None, description="Filter by provenance: reference | scraped | imported"),
):
    """Paginated car reviews, newest first."""
    with get_db_session() as session:
        q = session.query(CarReview)
        if brand:
            q = (
                q.join(CarModel, CarReview.model_id == CarModel.id)
                 .join(CarBrand, CarModel.brand_id == CarBrand.id)
                 .filter(CarBrand.name.ilike(f"%{brand}%"))
            )
        if origin:
            q = q.filter(CarReview.data_origin == origin)
        total = q.count()
        rows = q.order_by(CarReview.scraped_at.desc()).offset(offset).limit(limit).all()
        return PagedResponse(
            total=total,
            limit=limit,
            offset=offset,
            items=[CarReviewOut.model_validate(r) for r in rows],
        )


@app.get("/api/reviews/insurance", response_model=PagedResponse, tags=["reviews"])
def list_insurance_reviews(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Paginated insurance reviews, newest first."""
    with get_db_session() as session:
        total = session.query(InsuranceReview).count()
        rows = (
            session.query(InsuranceReview)
            .order_by(InsuranceReview.scraped_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return PagedResponse(
            total=total,
            limit=limit,
            offset=offset,
            items=[InsuranceReviewOut.model_validate(r) for r in rows],
        )


# ---- Insurance Companies --------------------------------------------------

class InsuranceCompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    country: Optional[str]
    website: Optional[str]
    founded_year: Optional[int]
    region: Optional[str]
    is_active: bool
    cluster_label: Optional[str]
    erp_module: Optional[str]
    review_count: int = 0
    avg_rating: Optional[float] = None
    negative_pct: Optional[float] = None


class InsuranceSentimentOut(BaseModel):
    company_id: UUID
    company_name: str
    total_reviews: int
    positive: int
    neutral: int
    negative: int
    avg_rating: Optional[float]
    top_topics: List[str]


class InsuranceLandscapeOut(BaseModel):
    total_companies: int
    total_reviews: int
    avg_rating: Optional[float]
    overall_negative_pct: float
    companies: List[InsuranceCompanyOut]
    sentiment_breakdown: List[InsuranceSentimentOut]


@app.get("/api/insurance/landscape", response_model=InsuranceLandscapeOut,
         tags=["insurance"], summary="Full insurance landscape dashboard data")
def insurance_landscape():
    """Aggregated insurance landscape: companies, review counts, sentiment breakdown."""
    from database.enums import SentimentLabel
    with get_db_session() as session:
        companies = (
            session.query(InsuranceCompany)
            .filter(InsuranceCompany.is_active.is_(True))
            .order_by(InsuranceCompany.name)
            .all()
        )

        company_list: List[InsuranceCompanyOut] = []
        sentiment_list: List[InsuranceSentimentOut] = []
        grand_total_reviews = 0
        all_ratings: List[float] = []
        all_negative = 0
        all_total_nlp = 0

        for c in companies:
            rev_count = (
                session.query(func.count(InsuranceReview.id))
                .filter(InsuranceReview.company_id == c.id)
                .scalar()
            ) or 0

            avg_rat = (
                session.query(func.avg(InsuranceReview.rating))
                .filter(InsuranceReview.company_id == c.id,
                        InsuranceReview.rating.isnot(None))
                .scalar()
            )

            # NLP sentiment counts
            pos = (
                session.query(func.count(InsuranceReviewNlp.id))
                .join(InsuranceReview, InsuranceReviewNlp.review_id == InsuranceReview.id)
                .filter(InsuranceReview.company_id == c.id,
                        InsuranceReviewNlp.sentiment_label == SentimentLabel.POSITIVE)
                .scalar()
            ) or 0
            neu = (
                session.query(func.count(InsuranceReviewNlp.id))
                .join(InsuranceReview, InsuranceReviewNlp.review_id == InsuranceReview.id)
                .filter(InsuranceReview.company_id == c.id,
                        InsuranceReviewNlp.sentiment_label == SentimentLabel.NEUTRAL)
                .scalar()
            ) or 0
            neg = (
                session.query(func.count(InsuranceReviewNlp.id))
                .join(InsuranceReview, InsuranceReviewNlp.review_id == InsuranceReview.id)
                .filter(InsuranceReview.company_id == c.id,
                        InsuranceReviewNlp.sentiment_label == SentimentLabel.NEGATIVE)
                .scalar()
            ) or 0

            # Top topics
            from database.models import Topic
            top_topics_rows = (
                session.query(Topic.topic_label, func.count(InsuranceReviewNlp.id).label("cnt"))
                .join(InsuranceReviewNlp, InsuranceReviewNlp.topic_id == Topic.id)
                .join(InsuranceReview, InsuranceReviewNlp.review_id == InsuranceReview.id)
                .filter(InsuranceReview.company_id == c.id)
                .group_by(Topic.topic_label)
                .order_by(func.count(InsuranceReviewNlp.id).desc())
                .limit(3)
                .all()
            )
            top_topics = [r[0] for r in top_topics_rows]

            neg_pct = round(neg / (pos + neu + neg) * 100, 1) if (pos + neu + neg) > 0 else None

            company_list.append(InsuranceCompanyOut(
                id=c.id,
                name=c.name,
                country=c.country,
                website=c.website,
                founded_year=c.founded_year,
                region=c.region,
                is_active=c.is_active,
                cluster_label=c.cluster_label,
                erp_module=c.erp_module,
                review_count=rev_count,
                avg_rating=round(float(avg_rat), 2) if avg_rat else None,
                negative_pct=neg_pct,
            ))

            if rev_count > 0:
                sentiment_list.append(InsuranceSentimentOut(
                    company_id=c.id,
                    company_name=c.name,
                    total_reviews=rev_count,
                    positive=pos,
                    neutral=neu,
                    negative=neg,
                    avg_rating=round(float(avg_rat), 2) if avg_rat else None,
                    top_topics=top_topics,
                ))

            grand_total_reviews += rev_count
            if avg_rat:
                all_ratings.append(float(avg_rat))
            all_negative += neg
            all_total_nlp += (pos + neu + neg)

        overall_avg = round(sum(all_ratings) / len(all_ratings), 2) if all_ratings else None
        overall_neg_pct = round(all_negative / all_total_nlp * 100, 1) if all_total_nlp > 0 else 0.0

        # Sort companies by review count desc
        company_list.sort(key=lambda x: -x.review_count)
        sentiment_list.sort(key=lambda x: -x.total_reviews)

        return InsuranceLandscapeOut(
            total_companies=len(companies),
            total_reviews=grand_total_reviews,
            avg_rating=overall_avg,
            overall_negative_pct=overall_neg_pct,
            companies=company_list,
            sentiment_breakdown=sentiment_list,
        )


# ---- Listings -------------------------------------------------------------

@app.get("/api/listings", response_model=PagedResponse, tags=["listings"])
def list_car_listings(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    brand: Optional[str] = Query(None, description="Filter by brand name (case-insensitive)"),
    origin: Optional[str] = Query(None, description="Filter by provenance: reference | scraped | imported"),
    currency: Optional[str] = Query(None, description="Filter by currency: EUR | TND"),
    search: Optional[str] = Query(None, description="Search by brand or model name (case-insensitive)"),
    sort: Optional[str] = Query(None, description="Sort order: price_asc | price_desc | newest"),
):
    """Paginated car marketplace listings."""
    with get_db_session() as session:
        q = (
            session.query(CarListing, CarModel.name.label("model_name"), CarBrand.name.label("brand_name"))
            .outerjoin(CarModel, CarListing.model_id == CarModel.id)
            .outerjoin(CarBrand, CarModel.brand_id == CarBrand.id)
        )
        if brand:
            q = q.filter(CarBrand.name.ilike(f"%{brand}%"))
        if search:
            pattern = f"%{search}%"
            q = q.filter(
                CarBrand.name.ilike(pattern) | CarModel.name.ilike(pattern)
            )
        if origin:
            q = q.filter(CarListing.data_origin == origin)
        if currency:
            q = q.filter(CarListing.currency == currency.upper())
        total = q.count()
        if sort == "price_asc":
            order = CarListing.listed_price.asc().nullslast()
        elif sort == "price_desc":
            order = CarListing.listed_price.desc().nullsfirst()
        else:
            order = CarListing.scraped_at.desc()
        rows = q.order_by(order).offset(offset).limit(limit).all()

        items = []
        for listing, model_name, brand_name in rows:
            d = ListingOut.model_validate(listing).model_dump()
            d["brand_name"] = brand_name
            d["model_name"] = model_name
            items.append(d)

        return PagedResponse(
            total=total,
            limit=limit,
            offset=offset,
            items=items,
        )


# ---- Articles -------------------------------------------------------------

# Keywords that make an article relevant to TEAMWILL's sales context.
# Any article whose title contains at least one of these passes the relevance filter.
_RELEVANCE_KEYWORDS = [
    # ── Automotive / vehicles ────────────────────────────────────────────────
    "car", "cars", "auto", "vehicle", "vehicles", "voiture", "voitures", "automobile",
    "automobiles", "véhicule", "véhicules", "automotive", "dealer", "dealership",
    "concessionnaire", "fleet", "flotte", "leasing", "lease",
    "carburant", "essence", "diesel", "petrol", "fuel",
    "motor", "moteur", "engine", "gearbox", "transmission", "turbo",
    "recall", "rappel constructeur", "defect", "défaut", "breakdown", "panne",
    "pièces", "spare parts", "réparation", "repair", "entretien", "maintenance",
    "driving", "conduite", "road", "route", "pothole", "nid de poule",
    "traffic", "trafic", "accident", "collision", "crash",
    # Car brands
    "Tesla", "BMW", "Toyota", "Renault", "Peugeot", "Volkswagen", "VW",
    "Hyundai", "Kia", "Stellantis", "Ford", "Mercedes", "Citroën", "Fiat",
    "Dacia", "Chery", "MG", "BYD", "Changan", "Geely", "Skoda", "Seat",
    "Audi", "Volvo", "Porsche", "Honda", "Nissan", "Mitsubishi", "Suzuki",
    "Opel", "Alfa Romeo", "Jeep", "Land Rover", "Range Rover",
    # EV / green mobility
    "electric vehicle", "EV", "hybrid", "hybride", "plug-in", "battery",
    "charging", "recharge", "borne de recharge", "zero emission",
    # Tunisian auto industry specifics
    "tunisie auto", "marché automobile tunisien", "industrie automobile tunisie",
    "STAFIM", "ENNAKL", "SATA", "AUTO HALL", "concessionnaire tunisien",
    # ── Insurance ────────────────────────────────────────────────────────────
    "insurance", "assurance", "insurer", "assureur", "premium", "prime",
    "claim", "sinistre", "coverage", "couverture", "policy", "police",
    "underwriting", "reinsurance", "réassurance", "indemnité", "liability",
    "responsabilité", "motor insurance", "auto insurance", "assurance auto",
    "assurance automobile", "P/C", "property casualty", "risk", "risque",
    "indemnification", "actuary", "actuaire", "loss ratio", "combined ratio",
    "insured", "assuré", "broker", "courtier", "agent d'assurance",
    # Customer experience / satisfaction
    "customer satisfaction", "satisfaction client", "insatisfaction",
    "complaint", "réclamation", "customer service", "service client",
    "review", "avis client", "rating", "note client", "NPS",
    "customer experience", "expérience client", "retention", "fidélisation",
    # ── Economy / Finance ────────────────────────────────────────────────────
    "economy", "économie", "economic", "économique", "finance", "financial",
    "financier", "market", "marché", "inflation", "price", "prix",
    "cost", "coût", "tariff", "tarif", "trade", "commerce", "export", "import",
    "growth", "croissance", "recession", "récession", "crisis", "crise",
    "GDP", "PIB", "investment", "investissement", "interest rate", "taux",
    "budget", "tax", "impôt", "fiscal", "bank", "banque", "credit", "crédit",
    "loan", "prêt", "stock", "bourse", "currency", "devise", "dollar", "euro",
    "dinar", "purchasing power", "pouvoir d'achat", "supply chain",
    "cost of living", "coût de la vie",
    # ── Energy / Commodities ────────────────────────────────────────────────
    "oil", "pétrole", "gas", "gaz", "energy", "énergie", "crude", "OPEC",
    "pipeline", "commodity", "matière première", "fuel price", "prix du carburant",
    "prix de l'essence", "prix du pétrole",
    # ── ERP / Information Systems / Management ───────────────────────────────
    "ERP", "odoo", "oddo", "alfa", "miles", "SAP", "oracle", "dynamics",
    "logiciel de gestion", "management system", "système d'information",
    "information system", "enterprise resource", "progiciel",
    "gestion de", "digital transformation", "transformation digitale",
    "software", "logiciel", "digital", "technology", "technologie",
    "AI", "IA", "intelligence artificielle", "artificial intelligence",
    "innovation", "data", "analytics", "plateforme", "platform",
    "automation", "automatisation", "workflow", "process", "processus",
    "operational efficiency", "efficacité opérationnelle",
    "information management", "gestion de l'information",
    # Managerial / operational problems
    "management problem", "operational problem", "inefficiency", "bottleneck",
    "legacy system", "système obsolète", "digital gap", "retard numérique",
    "expert opinion", "industry report", "étude de marché", "rapport sectoriel",
    "analyst", "analyste", "forecast", "prévision", "outlook", "perspective",
    # ── Tunisian economy / industry ──────────────────────────────────────────
    "tunisie", "tunisien", "tunisian", "économie tunisienne", "industrie tunisienne",
    "banque centrale tunisie", "BCT", "BIAT", "STB", "Attijari",
    "zone franche", "investissement étranger", "IDE",
    # ── Manufacturing / Industry ────────────────────────────────────────────
    "manufacturing", "industrie", "production", "factory", "usine",
    "supply", "shortage", "pénurie", "component", "composant",
]


@app.get("/api/articles", response_model=PagedResponse, tags=["articles"])
def list_articles(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    category: Optional[str] = Query(None, description="Single category filter (case-insensitive)"),
    categories: Optional[str] = Query(None, description="Comma-separated list of categories, e.g. Automotive,EV,Market"),
    region: Optional[str] = Query(None, description="Region filter: TN | EU (also matches Europe) | Global"),
    search: Optional[str] = Query(None, description="Keyword search in article title (case-insensitive)"),
    origin: Optional[str] = Query(None, description="Filter by provenance: reference | scraped | imported"),
    relevant_only: bool = Query(False, description="When true, restrict to articles with automotive/insurance/economy keywords in title"),
    sort: Optional[str] = Query("recent", description="Sort order: 'recent' (publication_date DESC) or 'category'"),
):
    """Paginated market-trend articles, newest first. Filterable by category, region, origin, and keyword search."""
    from sqlalchemy import or_
    with get_db_session() as session:
        q = session.query(MarketTrendArticle)
        # Single category (backward-compat)
        if category:
            q = q.filter(MarketTrendArticle.category.ilike(category))
        # Multi-category: comma-separated list
        if categories:
            cats = [c.strip() for c in categories.split(",") if c.strip()]
            if cats:
                q = q.filter(or_(*[MarketTrendArticle.category.ilike(c) for c in cats]))
        # Region: EU also matches "Europe"; TN matches "TN" or "Tunisia"
        if region:
            r = region.strip().upper()
            if r == "EU":
                q = q.filter(or_(
                    MarketTrendArticle.region.ilike("EU"),
                    MarketTrendArticle.region.ilike("Europe"),
                ))
            elif r == "TN":
                q = q.filter(or_(
                    MarketTrendArticle.region.ilike("TN"),
                    MarketTrendArticle.region.ilike("Tunisia"),
                ))
            else:
                q = q.filter(MarketTrendArticle.region.ilike(f"%{region}%"))
        # Keyword search in title
        if search:
            q = q.filter(MarketTrendArticle.title.ilike(f"%{search}%"))
        if origin:
            q = q.filter(MarketTrendArticle.data_origin == origin)
        # Relevance filter: title must mention at least one automotive/insurance/economy keyword
        if relevant_only:
            q = q.filter(or_(*[MarketTrendArticle.title.ilike(f"%{kw}%") for kw in _RELEVANCE_KEYWORDS]))
        total = q.count()
        if sort == "category":
            rows = q.order_by(
                MarketTrendArticle.category.asc().nullslast(),
                MarketTrendArticle.publication_date.desc().nullslast(),
            ).offset(offset).limit(limit).all()
        else:
            rows = q.order_by(
                MarketTrendArticle.publication_date.desc().nullslast(),
                MarketTrendArticle.scraped_at.desc(),
            ).offset(offset).limit(limit).all()
        return PagedResponse(
            total=total,
            limit=limit,
            offset=offset,
            items=[ArticleOut.model_validate(r) for r in rows],
        )


# ---- Competitor pricing ---------------------------------------------------

@app.get("/api/competitors", response_model=PagedResponse, tags=["insurance"])
def list_competitor_pricings(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    coverage_type: Optional[str] = Query(None, description="Filter by coverage type, e.g. comprehensive"),
    region: Optional[str] = Query(None, description="Filter by region, e.g. TN"),
):
    """Paginated competitor insurance pricing snapshots, newest first. Filterable by coverage type and region."""
    with get_db_session() as session:
        q = session.query(CompetitorPricing)
        if coverage_type:
            q = q.filter(CompetitorPricing.coverage_type.ilike(coverage_type))
        if region:
            q = q.filter(CompetitorPricing.region.ilike(f"%{region}%"))
        total = q.count()
        rows = (
            q.order_by(CompetitorPricing.snapshot_date.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return PagedResponse(
            total=total,
            limit=limit,
            offset=offset,
            items=[CompetitorPricingOut.model_validate(r) for r in rows],
        )


# ---- Pipeline runs --------------------------------------------------------

@app.get("/api/pipeline/runs", response_model=List[PipelineRunOut], tags=["pipeline"])
def list_pipeline_runs(limit: int = Query(20, ge=1, le=200)):
    """Recent pipeline run audit records, newest first.

    Merges both pipeline_runs (orchestration-level) and scraping_runs
    (task-level) so the Operations page always shows real run history.
    """
    with get_db_session() as session:
        # 1. Native pipeline_runs
        pipeline_rows = (
            session.query(PipelineRun)
            .order_by(PipelineRun.created_at.desc())
            .limit(limit)
            .all()
        )
        results = [PipelineRunOut.model_validate(r) for r in pipeline_rows]

        # 2. Scraping runs → mapped to same schema
        scraping_rows = (
            session.query(ScrapingRun)
            .join(ScrapingTask, ScrapingRun.task_id == ScrapingTask.id)
            .order_by(ScrapingRun.created_at.desc())
            .limit(limit)
            .all()
        )
        for sr in scraping_rows:
            results.append(PipelineRunOut(
                id=sr.id,
                task_name=sr.task.task_name if sr.task else f"scraping-{str(sr.task_id)[:8]}",
                started_at=sr.started_at,
                finished_at=sr.finished_at,
                status=sr.status.value if hasattr(sr.status, "value") else str(sr.status),
                records_scraped=sr.records_extracted,
                records_stored=sr.records_extracted - sr.records_rejected,
                error_message=sr.exit_message,
                created_at=sr.created_at,
            ))

        # Sort merged list newest-first and trim to limit
        results.sort(key=lambda r: r.created_at, reverse=True)
        return results[:limit]


# ===========================================================================
# Phase 10 — Operational Visibility
# ===========================================================================

# ---------------------------------------------------------------------------
# Additional Pydantic schemas
# ---------------------------------------------------------------------------

class PipelineStepRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    pipeline_run_id: Optional[UUID]
    step_name: str
    status: str
    started_at: datetime
    finished_at: Optional[datetime]
    duration_ms: Optional[int]
    records_seen: int
    records_processed: int
    records_skipped: int
    records_failed: int
    records_inserted: int
    error_count: int
    step_metadata: Optional[Any]
    created_at: datetime


class PipelineRunDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    task_name: str
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    status: str
    records_scraped: int
    records_stored: int
    error_message: Optional[str]
    created_at: datetime
    steps: List[PipelineStepRunOut]


class QualityEntitySummary(BaseModel):
    entity_type: str
    rejection_count: int
    top_errors: List[str]


class QualityOut(BaseModel):
    total_rejections: int
    raw_pages_unparsed: int
    raw_pages_parse_errors: int
    car_review_nlp_coverage_pct: float
    insurance_review_nlp_coverage_pct: float
    by_entity_type: List[QualityEntitySummary]


class FailureOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    source: str            # "validation" | "scraping"
    severity: str          # "error" | "warning"
    category: Optional[str]
    message: str
    source_url: Optional[str]
    entity_type: Optional[str]
    occurred_at: datetime


class SourceHealthOut(BaseModel):
    scraper_name: str
    total_runs: int
    successful_runs: int
    failed_runs: int
    last_run_status: Optional[str]
    last_run_at: Optional[datetime]
    last_success_at: Optional[datetime]
    avg_pages_fetched: Optional[float]
    avg_response_time_ms: Optional[float]
    success_rate: Optional[float]
    consecutive_failures: int


# ---------------------------------------------------------------------------
# GET /api/pipeline/status
# ---------------------------------------------------------------------------

@app.get("/api/pipeline/status", tags=["pipeline"], summary="System-wide pipeline health summary")
def pipeline_status():
    """High-level operational health: record counts, NLP coverage, latest step per stage."""
    with get_db_session() as session:
        total_raw       = session.query(RawPage).count()
        unparsed        = session.query(RawPage).filter(RawPage.is_parsed.is_(False)).count()
        parse_errors    = session.query(RawPage).filter(
            RawPage.is_parsed.is_(True), RawPage.parse_error.isnot(None)
        ).count()
        total_car       = session.query(CarReview).count()
        nlp_car         = session.query(CarReviewNlp).count()
        total_ins       = session.query(InsuranceReview).count()
        nlp_ins         = session.query(InsuranceReviewNlp).count()
        total_rejections = session.query(DataQualityLog).count()

        # Latest step run per step_name
        latest_steps_q = (
            session.query(
                PipelineStepRun.step_name,
                func.max(PipelineStepRun.created_at).label("latest"),
            )
            .group_by(PipelineStepRun.step_name)
            .all()
        )
        step_summary = {}
        for step_name, latest_ts in latest_steps_q:
            step = (
                session.query(PipelineStepRun)
                .filter(
                    PipelineStepRun.step_name == step_name,
                    PipelineStepRun.created_at == latest_ts,
                )
                .first()
            )
            if step:
                step_summary[step_name] = {
                    "status": step.status.value if step.status else None,
                    "last_run_at": step.created_at.isoformat() if step.created_at else None,
                    "records_processed": step.records_processed,
                    "records_failed": step.records_failed,
                    "duration_ms": step.duration_ms,
                }

        return {
            "raw_pages": {
                "total": total_raw,
                "unparsed": unparsed,
                "parse_errors": parse_errors,
            },
            "nlp_coverage": {
                "car_reviews": {
                    "total": total_car,
                    "nlp_processed": nlp_car,
                    "coverage_pct": round(nlp_car / total_car * 100, 1) if total_car else 0.0,
                },
                "insurance_reviews": {
                    "total": total_ins,
                    "nlp_processed": nlp_ins,
                    "coverage_pct": round(nlp_ins / total_ins * 100, 1) if total_ins else 0.0,
                },
            },
            "data_quality": {
                "total_rejections": total_rejections,
            },
            "pipeline_steps": step_summary,
        }


# ---------------------------------------------------------------------------
# GET /api/pipeline/runs/{id}
# ---------------------------------------------------------------------------

@app.get(
    "/api/pipeline/runs/{run_id}",
    response_model=PipelineRunDetailOut,
    tags=["pipeline"],
    summary="Pipeline run detail with step breakdown",
)
def get_pipeline_run(run_id: UUID):
    """Return a single PipelineRun with its associated PipelineStepRun rows."""
    with get_db_session() as session:
        run = session.get(PipelineRun, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Pipeline run not found")
        steps = (
            session.query(PipelineStepRun)
            .filter(PipelineStepRun.pipeline_run_id == run_id)
            .order_by(PipelineStepRun.started_at.asc())
            .all()
        )
        out = PipelineRunDetailOut(
            id=run.id,
            task_name=run.task_name,
            started_at=run.started_at,
            finished_at=run.finished_at,
            status=run.status.value if run.status else "unknown",
            records_scraped=run.records_scraped,
            records_stored=run.records_stored,
            error_message=run.error_message,
            created_at=run.created_at,
            steps=[PipelineStepRunOut.model_validate(s) for s in steps],
        )
        return out


# ---------------------------------------------------------------------------
# GET /api/pipeline/quality
# ---------------------------------------------------------------------------

@app.get(
    "/api/pipeline/quality",
    response_model=QualityOut,
    tags=["pipeline"],
    summary="Data quality metrics",
)
def pipeline_quality():
    """Aggregate data quality metrics: rejection counts, parse errors, NLP coverage."""
    with get_db_session() as session:
        total_rejections = session.query(DataQualityLog).count()
        unparsed         = session.query(RawPage).filter(RawPage.is_parsed.is_(False)).count()
        parse_errors     = session.query(RawPage).filter(
            RawPage.is_parsed.is_(True), RawPage.parse_error.isnot(None)
        ).count()

        total_car = session.query(CarReview).count()
        nlp_car   = session.query(CarReviewNlp).count()
        total_ins = session.query(InsuranceReview).count()
        nlp_ins   = session.query(InsuranceReviewNlp).count()

        # Rejection counts grouped by entity_type
        entity_counts = (
            session.query(
                DataQualityLog.entity_type,
                func.count(DataQualityLog.id).label("cnt"),
            )
            .group_by(DataQualityLog.entity_type)
            .order_by(func.count(DataQualityLog.id).desc())
            .all()
        )

        by_entity: List[QualityEntitySummary] = []
        for entity_type, cnt in entity_counts:
            # Fetch up to 3 distinct recent error messages for this entity type
            recent_errors = (
                session.query(DataQualityLog.validation_error)
                .filter(DataQualityLog.entity_type == entity_type)
                .order_by(DataQualityLog.rejected_at.desc())
                .limit(50)
                .all()
            )
            seen: dict = {}
            for (err,) in recent_errors:
                seen[err] = seen.get(err, 0) + 1
            top_errors = sorted(seen, key=lambda k: -seen[k])[:3]
            by_entity.append(
                QualityEntitySummary(
                    entity_type=entity_type or "unknown",
                    rejection_count=cnt,
                    top_errors=top_errors,
                )
            )

        return QualityOut(
            total_rejections=total_rejections,
            raw_pages_unparsed=unparsed,
            raw_pages_parse_errors=parse_errors,
            car_review_nlp_coverage_pct=round(nlp_car / total_car * 100, 1) if total_car else 0.0,
            insurance_review_nlp_coverage_pct=round(nlp_ins / total_ins * 100, 1) if total_ins else 0.0,
            by_entity_type=by_entity,
        )


# ---------------------------------------------------------------------------
# GET /api/pipeline/failures
# ---------------------------------------------------------------------------

@app.get(
    "/api/pipeline/failures",
    response_model=PagedResponse,
    tags=["pipeline"],
    summary="Combined failure log (validation rejections + scraping errors)",
)
def pipeline_failures(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    source: Optional[str] = Query(None, description="Filter by source: 'validation' or 'scraping'"),
):
    """
    Combined queryable failure log.

    - **validation** failures come from `data_quality_log` (parser rejection events)
    - **scraping** failures come from `scraping_errors` (HTTP / exception events)
    """
    failures: List[FailureOut] = []

    with get_db_session() as session:
        if source != "scraping":
            dql_rows = (
                session.query(DataQualityLog)
                .order_by(DataQualityLog.rejected_at.desc())
                .all()
            )
            for r in dql_rows:
                failures.append(FailureOut(
                    source="validation",
                    severity="error",
                    category="validation_rejection",
                    message=r.validation_error,
                    source_url=r.source_url,
                    entity_type=r.entity_type,
                    occurred_at=r.rejected_at,
                ))

        if source != "validation":
            err_rows = (
                session.query(ScrapingError)
                .order_by(ScrapingError.occurred_at.desc())
                .all()
            )
            for r in err_rows:
                failures.append(FailureOut(
                    source="scraping",
                    severity="error",
                    category=r.error_type,
                    message=r.error_message or "",
                    source_url=r.target_url,
                    entity_type=None,
                    occurred_at=r.occurred_at,
                ))

    # Sort combined list newest-first, then paginate in Python
    failures.sort(key=lambda f: f.occurred_at, reverse=True)
    total = len(failures)
    page = failures[offset: offset + limit]

    return PagedResponse(total=total, limit=limit, offset=offset, items=page)


# ---------------------------------------------------------------------------
# GET /api/sources/health
# ---------------------------------------------------------------------------

@app.get(
    "/api/sources/health",
    response_model=List[SourceHealthOut],
    tags=["sources"],
    summary="Per-scraper source health summary",
)
def sources_health():
    """
    Operational health per scraper source, derived from scraping_tasks,
    scraping_runs, and scraper_health_metrics.
    """
    with get_db_session() as session:
        tasks = session.query(ScrapingTask).order_by(ScrapingTask.task_name).all()
        results: List[SourceHealthOut] = []

        for task in tasks:
            runs = (
                session.query(ScrapingRun)
                .filter(ScrapingRun.task_id == task.id)
                .order_by(ScrapingRun.created_at.desc())
                .all()
            )
            total_runs     = len(runs)
            successful     = sum(1 for r in runs if r.status and r.status.value == "SUCCESS")
            failed         = sum(1 for r in runs if r.status and r.status.value == "FAILED")
            last_run       = runs[0] if runs else None
            last_success   = next(
                (r for r in runs if r.status and r.status.value == "SUCCESS"), None
            )

            # Consecutive failures from newest run backwards
            consec = 0
            for r in runs:
                if r.status and r.status.value == "FAILED":
                    consec += 1
                else:
                    break

            avg_pages = None
            if total_runs:
                fetched = [r.pages_fetched for r in runs if r.pages_fetched is not None]
                avg_pages = round(sum(fetched) / len(fetched), 1) if fetched else None

            # Latest health metric for this scraper
            health = (
                session.query(ScraperHealthMetric)
                .filter(ScraperHealthMetric.scraper_name == task.task_name)
                .order_by(ScraperHealthMetric.measured_at.desc())
                .first()
            )

            results.append(SourceHealthOut(
                scraper_name=task.task_name,
                total_runs=total_runs,
                successful_runs=successful,
                failed_runs=failed,
                last_run_status=last_run.status.value if last_run and last_run.status else None,
                last_run_at=last_run.created_at if last_run else None,
                last_success_at=last_success.finished_at if last_success else None,
                avg_pages_fetched=avg_pages,
                avg_response_time_ms=float(health.avg_response_time_ms) if health and health.avg_response_time_ms else None,
                success_rate=float(health.success_rate) if health and health.success_rate else None,
                consecutive_failures=consec,
            ))

        return results


# ===========================================================================
# Phase 11 — Dashboard aggregation endpoints
# ===========================================================================

# ---------------------------------------------------------------------------
# Additional schemas
# ---------------------------------------------------------------------------

class BrandSummaryOut(BaseModel):
    id: UUID
    name: str
    country_of_origin: Optional[str]
    founded_year: Optional[int]
    review_count: int
    avg_rating: Optional[float]
    avg_sentiment: Optional[float]
    latest_period: Optional[date]


class SourceBreakdownItem(BaseModel):
    source: str
    count: int


class ListingSummaryOut(BaseModel):
    total: int
    avg_price: Optional[float]
    avg_mileage: Optional[float]
    countries: int
    by_country: List[SourceBreakdownItem]


class PricingSummaryOut(BaseModel):
    total: int
    avg_price: Optional[float]
    by_coverage: List[SourceBreakdownItem]
    by_region: List[SourceBreakdownItem]


# ---------------------------------------------------------------------------
# GET /api/dashboard/summary
# ---------------------------------------------------------------------------

@app.get("/api/data/provenance", tags=["data"], summary="Reference vs scraped record counts per entity type")
def data_provenance():
    """
    Returns counts of records by data_origin (reference | scraped | imported)
    for the five main domain tables.  Used by the dashboard to distinguish
    demo data from real intelligence.
    """
    with get_db_session() as session:
        def _origins(model_cls, origin_col="data_origin"):
            col = getattr(model_cls, origin_col)
            rows = session.query(col, func.count()).group_by(col).all()
            return {r[0]: r[1] for r in rows}

        def _raw_origins(table: str) -> dict:
            rows = session.execute(
                text(f"SELECT data_origin, COUNT(*) FROM {table} GROUP BY data_origin")  # noqa: S608
            ).fetchall()
            return {r[0]: r[1] for r in rows}

        return {
            "car_reviews":            _origins(CarReview),
            "insurance_reviews":      _origins(InsuranceReview),
            "car_listings":           _origins(CarListing),
            "market_articles":        _origins(MarketTrendArticle),
            "competitor_pricings":    _origins(CompetitorPricing),
            "company_action_signals": _raw_origins("company_action_signals"),
            "company_tech_stack":     _raw_origins("company_tech_stack"),
            "nlp_models": {
                row[0]: row[1]
                for row in session.execute(
                    text("SELECT model_version, COUNT(*) FROM article_nlp_results GROUP BY model_version")
                ).fetchall()
            },
        }


# ---------------------------------------------------------------------------
# GET /api/region-summary — counts grouped by region
# ---------------------------------------------------------------------------

@app.get("/api/region-summary", tags=["data"], summary="Entity counts grouped by region")
def region_summary():
    """
    Returns counts of insurance companies, car brands, and market articles
    grouped by region (e.g. TN, EU, Global, None).
    """
    with get_db_session() as session:
        def _by_region(model_cls):
            rows = session.query(
                func.coalesce(model_cls.region, "unset"),
                func.count(),
            ).group_by(model_cls.region).all()
            return {r[0]: r[1] for r in rows}

        return {
            "insurance_companies": _by_region(InsuranceCompany),
            "car_brands":          _by_region(CarBrand),
            "market_articles":     _by_region(MarketTrendArticle),
        }


# ---------------------------------------------------------------------------
# Opportunity Scoring endpoints
# ---------------------------------------------------------------------------

class OpportunityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    entity_name: str
    entity_type: str
    entity_id: UUID
    region: Optional[str]
    overall_score: float
    complaint_score: float
    sentiment_drop_score: float
    review_volume_score: float
    signal_strength: str
    top_complaint_types: Optional[List[str]]
    score_reasoning: Optional[Any]
    sector_percentile: Optional[int] = None
    sector_avg_score: Optional[float] = None
    computed_at: datetime


class OpportunitySummaryTopOut(BaseModel):
    entity_name: str
    entity_type: str
    overall_score: float
    region: Optional[str]
    top_complaint: Optional[str]


class OpportunitySummaryOut(BaseModel):
    strong_signals: int
    moderate_signals: int
    weak_signals: int
    top_opportunity: Optional[OpportunitySummaryTopOut]
    by_region: dict


@app.get(
    "/api/opportunities/summary",
    response_model=OpportunitySummaryOut,
    tags=["opportunities"],
    summary="Opportunity signal summary counts",
)
def opportunities_summary():
    """Aggregate opportunity signal counts by strength and region."""
    with get_db_session() as session:
        all_signals = session.query(OpportunitySignal).all()

        strong = sum(1 for s in all_signals if s.signal_strength == "strong")
        moderate = sum(1 for s in all_signals if s.signal_strength == "moderate")
        weak = sum(1 for s in all_signals if s.signal_strength == "weak")

        # Top opportunity
        top = max(all_signals, key=lambda s: float(s.overall_score)) if all_signals else None

        # By region
        region_counts: dict = {}
        for s in all_signals:
            r = s.region or "unset"
            region_counts[r] = region_counts.get(r, 0) + 1

        return OpportunitySummaryOut(
            strong_signals=strong,
            moderate_signals=moderate,
            weak_signals=weak,
            top_opportunity=OpportunitySummaryTopOut(
                entity_name=top.entity_name,
                entity_type=top.entity_type,
                overall_score=float(top.overall_score),
                region=top.region,
                top_complaint=top.top_complaint_types[0] if top.top_complaint_types else None,
            ) if top else None,
            by_region=region_counts,
        )


@app.get(
    "/api/opportunities",
    response_model=List[OpportunityOut],
    tags=["opportunities"],
    summary="List opportunity signals sorted by score",
)
def list_opportunities(
    region: Optional[str] = Query(None, description="Filter by region code, e.g. TN"),
    entity_type: Optional[str] = Query(None, description="Filter: 'insurance' or 'brand'"),
    min_score: float = Query(0, ge=0, le=100, description="Minimum overall_score"),
):
    """Leaderboard of opportunity signals, highest score first."""
    with get_db_session() as session:
        q = session.query(OpportunitySignal).filter(
            OpportunitySignal.overall_score >= min_score
        )
        if region:
            q = q.filter(OpportunitySignal.region == region)
        if entity_type:
            q = q.filter(OpportunitySignal.entity_type == entity_type)
        rows = q.order_by(OpportunitySignal.overall_score.desc()).all()

        # Compute sector averages for enrichment
        sector_avgs: dict = {}
        for etype in ("insurance", "brand"):
            sector_rows = session.query(OpportunitySignal.overall_score).filter(
                OpportunitySignal.entity_type == etype
            ).all()
            if sector_rows:
                sector_avgs[etype] = round(sum(float(r[0]) for r in sector_rows) / len(sector_rows), 1)

        results = []
        for r in rows:
            out = OpportunityOut.model_validate(r)
            out.sector_avg_score = sector_avgs.get(r.entity_type)
            results.append(out)
        return results


class V2OpportunityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    entity_name: str
    entity_type: str
    entity_id: UUID
    region: Optional[str]
    # V1 baseline for comparison
    v1_overall_score: float
    v1_signal_strength: str
    # V2 axes
    v2_pain_score: Optional[float]
    v2_recovery_score: Optional[float]
    v2_erp_fit_score: Optional[float]
    v2_reachability_score: Optional[float]
    v2_overall_score: Optional[float]
    v2_tier: Optional[str]
    v2_reasoning: Optional[Any]
    v2_computed_at: Optional[datetime]


class V2EvidenceItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    label: str
    detail: Optional[str] = None
    source_url: Optional[str] = None
    source_name: Optional[str] = None
    date: Optional[str] = None
    confidence: Optional[str] = None
    tag: Optional[str] = None  # "pain" | "article" | "action" | "bonus" | "penalty" | "neutral" | "profile"


class V2ErpMatch(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    erp_name: str
    vendor: str
    relevance_score: int                    # 1–5 scale
    fit_score: int                           # 0–10 sector fit (automotive or insurance)
    automotive_fit_score: int
    insurance_fit_score: int
    matched_keyword: str                     # the keyword that triggered the match
    match_source: str                        # human-readable reason
    # Detail fields for the expandable catalog card
    industries_strong_in: List[str]
    key_modules: List[str]
    notable_customers: List[str]
    mena_africa_adoption: Optional[str]
    top_pros: Optional[str]


class V2EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    entity_id: str
    entity_name: str
    entity_type: str
    pain_evidence: List[V2EvidenceItem]
    recovery_evidence: List[V2EvidenceItem]
    erp_fit_evidence: List[V2EvidenceItem]
    erp_catalog_matches: List[V2ErpMatch]   # matched rows from teamwill_erp_solutions
    erp_profile_sources: List[str]           # URLs from company_profile.source_urls
    reachability_evidence: List[V2EvidenceItem]


@app.get(
    "/api/opportunities/v2",
    response_model=List[V2OpportunityResponse],
    tags=["opportunities"],
    summary="V2 ranked opportunities with four-axis reasoning",
)
def list_v2_opportunities(
    tier: Optional[str] = Query(None, description="engage | develop | watch | needs_investigation"),
    min_score: Optional[float] = Query(None, ge=0, le=100, description="Minimum v2_overall_score"),
    limit: int = Query(50, ge=1, le=200),
):
    """V2 four-axis opportunity leaderboard. Returns full reasoning JSONB for radar charts."""
    with get_db_session() as session:
        q = session.query(OpportunitySignal)
        if tier:
            q = q.filter(OpportunitySignal.v2_tier == tier)
        if min_score is not None:
            q = q.filter(OpportunitySignal.v2_overall_score >= min_score)
        rows = (
            q.order_by(OpportunitySignal.v2_overall_score.desc().nullslast())
            .limit(limit)
            .all()
        )
        return [
            V2OpportunityResponse(
                entity_name=r.entity_name,
                entity_type=r.entity_type,
                entity_id=r.entity_id,
                region=r.region,
                v1_overall_score=float(r.overall_score),
                v1_signal_strength=r.signal_strength,
                v2_pain_score=float(r.v2_pain_score) if r.v2_pain_score is not None else None,
                v2_recovery_score=float(r.v2_recovery_score) if r.v2_recovery_score is not None else None,
                v2_erp_fit_score=float(r.v2_erp_fit_score) if r.v2_erp_fit_score is not None else None,
                v2_reachability_score=float(r.v2_reachability_score) if r.v2_reachability_score is not None else None,
                v2_overall_score=float(r.v2_overall_score) if r.v2_overall_score is not None else None,
                v2_tier=r.v2_tier,
                v2_reasoning=r.v2_reasoning,
                v2_computed_at=r.v2_computed_at,
            )
            for r in rows
        ]


@app.get(
    "/api/opportunities/v2/{entity_id}/evidence",
    response_model=V2EvidenceResponse,
    tags=["opportunities"],
    summary="Per-axis evidence links for the V2 radar explainer",
)
def get_v2_evidence(entity_id: UUID):
    """
    Returns four evidence buckets backing the V2 axis scores.
    Used by the Radar Modal to show clickable source links per axis.
    """
    with get_db_session() as session:
        sig = (
            session.query(OpportunitySignal)
            .filter(OpportunitySignal.entity_id == entity_id)
            .first()
        )
        if not sig:
            raise HTTPException(status_code=404, detail="No V2 signal found for this entity")

        eid_str   = str(entity_id)
        ent_type  = sig.entity_type
        ent_name  = sig.entity_name
        reasoning = sig.v2_reasoning or {}

        def _iso(d) -> Optional[str]:
            if d is None:
                return None
            return d.isoformat() if hasattr(d, "isoformat") else str(d)

        # ── Pain: negative reviews + keyword-matched articles ────────────
        pain_items: List[Dict[str, Any]] = []

        if ent_type == "brand":
            rev_rows = session.execute(text("""
                SELECT cr.source_url, cr.rating, cr.review_title, cr.review_date
                FROM car_reviews cr
                JOIN car_models cm ON cr.model_id = cm.id
                WHERE cm.brand_id = CAST(:eid AS uuid)
                  AND cr.data_origin = 'scraped'
                  AND cr.rating <= 2
                ORDER BY cr.review_date DESC NULLS LAST
                LIMIT 5
            """), {"eid": eid_str}).fetchall()
        else:
            rev_rows = session.execute(text("""
                SELECT source_url, rating, review_title, review_date
                FROM insurance_reviews
                WHERE company_id = CAST(:eid AS uuid)
                  AND data_origin = 'scraped'
                  AND rating <= 2
                ORDER BY review_date DESC NULLS LAST
                LIMIT 5
            """), {"eid": eid_str}).fetchall()

        for r in rev_rows:
            pain_items.append({
                "label": r.review_title or f"Review · {r.rating}/5",
                "detail": f"Rating: {r.rating}/5",
                "source_url": r.source_url,
                "date": _iso(r.review_date),
                "tag": "pain",
            })

        art_rows = session.execute(text("""
            SELECT title, source_url, publication_date
            FROM market_trend_articles
            WHERE LOWER(title) LIKE '%' || LOWER(:name) || '%'
              AND data_origin = 'scraped'
            ORDER BY publication_date DESC NULLS LAST
            LIMIT 5
        """), {"name": ent_name}).fetchall()

        for a in art_rows:
            pain_items.append({
                "label": a.title,
                "source_url": a.source_url,
                "date": _iso(a.publication_date),
                "tag": "article",
            })

        # ── Recovery: scraped action signals ─────────────────────────────
        action_rows = session.execute(text("""
            SELECT headline, signal_type, signal_date, confidence, source_url, source_name
            FROM company_action_signals
            WHERE entity_id = :eid
              AND polarity = 'action_taken'
              AND data_origin = 'scraped'
            ORDER BY signal_date DESC
        """), {"eid": eid_str}).fetchall()

        recovery_items: List[Dict[str, Any]] = [
            {
                "label": a.headline,
                "detail": (a.signal_type or "").replace("_", " ").title() or None,
                "source_url": a.source_url,
                "source_name": a.source_name,
                "date": _iso(a.signal_date),
                "confidence": a.confidence,
                "tag": "action",
            }
            for a in action_rows
        ]

        # ── ERP Fit: sub-segment profile + catalog matches ────────────────
        import re as _re

        erp_reasoning = (reasoning.get("axes") or {}).get("erp_fit") or {}
        sub_seg = erp_reasoning.get("sub_segment") or ""
        hq      = erp_reasoning.get("headquarters_country") or ""

        erp_items: List[Dict[str, Any]] = []
        if sub_seg:
            erp_items.append({"label": f"Sub-segment: {sub_seg}", "tag": "profile"})
        if hq:
            erp_items.append({"label": f"HQ: {hq}", "tag": "profile"})
        if erp_reasoning.get("sofico_keyword_hit"):
            erp_items.append({"label": "Sofico keyword match (+35 boost)", "tag": "bonus"})
        geo_bonus = erp_reasoning.get("geo_bonus") or 0
        if geo_bonus > 0:
            erp_items.append({"label": f"Geographic bonus: +{geo_bonus:.0f} (TEAMWILL territory)", "tag": "bonus"})

        # ── ERP catalog matching — multi-keyword search ──────────────────
        # Extract meaningful tokens from sub_segment + add entity-type base keyword.
        # This is wider than the scorer's ILIKE because here we want to explain
        # the match to a human, so we cast a broad net and let fit_score sort.
        _SKIP_WORDS = {
            "and", "the", "for", "of", "in", "a", "an", "is", "are",
            "first", "private", "insurer", "company", "group", "holding",
        }

        def _extract_keywords(seg: str, etype: str) -> List[str]:
            base = [etype]                                  # "insurance" or "brand"
            tokens = _re.split(r"[\+\-/,&\(\)\s]+", seg)
            for t in tokens:
                t = t.strip()
                if len(t) >= 3 and t.lower() not in _SKIP_WORDS:
                    base.append(t)
            return list(dict.fromkeys(base))[:8]           # deduplicate, cap at 8

        search_keywords = _extract_keywords(sub_seg, ent_type)

        # Fetch every ERP that matches at least one keyword; track which keyword hit
        seen_erp_ids: Dict[str, str] = {}   # erp_name → first matched keyword
        for kw in search_keywords:
            rows_kw = session.execute(text("""
                SELECT erp_name, vendor, teamwill_relevance_score,
                       automotive_fit_score, insurance_fit_score
                FROM teamwill_erp_solutions
                WHERE industries_strong_in::text ILIKE '%' || :kw || '%'
                  AND teamwill_relevance_score >= 3
                ORDER BY teamwill_relevance_score DESC, erp_name
                LIMIT 6
            """), {"kw": kw}).fetchall()
            for row in rows_kw:
                if row.erp_name not in seen_erp_ids:
                    seen_erp_ids[row.erp_name] = kw

        # Also check Sofico Miles explicitly (it matches on sub_segment keywords,
        # not on industries_strong_in which lists automotive/leasing verticals)
        if erp_reasoning.get("sofico_keyword_hit") and "Sofico Miles" not in seen_erp_ids:
            sofico_kws = ["captive", "leasing", "fleet", "auto finance", "mobility"]
            matched_sofico_kw = next(
                (kw for kw in sofico_kws if kw in sub_seg.lower()),
                "Sofico keyword"
            )
            seen_erp_ids["Sofico Miles"] = matched_sofico_kw

        # Fetch full records for all matched ERPs, sorted by fit then relevance
        erp_catalog_matches: List[V2ErpMatch] = []
        if seen_erp_ids:
            names_list = list(seen_erp_ids.keys())
            placeholders = ", ".join(f":n{i}" for i in range(len(names_list)))
            params: Dict[str, Any] = {f"n{i}": n for i, n in enumerate(names_list)}
            params["etype"] = ent_type
            full_rows = session.execute(text(f"""
                SELECT erp_name, vendor, teamwill_relevance_score,
                       automotive_fit_score, insurance_fit_score,
                       industries_strong_in, key_modules, notable_customers,
                       mena_africa_adoption, top_pros
                FROM teamwill_erp_solutions
                WHERE erp_name IN ({placeholders})
                  AND CASE WHEN :etype = 'brand'
                           THEN automotive_fit_score ELSE insurance_fit_score END >= 3
                ORDER BY
                    CASE WHEN :etype = 'brand'     THEN automotive_fit_score
                                                   ELSE insurance_fit_score END DESC NULLS LAST,
                    teamwill_relevance_score DESC NULLS LAST
                LIMIT 5
            """), params).fetchall()

            _rel_labels = {5: "certified TEAMWILL partner", 4: "high relevance", 3: "medium relevance"}

            for row in full_rows:
                fit = int(row.automotive_fit_score or 0) if ent_type == "brand" else int(row.insurance_fit_score or 0)
                kw  = seen_erp_ids.get(row.erp_name, "keyword match")
                rel = int(row.teamwill_relevance_score or 0)
                rel_label = _rel_labels.get(rel, "")
                match_src = (
                    f'Sofico/leasing keyword "{kw}" in sub-segment'
                    if row.erp_name == "Sofico Miles"
                    else f'Keyword "{kw}" in sub-segment matched ERP\'s target industries'
                )
                def _to_str_list(v) -> List[str]:
                    if isinstance(v, list):
                        return [str(x) for x in v]
                    return []

                erp_catalog_matches.append(V2ErpMatch(
                    erp_name=row.erp_name,
                    vendor=row.vendor,
                    relevance_score=rel,
                    fit_score=fit,
                    automotive_fit_score=int(row.automotive_fit_score or 0),
                    insurance_fit_score=int(row.insurance_fit_score or 0),
                    matched_keyword=kw,
                    match_source=f"{match_src}{' · ' + rel_label if rel_label else ''}",
                    industries_strong_in=_to_str_list(row.industries_strong_in),
                    key_modules=_to_str_list(row.key_modules)[:8],
                    notable_customers=_to_str_list(row.notable_customers)[:6],
                    mena_africa_adoption=row.mena_africa_adoption or None,
                    top_pros=row.top_pros or None,
                ))

        # ── Reachability: scraped tech stack records ──────────────────────
        tech_rows = session.execute(text("""
            SELECT vendor, product, evidence_excerpt, confidence,
                   source_url, source_name, detected_date
            FROM company_tech_stack
            WHERE entity_id = :eid
              AND data_origin = 'scraped'
            ORDER BY detected_date DESC NULLS LAST
        """), {"eid": eid_str}).fetchall()

        reach_axis   = (reasoning.get("axes") or {}).get("reachability") or {}
        raw_penalties = reach_axis.get("penalties") or []
        raw_bonuses   = reach_axis.get("bonuses") or []

        def _reach_tag(vendor: str) -> tuple:
            vl = vendor.lower()
            for p in raw_penalties:
                if vl in p.lower():
                    return "penalty", p
            for b in raw_bonuses:
                if vl in b.lower():
                    return "bonus", b
            return "neutral", None

        reach_items: List[Dict[str, Any]] = []
        for t in tech_rows:
            tag, label_detail = _reach_tag(t.vendor or "")
            reach_items.append({
                "label": t.vendor or "Unknown vendor",
                "detail": label_detail or t.evidence_excerpt,
                "source_url": t.source_url,
                "source_name": t.source_name,
                "date": _iso(t.detected_date),
                "confidence": t.confidence,
                "tag": tag,
            })

        # ── ERP profile sources: URLs from company_profile.source_urls ───
        profile_row = session.execute(text("""
            SELECT source_urls
            FROM company_profile
            WHERE entity_id = :eid
            LIMIT 1
        """), {"eid": eid_str}).fetchone()

        erp_profile_sources: List[str] = []
        if profile_row and profile_row.source_urls:
            raw = profile_row.source_urls
            # source_urls may be stored as a Python list (JSONB) or a JSON string
            if isinstance(raw, list):
                erp_profile_sources = [u for u in raw if isinstance(u, str) and u.startswith("http")]
            elif isinstance(raw, str):
                import json as _json
                try:
                    parsed = _json.loads(raw)
                    erp_profile_sources = [u for u in parsed if isinstance(u, str) and u.startswith("http")]
                except Exception:
                    pass

        return V2EvidenceResponse(
            entity_id=eid_str,
            entity_name=ent_name,
            entity_type=ent_type,
            pain_evidence=[V2EvidenceItem(**i) for i in pain_items],
            recovery_evidence=[V2EvidenceItem(**i) for i in recovery_items],
            erp_fit_evidence=[V2EvidenceItem(**i) for i in erp_items],
            erp_catalog_matches=erp_catalog_matches,
            erp_profile_sources=erp_profile_sources,
            reachability_evidence=[V2EvidenceItem(**i) for i in reach_items],
        )


# ---------------------------------------------------------------------------
# ERP Sales Brief endpoint — Groq-powered pitch recommendation
# NOTE: must be registered BEFORE /{entity_id} to avoid route shadowing
# ---------------------------------------------------------------------------

@app.get(
    "/api/opportunities/{entity_id}/erp-brief",
    tags=["opportunities"],
    summary="AI-generated ERP sales brief for a prospect (Groq LLaMA-3.3-70B)",
)
def get_erp_brief(entity_id: UUID):
    """
    Fetches entity pain data, top-3 matched ERPs, and relevant competitors,
    then calls Groq LLaMA-3.3-70B to produce a ranked sales brief as JSON.
    Attaches raw ERP score metadata in _metadata for the frontend evidence row.
    """
    import json as _json

    eid_str = str(entity_id)

    with get_db_session() as session:
        sig = session.execute(text("""
            SELECT entity_name, entity_type, company_state,
                   ceo_name, ceo_appointment_date, is_hiring_aggressively,
                   key_hiring_roles, top_complaint_types,
                   v2_pain_score, v2_recovery_score,
                   overall_score, v2_overall_score,
                   intervention_level, outreach_timing
            FROM opportunity_signals
            WHERE entity_id = :eid
            LIMIT 1
        """), {"eid": eid_str}).fetchone()

        if not sig:
            raise HTTPException(status_code=404, detail="Entity not found")

        ent_type = sig.entity_type

        try:
            profile = session.execute(text("""
                SELECT sub_segment, parent_company, headquarters_country, employee_count_range
                FROM company_profile
                WHERE entity_id = :eid
                LIMIT 1
            """), {"eid": eid_str}).fetchone()
        except Exception:
            profile = None

        try:
            signal_rows = session.execute(text("""
                SELECT headline, signal_type, signal_date
                FROM company_action_signals
                WHERE entity_id = :eid
                ORDER BY signal_date DESC NULLS LAST
                LIMIT 3
            """), {"eid": eid_str}).fetchall()
        except Exception:
            signal_rows = []

        fit_col = "automotive_fit_score" if ent_type == "brand" else "insurance_fit_score"
        try:
            erp_rows = session.execute(text(f"""
                SELECT erp_name, vendor, key_modules, notable_customers,
                       top_pros, automotive_fit_score, insurance_fit_score,
                       teamwill_relevance_score, mena_africa_adoption,
                       industries_strong_in
                FROM teamwill_erp_solutions
                WHERE teamwill_relevance_score >= 3
                ORDER BY {fit_col} DESC NULLS LAST,
                         teamwill_relevance_score DESC NULLS LAST
                LIMIT 3
            """)).fetchall()
        except Exception:
            erp_rows = []

        try:
            comp_rows = session.execute(text("""
                SELECT company_name, competitor_tier, overlap_with_teamwill_score,
                       erp_partnerships, primary_services
                FROM teamwill_competitors
                WHERE overlap_with_teamwill_score >= 4
                ORDER BY overlap_with_teamwill_score DESC NULLS LAST
                LIMIT 5
            """)).fetchall()
        except Exception:
            # Fallback: try without erp_partnerships in case column schema differs
            try:
                comp_rows = session.execute(text("""
                    SELECT company_name, competitor_tier, overlap_with_teamwill_score,
                           NULL AS erp_partnerships, primary_services
                    FROM teamwill_competitors
                    WHERE overlap_with_teamwill_score >= 4
                    ORDER BY overlap_with_teamwill_score DESC NULLS LAST
                    LIMIT 5
                """)).fetchall()
            except Exception:
                comp_rows = []

    def _to_list(v):
        if isinstance(v, list):
            return [str(x) for x in v]
        if isinstance(v, str):
            try:
                parsed = _json.loads(v)
                return [str(x) for x in parsed] if isinstance(parsed, list) else [v]
            except Exception:
                return [x.strip() for x in v.split(",") if x.strip()]
        return []

    def _ls(lst, limit=8):
        if not lst:
            return "none"
        return ", ".join(str(x) for x in list(lst)[:limit])

    complaints = _to_list(sig.top_complaint_types) if sig.top_complaint_types else []

    signals_text = "\n".join(
        f"  - [{s.signal_date}] {s.signal_type}: {s.headline}"
        for s in signal_rows
    ) or "  (no recent signals)"

    erps_text = ""
    for e in erp_rows:
        erps_text += f"""
ERP: {e.erp_name} by {e.vendor}
  Automotive fit: {e.automotive_fit_score}/10 | Insurance fit: {e.insurance_fit_score}/10 | TEAMWILL relevance: {e.teamwill_relevance_score}/5
  Industries served: {_ls(_to_list(e.industries_strong_in))}
  Key modules: {_ls(_to_list(e.key_modules))}
  Notable customers: {_ls(_to_list(e.notable_customers))}
  Top strengths: {e.top_pros or 'n/a'}
  MENA adoption: {e.mena_africa_adoption or 'n/a'}
"""

    competitors_text = "\n".join(
        f"  - {c.company_name} ({c.competitor_tier or 'unknown'}, overlap {c.overlap_with_teamwill_score}/5)\n"
        f"    Implements: {_ls(_to_list(c.erp_partnerships))}\n"
        f"    Services: {c.primary_services or 'n/a'}"
        for c in comp_rows
    ) or "  (none identified)"

    system_prompt = (
        "You are a senior ERP sales strategist at TEAMWILL, a specialized consulting firm "
        "certified on Sofico Miles for automotive finance/leasing and active across Europe, "
        "Tunisia, and MENA. Your job is to analyze a prospect company and produce a ranked "
        "ERP recommendation brief that a sales rep can use immediately.\n\n"
        "TEAMWILL's core differentiators:\n"
        "- Certified Sofico Miles partner (automotive finance/leasing/captive — unique in the market)\n"
        "- 11-country presence (France, Tunisia, Morocco, Spain, UK, Belgium, Germany, Portugal, Singapore, US, Italy)\n"
        "- Deep credit & asset finance domain (NOT a generalist consulting firm)\n"
        "- Mid-market speed: faster implementation than Tier 1 giants (Capgemini, Accenture)\n\n"
        "REASONING CHAIN you must follow for each ERP:\n"
        "Step 1: What is the REAL operational problem behind the complaint types? (Not the symptom — the root workflow breakdown)\n"
        "Step 2: Which specific modules of this ERP address that root problem?\n"
        "Step 3: Are there notable customers of this ERP that are direct industry peers of the prospect?\n"
        "Step 4: Does the prospect's company_state or recent signals create a buying window?\n"
        "Step 5: What is TEAMWILL's specific advantage selling this ERP vs Capgemini or BearingPoint?\n\n"
        "BANNED phrases: 'optimize operations', 'streamline processes', 'industry-leading', "
        "'robust solution', 'key features', 'comprehensive platform', 'leverage synergies', "
        "'best-in-class', 'end-to-end solution'\n\n"
        "OUTPUT FORMAT — respond ONLY with valid JSON, no markdown, no preamble:\n"
        '{"top_pick":{"erp_name":"...","rank":1,"verdict":"2-3 sentences. Specific. Uses real complaint types, real peer customers. No generic language.","tags":["3-4 short tags"],"opening_line":"One sentence referencing a real peer customer.","peer_customers":["names from notable_customers that are sector peers"],"teamwill_advantage":"1 sentence. Why TEAMWILL beats competitors for this specific prospect."},'
        '"alternative":{"erp_name":"...","rank":2,"verdict":"1-2 sentences. When to use this instead.","why_ranked_lower":"1 sentence.","tags":["2-3 tags"]},'
        '"competitor_alerts":[{"company_name":"...","tier":"...","threat":"1 sentence. Specific threat + how TEAMWILL counters it."}],'
        '"avoid":{"erp_name":"...","reason":"1 sentence. Why skip this despite the fit score."}}'
    )

    user_message = (
        f"PROSPECT: {sig.entity_name}\n"
        f"Type: {ent_type} | HQ: {profile.headquarters_country if profile else 'Unknown'}\n"
        f"Sub-segment: {profile.sub_segment if profile else 'Unknown'} | Parent: {profile.parent_company if profile else 'None'}\n"
        f"Employee range: {profile.employee_count_range if profile else 'Unknown'}\n\n"
        f"COMPANY STATE: {sig.company_state or 'Unknown'}\n"
        f"CEO: {sig.ceo_name or 'Unknown'} (appointed {sig.ceo_appointment_date.isoformat() if sig.ceo_appointment_date else 'unknown date'})\n"
        f"Hiring aggressively: {sig.is_hiring_aggressively}\n"
        f"Key roles being filled: {sig.key_hiring_roles or 'none specified'}\n\n"
        f"PAIN DATA:\n"
        f"Top complaint types: {_ls(complaints)}\n"
        f"Pain score: {float(sig.v2_pain_score or 0):.1f}/35 | Recovery score: {float(sig.v2_recovery_score or 0):.1f}/25\n"
        f"Overall opportunity score: {float(sig.v2_overall_score or sig.overall_score or 0):.1f}\n"
        f"Intervention level: {sig.intervention_level or '—'}\n\n"
        f"RECENT SIGNALS:\n{signals_text}\n\n"
        f"MATCHED ERP CATALOG (top 3 by fit score):\n{erps_text}\n"
        f"COMPETITORS WHO MAY BE IN THIS ACCOUNT:\n{competitors_text}\n\n"
        f"Now apply the reasoning chain and produce the JSON brief."
    )

    groq_key = os.environ.get("GROQ_API_KEY", "")
    if not groq_key:
        raise HTTPException(status_code=503, detail="GROQ_API_KEY not configured")

    try:
        from groq import Groq as _Groq
        _gc = _Groq(api_key=groq_key)
        resp = _gc.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_message},
            ],
            max_tokens=2048,
            temperature=0.25,
            top_p=0.85,
        )
        raw = resp.choices[0].message.content.strip()
        # Strip markdown code fences if the model wraps the JSON
        if raw.startswith("```"):
            raw = "\n".join(raw.split("\n")[1:])
        if raw.endswith("```"):
            raw = "\n".join(raw.split("\n")[:-1])
        brief = _json.loads(raw.strip())
    except _json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail=f"LLM returned invalid JSON: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Groq call failed: {exc}")

    # Attach raw ERP scores so the frontend can render the evidence row
    brief["_metadata"] = {
        "entity_name": sig.entity_name,
        "entity_type": ent_type,
        "erp_scores": {
            e.erp_name: {
                "automotive_fit": int(e.automotive_fit_score or 0),
                "insurance_fit":  int(e.insurance_fit_score  or 0),
                "teamwill_relevance": int(e.teamwill_relevance_score or 0),
                "mena_adoption": e.mena_africa_adoption or "—",
                "notable_customers": _to_list(e.notable_customers),
            }
            for e in erp_rows
        },
    }

    return brief


# ---------------------------------------------------------------------------
# Company Intelligence endpoint — must be registered BEFORE /{entity_id}
# ---------------------------------------------------------------------------

class ActionSignalOut(BaseModel):
    signal_type: Optional[str]
    signal_date: Optional[str]
    headline: Optional[str]
    summary: Optional[str]
    source_url: Optional[str]
    source_name: Optional[str]
    polarity: Optional[str]


class SentimentTrendOut(BaseModel):
    period_date: str
    negative_count: int
    positive_count: int
    neutral_count: int


class IntelligenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    entity_name: str
    entity_type: str
    entity_id: UUID
    region: Optional[str]
    overall_score: float
    signal_strength: str
    top_complaint_types: Optional[List[str]]
    v2_pain_score: Optional[float]
    v2_recovery_score: Optional[float]
    v2_erp_fit_score: Optional[float]
    v2_reachability_score: Optional[float]
    v2_overall_score: Optional[float]
    v2_tier: Optional[str]
    v2_reasoning: Optional[Any]
    company_state: Optional[str] = None
    ceo_name: Optional[str] = None
    ceo_appointment_date: Optional[Any] = None
    is_hiring_aggressively: Optional[bool] = None
    open_roles_estimate: Optional[int] = None
    key_hiring_roles: Optional[str] = None
    intervention_level: Optional[str] = None
    outreach_timing: Optional[str] = None
    trend_direction: Optional[str] = None
    intervention_brief: Optional[Any] = None
    recent_signals: List[ActionSignalOut] = []
    sentiment_trend: List[SentimentTrendOut] = []


@app.get(
    "/api/opportunities/intelligence",
    response_model=List[IntelligenceOut],
    tags=["opportunities"],
    summary="Full entity intelligence: scores + company state + signals + sentiment",
)
def list_intelligence():
    """Returns all entities with opportunity scores, company intelligence columns,
    last-5 action signals, and last-6-months sentiment trend."""
    with get_db_session() as session:
        opp_rows = session.execute(text("""
            SELECT
                entity_id, entity_name, entity_type, region,
                overall_score, signal_strength, top_complaint_types,
                v2_pain_score, v2_recovery_score, v2_erp_fit_score,
                v2_reachability_score, v2_overall_score, v2_tier, v2_reasoning,
                company_state, ceo_name, ceo_appointment_date,
                is_hiring_aggressively, open_roles_estimate, key_hiring_roles,
                intervention_level, outreach_timing, score_reasoning,
                intervention_brief,
                COALESCE(
                    trend_direction,
                    score_reasoning->'trend'->>'direction'
                ) AS trend_direction
            FROM opportunity_signals
            ORDER BY COALESCE(v2_overall_score, overall_score) DESC NULLS LAST
        """)).fetchall()

        if not opp_rows:
            return []

        entity_ids = [str(r.entity_id) for r in opp_rows]

        signals_rows = session.execute(text("""
            SELECT
                s.entity_id::text AS entity_id,
                s.signal_type,
                s.signal_date::text AS signal_date,
                s.headline, s.summary, s.source_url, s.source_name, s.polarity
            FROM company_action_signals s
            INNER JOIN (
                SELECT entity_id, signal_date
                FROM (
                    SELECT entity_id, signal_date,
                           ROW_NUMBER() OVER (PARTITION BY entity_id ORDER BY signal_date DESC NULLS LAST) AS rn
                    FROM company_action_signals
                    WHERE entity_id::text = ANY(:eids)
                ) ranked
                WHERE rn <= 5
            ) top ON top.entity_id = s.entity_id AND top.signal_date = s.signal_date
            ORDER BY s.entity_id, s.signal_date DESC NULLS LAST
        """), {"eids": entity_ids}).fetchall()

        signals_by_entity: Dict[str, List[ActionSignalOut]] = {}
        for sg in signals_rows:
            signals_by_entity.setdefault(sg.entity_id, []).append(ActionSignalOut(
                signal_type=sg.signal_type, signal_date=sg.signal_date,
                headline=sg.headline, summary=sg.summary,
                source_url=sg.source_url, source_name=sg.source_name, polarity=sg.polarity,
            ))

        brand_entity_ids = [str(r.entity_id) for r in opp_rows if r.entity_type == "brand"]
        sentiment_by_entity: Dict[str, List[SentimentTrendOut]] = {}
        if brand_entity_ids:
            sentiment_rows = session.execute(text("""
                SELECT brand_id::text AS entity_id,
                       period_date::text AS period_date,
                       negative_count, positive_count, neutral_count
                FROM sentiment_trends
                WHERE brand_id::text = ANY(:eids)
                  AND period_date >= NOW() - INTERVAL '6 months'
                ORDER BY brand_id, period_date ASC
            """), {"eids": brand_entity_ids}).fetchall()
            for st in sentiment_rows:
                sentiment_by_entity.setdefault(st.entity_id, []).append(SentimentTrendOut(
                    period_date=st.period_date,
                    negative_count=st.negative_count,
                    positive_count=st.positive_count,
                    neutral_count=st.neutral_count,
                ))

        results = []
        for r in opp_rows:
            eid_str = str(r.entity_id)
            results.append(IntelligenceOut(
                entity_name=r.entity_name, entity_type=r.entity_type,
                entity_id=r.entity_id, region=r.region,
                overall_score=float(r.overall_score), signal_strength=r.signal_strength,
                top_complaint_types=r.top_complaint_types,
                v2_pain_score=float(r.v2_pain_score) if r.v2_pain_score is not None else None,
                v2_recovery_score=float(r.v2_recovery_score) if r.v2_recovery_score is not None else None,
                v2_erp_fit_score=float(r.v2_erp_fit_score) if r.v2_erp_fit_score is not None else None,
                v2_reachability_score=float(r.v2_reachability_score) if r.v2_reachability_score is not None else None,
                v2_overall_score=float(r.v2_overall_score) if r.v2_overall_score is not None else None,
                v2_tier=r.v2_tier, v2_reasoning=r.v2_reasoning,
                company_state=r.company_state, ceo_name=r.ceo_name,
                ceo_appointment_date=str(r.ceo_appointment_date) if r.ceo_appointment_date else None,
                is_hiring_aggressively=r.is_hiring_aggressively,
                open_roles_estimate=r.open_roles_estimate, key_hiring_roles=r.key_hiring_roles,
                intervention_level=r.intervention_level, outreach_timing=r.outreach_timing,
                trend_direction=r.trend_direction,
                intervention_brief=r.intervention_brief,
                recent_signals=signals_by_entity.get(eid_str, []),
                sentiment_trend=sentiment_by_entity.get(eid_str, []),
            ))
        return results


@app.get(
    "/api/opportunities/{entity_id}",
    response_model=OpportunityOut,
    tags=["opportunities"],
    summary="Single opportunity signal by entity ID",
)
def get_opportunity(entity_id: UUID):
    """Return the opportunity signal for a specific entity (brand or insurer)."""
    with get_db_session() as session:
        signal = (
            session.query(OpportunitySignal)
            .filter(OpportunitySignal.entity_id == entity_id)
            .first()
        )
        if not signal:
            raise HTTPException(status_code=404, detail="No opportunity signal found for this entity")
        return OpportunityOut.model_validate(signal)


@app.get("/api/dashboard/summary", tags=["dashboard"], summary="One-shot overview for the dashboard")
def dashboard_summary():
    """
    Aggregated overview payload for the dashboard Overview page.
    Combines record counts, pipeline status, source health, and recent failures
    in a single round-trip.
    """
    from urllib.parse import urlparse as _urlparse
    with get_db_session() as session:
        total_car_reviews          = session.query(CarReview).count()
        total_insurance_reviews    = session.query(InsuranceReview).count()
        total_listings             = session.query(CarListing).count()
        total_articles             = session.query(MarketTrendArticle).count()
        total_competitors          = session.query(CompetitorPricing).count()
        total_brands               = session.query(CarBrand).filter(CarBrand.is_active.is_(True)).count()
        total_insurance_companies  = session.query(InsuranceCompany).count()

        # Ingestion sources distribution — use ReviewSource table directly
        # to show ALL sources with real scraped record counts, not just URL sampling
        from sqlalchemy import case as sa_case
        source_rows = (
            session.query(ReviewSource.name, ReviewSource.total_records_scraped)
            .filter(ReviewSource.total_records_scraped > 0)
            .order_by(ReviewSource.total_records_scraped.desc())
            .all()
        )
        # Also count MarketTrendArticle by source name for sources not tracked in ReviewSource
        article_source_rows = (
            session.query(ReviewSource.name, func.count(MarketTrendArticle.id))
            .join(MarketTrendArticle, MarketTrendArticle.source_id == ReviewSource.id)
            .filter(MarketTrendArticle.data_origin == "scraped")
            .group_by(ReviewSource.name)
            .all()
        )
        article_counts = {name: cnt for name, cnt in article_source_rows}

        review_sources_dict: dict = {}
        for name, total in source_rows:
            review_sources_dict[name] = total or 0
        # Merge article counts for sources not already counted
        for name, cnt in article_counts.items():
            if name not in review_sources_dict:
                review_sources_dict[name] = cnt

        review_sources = sorted(
            [{"source": k, "count": v} for k, v in review_sources_dict.items() if v > 0],
            key=lambda x: -x["count"],
        )[:10]

        # Provenance counts
        real_articles = session.query(MarketTrendArticle).filter(MarketTrendArticle.data_origin == "scraped").count()
        real_listings = session.query(CarListing).filter(CarListing.data_origin == "scraped").count()
        real_reviews  = session.query(CarReview).filter(CarReview.data_origin == "scraped").count()

    ps = pipeline_status()
    sh = sources_health()
    pf_page = pipeline_failures(limit=10, offset=0, source=None)

    return {
        "total_car_reviews": total_car_reviews,
        "total_insurance_reviews": total_insurance_reviews,
        "total_listings": total_listings,
        "total_articles": total_articles,
        "total_competitors": total_competitors,
        "total_brands": total_brands,
        "total_insurance_companies": total_insurance_companies,
        "review_sources": review_sources,
        "pipeline_status": ps,
        "source_health": [s.model_dump() for s in sh],
        "recent_failures": [f.model_dump() for f in pf_page.items],
        "provenance": {
            "real_articles": real_articles,
            "real_listings": real_listings,
            "real_reviews": real_reviews,
        },
    }


# ---------------------------------------------------------------------------
# GET /api/brands/summary — all brands with review counts + latest scores
# ---------------------------------------------------------------------------

@app.get("/api/brands/summary", response_model=List[BrandSummaryOut], tags=["brands"],
         summary="All brands with review counts and latest reputation scores")
def brands_summary(
    origin: Optional[str] = Query(None, description="Provenance filter for analytics: all | reference | scraped"),
):
    """Brand leaderboard: review counts, average rating, latest sentiment score."""
    analytics_origin = origin or "all"
    with get_db_session() as session:
        brands = session.query(CarBrand).filter(CarBrand.is_active.is_(True)).order_by(CarBrand.name).all()
        results = []
        for b in brands:
            review_q = (
                session.query(CarReview)
                .join(CarModel, CarReview.model_id == CarModel.id)
                .filter(CarModel.brand_id == b.id)
            )
            if origin:
                review_q = review_q.filter(CarReview.data_origin == origin)
            review_count = review_q.count()
            latest_rep = (
                session.query(BrandReputationScore)
                .filter(BrandReputationScore.brand_id == b.id,
                        BrandReputationScore.data_origin == analytics_origin)
                .order_by(BrandReputationScore.period_date.desc())
                .first()
            )
            results.append(BrandSummaryOut(
                id=b.id,
                name=b.name,
                country_of_origin=b.country_of_origin,
                founded_year=b.founded_year,
                review_count=review_count,
                avg_rating=round(latest_rep.avg_rating, 2) if latest_rep and latest_rep.avg_rating else None,
                avg_sentiment=round(float(latest_rep.avg_sentiment_score), 3)
                    if latest_rep and latest_rep.avg_sentiment_score else None,
                latest_period=latest_rep.period_date if latest_rep else None,
            ))
        return sorted(results, key=lambda x: -(x.review_count))


# ---------------------------------------------------------------------------
# GET /api/listings/summary
# ---------------------------------------------------------------------------

@app.get("/api/listings/summary", response_model=ListingSummaryOut, tags=["listings"],
         summary="Listings aggregate summary")
def listings_summary():
    """Aggregate stats: total, avg price, avg mileage, countries."""
    with get_db_session() as session:
        total = session.query(CarListing).count()
        rows = session.query(CarListing.listed_price, CarListing.mileage_km, CarListing.country, CarListing.currency).all()

        prices = [r.listed_price for r in rows if r.listed_price is not None and r.currency == "EUR"]
        mileages = [r.mileage_km for r in rows if r.mileage_km is not None]
        country_counts: dict = {}
        for r in rows:
            if r.country:
                country_counts[r.country] = country_counts.get(r.country, 0) + 1

        return ListingSummaryOut(
            total=total,
            avg_price=round(sum(prices) / len(prices), 0) if prices else None,
            avg_mileage=round(sum(mileages) / len(mileages), 0) if mileages else None,
            countries=len(country_counts),
            by_country=sorted(
                [SourceBreakdownItem(source=k, count=v) for k, v in country_counts.items()],
                key=lambda x: -x.count,
            )[:10],
        )


# ---------------------------------------------------------------------------
# GET /api/competitors/summary
# ---------------------------------------------------------------------------

@app.get("/api/competitors/summary", response_model=PricingSummaryOut, tags=["insurance"],
         summary="Competitor pricing aggregate summary")
def competitors_summary():
    """Aggregate pricing stats: total, avg price, by coverage type, by region."""
    with get_db_session() as session:
        rows = session.query(
            CompetitorPricing.price, CompetitorPricing.coverage_type, CompetitorPricing.region
        ).all()

        prices = [r.price for r in rows if r.price is not None]
        cov_counts: dict = {}
        reg_counts: dict = {}
        for r in rows:
            if r.coverage_type:
                cov_counts[r.coverage_type] = cov_counts.get(r.coverage_type, 0) + 1
            if r.region:
                reg_counts[r.region] = reg_counts.get(r.region, 0) + 1

        return PricingSummaryOut(
            total=len(rows),
            avg_price=round(sum(prices) / len(prices), 2) if prices else None,
            by_coverage=sorted(
                [SourceBreakdownItem(source=k, count=v) for k, v in cov_counts.items()],
                key=lambda x: -x.count,
            ),
            by_region=sorted(
                [SourceBreakdownItem(source=k, count=v) for k, v in reg_counts.items()],
                key=lambda x: -x.count,
            ),
        )


# ===========================================================================
# Phase 12 — Richer data endpoints
# ===========================================================================

class CarModelDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    brand_id: UUID
    brand_name: str
    name: str
    year: Optional[int]
    segment: Optional[str]
    body_type: Optional[str]
    engine_type: Optional[str]
    trim_level: Optional[str]
    transmission: Optional[str]
    drivetrain: Optional[str]
    horsepower_hp: Optional[int]
    torque_nm: Optional[int]
    battery_kwh: Optional[float]
    range_km: Optional[int]
    doors: Optional[int]
    seats: Optional[int]
    msrp_eur: Optional[float]
    review_count: int


class ArticleCategoryOut(BaseModel):
    category: str
    label: str
    count: int


# ---------------------------------------------------------------------------
# GET /api/models  — browsable model catalogue with spec data
# ---------------------------------------------------------------------------

@app.get("/api/models", response_model=PagedResponse, tags=["models"],
         summary="Browse all car models with full specification data")
def list_models(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    brand: Optional[str] = Query(None, description="Filter by brand name (case-insensitive)"),
    engine_type: Optional[str] = Query(None, description="Filter by engine type: Electric, Hybrid, Petrol, Diesel"),
    segment: Optional[str] = Query(None, description="Filter by segment, e.g. Compact SUV"),
    ev_only: bool = Query(False, description="Return only models with range data (EVs/PHEVs)"),
):
    """
    Full model catalogue with spec data: HP, transmission, drivetrain, EV range, MSRP.
    Filterable by brand, engine type, segment, or EV-only.
    """
    with get_db_session() as session:
        q = (
            session.query(CarModel, CarBrand)
            .join(CarBrand, CarModel.brand_id == CarBrand.id)
            .filter(CarBrand.deleted_at.is_(None))
        )
        if brand:
            q = q.filter(CarBrand.name.ilike(f"%{brand}%"))
        if engine_type:
            q = q.filter(CarModel.engine_type.ilike(f"%{engine_type}%"))
        if segment:
            q = q.filter(CarModel.segment.ilike(f"%{segment}%"))
        if ev_only:
            q = q.filter(CarModel.range_km.isnot(None))

        total = q.count()
        rows = (
            q.order_by(CarBrand.name, CarModel.name, CarModel.year)
            .offset(offset)
            .limit(limit)
            .all()
        )

        items = []
        for model, brand_obj in rows:
            review_count = (
                session.query(func.count(CarReview.id))
                .filter(CarReview.model_id == model.id)
                .scalar() or 0
            )
            items.append(CarModelDetailOut(
                id=model.id,
                brand_id=brand_obj.id,
                brand_name=brand_obj.name,
                name=model.name,
                year=model.year,
                segment=model.segment,
                body_type=model.body_type,
                engine_type=model.engine_type,
                trim_level=model.trim_level,
                transmission=model.transmission,
                drivetrain=model.drivetrain,
                horsepower_hp=model.horsepower_hp,
                torque_nm=model.torque_nm,
                battery_kwh=float(model.battery_kwh) if model.battery_kwh else None,
                range_km=model.range_km,
                doors=model.doors,
                seats=model.seats,
                msrp_eur=float(model.msrp_eur) if model.msrp_eur else None,
                review_count=review_count,
            ))

        return PagedResponse(total=total, limit=limit, offset=offset, items=items)


# ---------------------------------------------------------------------------
# GET /api/articles/categories  — article category distribution
# ---------------------------------------------------------------------------

@app.get("/api/articles/categories", response_model=List[ArticleCategoryOut], tags=["articles"],
         summary="Article count by category")
def article_categories():
    """Distribution of articles by editorial category."""
    with get_db_session() as session:
        rows = (
            session.query(
                MarketTrendArticle.category,
                func.count(MarketTrendArticle.id).label("cnt"),
            )
            .filter(MarketTrendArticle.category.isnot(None))
            .group_by(MarketTrendArticle.category)
            .order_by(func.count(MarketTrendArticle.id).desc())
            .all()
        )
        return [
            ArticleCategoryOut(
                category=r.category,
                label=_CATEGORY_LABELS.get((r.category or "").lower(), "General"),
                count=r.cnt,
            )
            for r in rows
        ]


# ---------------------------------------------------------------------------
# Helpers for event field extraction
# ---------------------------------------------------------------------------

def _extract_event_location(title: str, body: str) -> str:
    text = f"{title} {body}"
    
    # 1. Look for explicit Venue/Location
    match = re.search(r'(?:Venue|Location):\s*([^.\n]+)', text, re.IGNORECASE)
    if match:
        loc = match.group(1).strip()
        loc = re.sub(r',\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec).*$', '', loc, flags=re.IGNORECASE)
        if 3 < len(loc) < 60:
            return loc

    # 2. Extract from title dashes
    parts = re.split(r'[\u2014\u2013\uFFFD\-\|]', title)
    parts = [p.strip() for p in parts if p.strip()]
    if len(parts) >= 3:
        potential = parts[1]
        if not re.search(r'(january|february|march|april|may|june|july|august|september|october|november|december|q1|q2|q3|q4)', potential, re.IGNORECASE):
            if len(potential) < 50:
                return potential

    # 3. Fallback to keywords
    b = text.lower()
    locations = [
        ("nashville", "Nashville, TN"),
        ("las vegas", "Las Vegas, NV"),
        ("orlando", "Orlando, FL"),
        ("san francisco", "San Francisco, CA"),
        ("seattle", "Seattle, WA"),
        ("birmingham", "Birmingham, UK"),
        ("london", "London, UK"),
        ("são paulo", "São Paulo, Brazil"),
        ("sao paulo", "São Paulo, Brazil"),
        ("chicago", "Chicago, IL"),
        ("new york", "New York, NY"),
        ("paris", "Paris, France"),
        ("amsterdam", "Amsterdam, Netherlands"),
        ("dubai", "Dubai, UAE"),
        ("singapore", "Singapore"),
        ("tunis", "Tunis, Tunisia"),
        ("virtual", "Online"),
        ("online", "Online"),
    ]
    for keyword, label in locations:
        if keyword in b:
            return label
    return ""


def _extract_event_audience(body: str) -> str:
    b = body.lower()
    if "cio" in b or "cto" in b:
        return "C-Suite & Tech Leaders"
    if "dealer" in b or "automotive" in b:
        return "Automotive Professionals"
    if "insurer" in b or "underwriting" in b or "claims" in b:
        return "Insurance Leaders"
    if "startup" in b or "founder" in b or " vc " in b:
        return "Founders & Investors"
    if "erp" in b or "sap" in b or "dynamics" in b:
        return "ERP Practitioners"
    if "consultant" in b:
        return "Consultants"
    return "Enterprise Professionals"


class ArticleEventOut(ArticleOut):
    days_until: int = 0
    is_upcoming: bool = False
    is_this_month: bool = False
    is_past: bool = False
    event_location: str = ""
    event_audience: str = "Enterprise Professionals"

    @model_validator(mode="after")
    def _compute_event_fields(self) -> "ArticleEventOut":
        if self.publication_date:
            today = date.today()
            self.days_until = (self.publication_date - today).days
            self.is_upcoming = self.publication_date >= today
            self.is_past = self.publication_date < today
            self.is_this_month = (
                self.publication_date.year == today.year
                and self.publication_date.month == today.month
            )
        body = self.body_text or ""
        self.event_location = _extract_event_location(self.title or "", body)
        self.event_audience = _extract_event_audience(body)
        return self


# ---------------------------------------------------------------------------
# GET /api/articles/events  — upcoming and recent events/conferences
# ---------------------------------------------------------------------------

@app.get("/api/articles/events", response_model=List[ArticleEventOut], tags=["articles"],
         summary="Upcoming and recent professional events and conferences")
def article_events():
    """Returns seeded professional event articles, sorted by publication_date ASC."""
    with get_db_session() as session:
        rows = (
            session.query(MarketTrendArticle)
            .filter(
                or_(
                    MarketTrendArticle.data_origin == "seeded",
                    MarketTrendArticle.category.ilike("forum")
                ),
                MarketTrendArticle.publication_date.isnot(None),
                MarketTrendArticle.publication_date >= date.today()
            )
            .order_by(MarketTrendArticle.publication_date.asc())
            .all()
        )
        return [ArticleEventOut.model_validate(r) for r in rows]


# ---------------------------------------------------------------------------
# GET /api/listings/breakdown  — listing detail breakdown (fuel, color, transmission)
# ---------------------------------------------------------------------------

class ListingBreakdownOut(BaseModel):
    by_fuel_type: List[SourceBreakdownItem]
    by_transmission: List[SourceBreakdownItem]
    by_color: List[SourceBreakdownItem]
    by_country: List[SourceBreakdownItem]
    by_brand: List[SourceBreakdownItem]
    price_ranges: dict


@app.get("/api/listings/breakdown", response_model=ListingBreakdownOut, tags=["listings"],
         summary="Listing breakdown by fuel type, transmission, color, country, brand")
def listings_breakdown():
    """Detailed breakdown of listings by all key dimensions."""
    with get_db_session() as session:
        rows = session.query(
            CarListing.fuel_type,
            CarListing.transmission,
            CarListing.color,
            CarListing.country,
            CarListing.listed_price,
        ).all()

        fuel_counts: dict = {}
        trans_counts: dict = {}
        color_counts: dict = {}
        country_counts: dict = {}
        prices = []

        for r in rows:
            if r.fuel_type:
                fuel_counts[r.fuel_type] = fuel_counts.get(r.fuel_type, 0) + 1
            if r.transmission:
                trans_counts[r.transmission] = trans_counts.get(r.transmission, 0) + 1
            if r.color:
                color_counts[r.color] = color_counts.get(r.color, 0) + 1
            if r.country:
                country_counts[r.country] = country_counts.get(r.country, 0) + 1
            if r.listed_price:
                prices.append(float(r.listed_price))

        brand_counts_q = (
            session.query(CarBrand.name, func.count(CarListing.id).label("cnt"))
            .join(CarModel, CarListing.model_id == CarModel.id)
            .join(CarBrand, CarModel.brand_id == CarBrand.id)
            .group_by(CarBrand.name)
            .order_by(func.count(CarListing.id).desc())
            .limit(15)
            .all()
        )

        price_ranges = {}
        if prices:
            sorted_p = sorted(prices)
            n = len(sorted_p)
            price_ranges = {
                "min": round(sorted_p[0], 0),
                "max": round(sorted_p[-1], 0),
                "median": round(sorted_p[n // 2], 0),
                "avg": round(sum(prices) / n, 0),
                "under_25k": sum(1 for p in prices if p < 25000),
                "25k_50k": sum(1 for p in prices if 25000 <= p < 50000),
                "50k_100k": sum(1 for p in prices if 50000 <= p < 100000),
                "over_100k": sum(1 for p in prices if p >= 100000),
            }

        def top(d: dict, n: int = 10) -> List[SourceBreakdownItem]:
            return sorted(
                [SourceBreakdownItem(source=k, count=v) for k, v in d.items()],
                key=lambda x: -x.count
            )[:n]

        return ListingBreakdownOut(
            by_fuel_type=top(fuel_counts),
            by_transmission=top(trans_counts),
            by_color=top(color_counts, 12),
            by_country=top(country_counts),
            by_brand=[SourceBreakdownItem(source=r.name, count=r.cnt) for r in brand_counts_q],
            price_ranges=price_ranges,
        )


# ---------------------------------------------------------------------------
# PDF Export
# ---------------------------------------------------------------------------

@app.get(
    "/api/export/weekly-brief",
    tags=["export"],
    summary="Download PDF weekly intelligence brief",
)
def export_weekly_brief():
    """Generate and return a PDF market intelligence brief."""
    from datetime import datetime as _dt, timezone as _tz
    from analytics.pdf_exporter import generate_opportunity_brief

    with get_db_session() as session:
        pdf_bytes = generate_opportunity_brief(session)

    date_str = _dt.now(_tz.utc).strftime("%Y-%m-%d")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="teamwill-brief-{date_str}.pdf"'
        },
    )


@app.get(
    "/api/export/company/{company_type}/{company_id}",
    tags=["export"],
    summary="Download PDF pre-call brief for a single company",
)
def export_company_brief(company_type: str, company_id: UUID):
    """Generate and return a PDF pre-call intelligence brief for a car brand or insurance company."""
    from datetime import datetime as _dt, timezone as _tz
    from analytics.pdf_exporter import generate_company_brief

    if company_type == "car":
        profile = car_brand_profile(company_id)
    elif company_type == "insurance":
        profile = insurance_company_profile(company_id)
    else:
        raise HTTPException(status_code=400, detail="company_type must be 'car' or 'insurance'")

    profile_dict = profile.model_dump()
    pdf_bytes = generate_company_brief(profile_dict)

    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in profile_dict.get("name", "company"))
    date_str = _dt.now(_tz.utc).strftime("%Y-%m-%d")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="teamwill-{safe_name}-{date_str}.pdf"'
        },
    )


# ===========================================================================
# AI Market Analyst — Chat endpoint (Groq-powered, LLaMA 3.3 70B)
# ===========================================================================

from groq import Groq

# ===========================================================================
# RAG — Hybrid Retrieval-Augmented Generation Layer
# ===========================================================================
#
# Architecture:
#   Query ──► BGE-base-en-v1.5 (768-dim, L2-norm)
#          ──► Semantic search  (pgvector HNSW, cosine)   ┐
#          ──► BM25 full-text   (PostgreSQL tsvector GIN)  ├─► RRF merge
#          ──► Cross-encoder rerank (ms-marco-MiniLM-L-6) ─┘
#          ──► Grounded context injected into Groq LLaMA 3.3 70B prompt
#
# Models loaded lazily on first use (no startup penalty):
#   • BAAI/bge-base-en-v1.5          — retrieval embedding (~440 MB)
#   • cross-encoder/ms-marco-MiniLM-L-6-v2 — reranking     (~67 MB)
# ===========================================================================

_RAG_EMBEDDER = None
_RAG_CROSS_ENCODER = None
# BGE query instruction prefix (passages have NO prefix — asymmetric retrieval)
_BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


def _safe_str(text: str) -> str:
    """Strip surrogate characters that break UTF-8 / JSON encoding.
    Review texts scraped from the web sometimes contain lone surrogates
    (U+D800–U+DFFF) that are invalid in UTF-8 and cause UnicodeEncodeError
    when Groq serialises the request body.
    """
    return text.encode("utf-8", errors="replace").decode("utf-8")


def _get_rag_embedder():
    global _RAG_EMBEDDER
    if _RAG_EMBEDDER is None:
        from sentence_transformers import SentenceTransformer
        _RAG_EMBEDDER = SentenceTransformer("BAAI/bge-base-en-v1.5")
    return _RAG_EMBEDDER


def _get_cross_encoder():
    global _RAG_CROSS_ENCODER
    if _RAG_CROSS_ENCODER is None:
        from sentence_transformers import CrossEncoder
        _RAG_CROSS_ENCODER = CrossEncoder(
            "cross-encoder/ms-marco-MiniLM-L-6-v2", max_length=512
        )
    return _RAG_CROSS_ENCODER


def _embed_query(text: str) -> list:
    """Embed a query string with BGE query prefix, L2-normalised."""
    model = _get_rag_embedder()
    emb = model.encode(_BGE_QUERY_PREFIX + text, normalize_embeddings=True)
    return emb.tolist()


def _rrf_merge(ranked_lists: list, k: int = 60) -> list:
    """
    Reciprocal Rank Fusion across multiple ranked doc lists.
    k=60 is the standard constant from the original RRF paper (Cormack 2009).
    """
    scores: dict = {}
    docs: dict = {}
    for ranked in ranked_lists:
        for rank, doc in enumerate(ranked):
            doc_id = doc["id"]
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
            if doc_id not in docs:
                docs[doc_id] = doc
    merged = sorted(docs.values(), key=lambda d: scores[d["id"]], reverse=True)
    for doc in merged:
        doc["rrf_score"] = round(scores[doc["id"]], 6)
    return merged


def _cross_rerank(query: str, candidates: list) -> list:
    """
    Cross-encoder reranking of candidates for final precision.
    Returns candidates sorted by rerank_score descending.
    """
    if not candidates:
        return candidates
    encoder = _get_cross_encoder()
    pairs = [(query, c["text"][:500]) for c in candidates]
    scores = encoder.predict(pairs)
    for cand, score in zip(candidates, scores):
        cand["rerank_score"] = float(score)
    return sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)


# ---------------------------------------------------------------------------
# Per-corpus semantic search helpers (pgvector cosine)
# ---------------------------------------------------------------------------

def _cosine_top_n(query_emb: list, rows_with_emb: list, top_n: int) -> list:
    """
    Pure numpy cosine similarity ranking.
    Both query and stored embeddings are L2-normalised by BGE, so
    cosine similarity == dot product — no division needed.
    rows_with_emb: list of (doc_dict, embedding_list) tuples.
    Returns top_n doc_dicts sorted by similarity descending.
    """
    import numpy as np
    if not rows_with_emb:
        return []
    q = np.array(query_emb, dtype=np.float32)
    matrix = np.array([r[1] for r in rows_with_emb], dtype=np.float32)
    scores = matrix @ q  # shape (n,)
    top_idx = np.argsort(scores)[::-1][:top_n]
    result = []
    for idx in top_idx:
        doc = dict(rows_with_emb[idx][0])
        doc["score"] = float(scores[idx])
        result.append(doc)
    return result


def _sem_articles(query_emb: list, session, top_n: int = 20) -> list:
    from sqlalchemy import text as _t
    sql = _t("""
        SELECT
            id::text          AS id,
            title,
            coalesce(body_text, '') AS body,
            category,
            region,
            publication_date::text AS pub_date,
            embedding
        FROM market_trend_articles
        WHERE embedding IS NOT NULL
    """)
    try:
        rows = session.execute(sql).fetchall()
    except Exception:
        return []
    pairs = [
        (
            {
                "id": r.id,
                "text": f"{r.title}. {r.body[:400]}",
                "source_type": "article",
                "score": 0.0,
                "metadata": {"category": r.category, "region": r.region, "date": r.pub_date},
            },
            r.embedding,
        )
        for r in rows if r.embedding
    ]
    return _cosine_top_n(query_emb, pairs, top_n)


def _bm25_articles(query: str, session, top_n: int = 20) -> list:
    from sqlalchemy import text as _t
    sql = _t("""
        SELECT
            id::text          AS id,
            title,
            coalesce(body_text, '') AS body,
            category,
            region,
            publication_date::text AS pub_date,
            ts_rank_cd(
                to_tsvector('english', coalesce(title,'') || ' ' || coalesce(body_text,'')),
                plainto_tsquery('english', :q)
            ) AS score
        FROM market_trend_articles
        WHERE to_tsvector('english', coalesce(title,'') || ' ' || coalesce(body_text,''))
              @@ plainto_tsquery('english', :q)
        ORDER BY score DESC
        LIMIT :n
    """)
    try:
        rows = session.execute(sql, {"q": query, "n": top_n}).fetchall()
    except Exception:
        return []
    return [
        {
            "id": r.id,
            "text": f"{r.title}. {r.body[:400]}",
            "source_type": "article",
            "score": float(r.score),
            "metadata": {"category": r.category, "region": r.region, "date": r.pub_date},
        }
        for r in rows
    ]


def _sem_car_reviews(query_emb: list, session, top_n: int = 20, brand_name: str = None) -> list:
    from sqlalchemy import text as _t
    brand_clause = (
        "AND cm.brand_id IN (SELECT id FROM car_brands WHERE name ILIKE :brand)"
        if brand_name else ""
    )
    sql = _t(f"""
        SELECT
            cr.id::text       AS id,
            coalesce(cr.review_title, '') AS rtitle,
            cr.review_text,
            cr.rating,
            cr.review_date::text AS rev_date,
            cm.name           AS model_name,
            cb.name           AS brand_name,
            cr.embedding
        FROM car_reviews cr
        JOIN car_models cm ON cr.model_id = cm.id
        JOIN car_brands cb ON cm.brand_id = cb.id
        WHERE cr.embedding IS NOT NULL {brand_clause}
    """)
    params: dict = {}
    if brand_name:
        params["brand"] = f"%{brand_name}%"
    try:
        rows = session.execute(sql, params).fetchall()
    except Exception:
        return []
    pairs = [
        (
            {
                "id": r.id,
                "text": f"{r.brand_name} {r.model_name}: {r.rtitle}. {r.review_text[:350]}",
                "source_type": "car_review",
                "score": 0.0,
                "metadata": {
                    "brand": r.brand_name, "model": r.model_name,
                    "rating": float(r.rating) if r.rating else None, "date": r.rev_date,
                },
            },
            r.embedding,
        )
        for r in rows if r.embedding
    ]
    return _cosine_top_n(query_emb, pairs, top_n)


def _sem_insurance_reviews(
    query_emb: list, session, top_n: int = 20, company_name: str = None
) -> list:
    from sqlalchemy import text as _t
    company_clause = "AND ic.name ILIKE :company" if company_name else ""
    sql = _t(f"""
        SELECT
            ir.id::text       AS id,
            coalesce(ir.review_title, '') AS rtitle,
            ir.review_text,
            ir.rating,
            ir.review_date::text AS rev_date,
            ic.name           AS company_name,
            ir.embedding
        FROM insurance_reviews ir
        JOIN insurance_companies ic ON ir.company_id = ic.id
        WHERE ir.embedding IS NOT NULL {company_clause}
    """)
    params: dict = {}
    if company_name:
        params["company"] = f"%{company_name}%"
    try:
        rows = session.execute(sql, params).fetchall()
    except Exception:
        return []
    pairs = [
        (
            {
                "id": r.id,
                "text": f"{r.company_name}: {r.rtitle}. {r.review_text[:350]}",
                "source_type": "insurance_review",
                "score": 0.0,
                "metadata": {
                    "company": r.company_name,
                    "rating": float(r.rating) if r.rating else None, "date": r.rev_date,
                },
            },
            r.embedding,
        )
        for r in rows if r.embedding
    ]
    return _cosine_top_n(query_emb, pairs, top_n)


# ---------------------------------------------------------------------------
# Primary RAG retrieval function
# ---------------------------------------------------------------------------

def _rag_retrieve(
    query: str,
    session,
    corpus: str = "all",
    top_k: int = 5,
    brand_name: str = None,
    company_name: str = None,
    pool: int = 20,
) -> list:
    """
    Full hybrid RAG pipeline:
      1. Embed query with BGE-base-en-v1.5 (768-dim, L2-norm)
      2. Semantic search per corpus (pgvector cosine via CAST)
      3. BM25 full-text search (PostgreSQL tsvector) for articles
      4. RRF merge across all ranked lists
      5. Cross-encoder rerank top-40 → top_k

    corpus: "articles" | "car_reviews" | "insurance_reviews" | "all"
    Returns list of dicts: {id, text, source_type, score, rrf_score, rerank_score, metadata}
    Silently returns [] on any infrastructure error (embeddings not indexed yet, etc.).
    """
    try:
        query_emb = _embed_query(query)
    except Exception:
        return []

    ranked_lists: list = []

    if corpus in ("articles", "all"):
        sem = _sem_articles(query_emb, session, pool)
        bm25 = _bm25_articles(query, session, pool)
        # RRF within the article corpus (semantic + keyword)
        article_pool = _rrf_merge([sem, bm25])[:pool] if (sem or bm25) else []
        if article_pool:
            ranked_lists.append(article_pool)

    if corpus in ("car_reviews", "all"):
        sem = _sem_car_reviews(query_emb, session, pool, brand_name)
        if sem:
            ranked_lists.append(sem)

    if corpus in ("insurance_reviews", "all"):
        sem = _sem_insurance_reviews(query_emb, session, pool, company_name)
        if sem:
            ranked_lists.append(sem)

    if not ranked_lists:
        return []

    # Global RRF across all corpora
    merged = _rrf_merge(ranked_lists) if len(ranked_lists) > 1 else ranked_lists[0]

    # Cross-encoder rerank top-40 → top_k
    reranked = _cross_rerank(query, merged[:40])
    return reranked[:top_k]


class AnalystMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str

class AnalystChatRequest(BaseModel):
    messages: List[AnalystMessage]

class AnalystChatResponse(BaseModel):
    reply: str
    context_used: List[str] = Field(default_factory=list)


def _gather_analyst_context(session) -> tuple[str, list[str]]:
    """Query live DB data to build a context snapshot for the AI analyst."""
    context_parts: list[str] = []
    sources: list[str] = []

    # 1. Record counts
    total_reviews = session.query(CarReview).count()
    total_insurance = session.query(InsuranceReview).count()
    total_listings = session.query(CarListing).count()
    total_articles = session.query(MarketTrendArticle).count()
    total_brands = session.query(CarBrand).count()
    total_competitors = session.query(CompetitorPricing).count()

    context_parts.append(
        f"DATABASE OVERVIEW: {total_reviews} car reviews, {total_insurance} insurance reviews, "
        f"{total_listings} listings, {total_articles} articles, {total_brands} brands, "
        f"{total_competitors} competitor pricing records."
    )
    sources.append("record_counts")

    # 2. Brand reputation scores (latest period)
    brands = session.query(CarBrand).filter(CarBrand.is_active.is_(True)).order_by(CarBrand.name).all()
    brand_lines = []
    for b in brands:
        rep = (
            session.query(BrandReputationScore)
            .filter(BrandReputationScore.brand_id == b.id)
            .order_by(BrandReputationScore.period_date.desc())
            .first()
        )
        review_count = (
            session.query(func.count(CarReview.id))
            .join(CarModel, CarReview.model_id == CarModel.id)
            .filter(CarModel.brand_id == b.id)
            .scalar() or 0
        )
        rating_str = f"avg_rating={round(rep.avg_rating, 2)}" if rep and rep.avg_rating else "no rating"
        sentiment_str = f"sentiment={round(float(rep.avg_sentiment_score), 3)}" if rep and rep.avg_sentiment_score else "no sentiment"
        brand_lines.append(f"  - {b.name} ({b.country_of_origin or '?'}): {review_count} reviews, {rating_str}, {sentiment_str}")

    if brand_lines:
        context_parts.append("BRAND INTELLIGENCE:\n" + "\n".join(brand_lines[:20]))
        sources.append("brand_reputation")

    # 3. Opportunity signals
    opp_signals = (
        session.query(OpportunitySignal)
        .order_by(OpportunitySignal.overall_score.desc())
        .limit(10)
        .all()
    )
    if opp_signals:
        opp_lines = []
        for s in opp_signals:
            complaints = ", ".join(s.top_complaint_types[:2]) if s.top_complaint_types else "none"
            opp_lines.append(
                f"  - {s.entity_name} ({s.entity_type}, {s.region or 'global'}): "
                f"score={round(float(s.overall_score))}/100, strength={s.signal_strength}, "
                f"complaints=[{complaints}]"
            )
        context_parts.append("TOP OPPORTUNITY SIGNALS:\n" + "\n".join(opp_lines))
        sources.append("opportunity_signals")

    # 4. Listing price summary
    prices = session.query(CarListing.listed_price).filter(CarListing.listed_price.isnot(None)).all()
    if prices:
        price_vals = sorted([float(p[0]) for p in prices])
        n = len(price_vals)
        context_parts.append(
            f"LISTING PRICES: {n} with price data. "
            f"Min={round(price_vals[0])}, Median={round(price_vals[n//2])}, "
            f"Max={round(price_vals[-1])}, Avg={round(sum(price_vals)/n)}."
        )
        sources.append("listing_prices")

    # 5. Article categories
    cat_rows = (
        session.query(MarketTrendArticle.category, func.count(MarketTrendArticle.id))
        .filter(MarketTrendArticle.category.isnot(None))
        .group_by(MarketTrendArticle.category)
        .order_by(func.count(MarketTrendArticle.id).desc())
        .limit(10)
        .all()
    )
    if cat_rows:
        cat_str = ", ".join(f"{r[0]}({r[1]})" for r in cat_rows)
        context_parts.append(f"ARTICLE CATEGORIES: {cat_str}")
        sources.append("article_categories")

    # 6. Recent pipeline health
    recent_steps = (
        session.query(PipelineStepRun)
        .order_by(PipelineStepRun.started_at.desc())
        .limit(5)
        .all()
    )
    if recent_steps:
        step_lines = []
        for st in recent_steps:
            step_lines.append(
                f"  - {st.step_name}: {st.status}, "
                f"processed={st.records_processed}, failed={st.records_failed}"
            )
        context_parts.append("RECENT PIPELINE STEPS:\n" + "\n".join(step_lines))
        sources.append("pipeline_health")

    return "\n\n".join(context_parts), sources


def _call_groq(system_prompt: str, user_message: str, history: list) -> str:
    """Call Groq API (LLaMA 3.3 70B) with system prompt, history, and new message."""
    groq_key = os.environ.get("GROQ_API_KEY", "")
    if not groq_key:
        raise HTTPException(
            status_code=503,
            detail="GROQ_API_KEY not configured. Add it to .env to enable the AI analyst.",
        )

    client = Groq(api_key=groq_key)

    messages: list[dict] = [{"role": "system", "content": system_prompt}]

    # Add conversation history (last 6 messages for context window)
    for msg in history[-6:]:
        messages.append({"role": msg["role"], "content": msg["content"]})

    # Add the new user message
    messages.append({"role": "user", "content": user_message})

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        max_tokens=1024,
        temperature=0.3,   # conservative nucleus: factual market QA, reduces hallucination
        top_p=0.85,        # nucleus sampling — Holtzman et al. (2020)
    )

    return response.choices[0].message.content


@app.post(
    "/api/analyst/chat",
    response_model=AnalystChatResponse,
    tags=["analyst"],
    summary="AI Market Analyst chat powered by Groq (LLaMA 3.3 70B)",
)
async def analyst_chat(body: AnalystChatRequest):
    """
    Send a conversation to the AI Market Analyst.

    Context strategy (layered):
      1. Structural overview — record counts, brand scores, opportunity signals (static SQL).
         Gives the LLM a "map" of what data exists.
      2. RAG evidence — top-8 chunks semantically matched to the user's actual question
         via hybrid retrieval (pgvector + BM25 + RRF) and cross-encoder reranking.
         Grounds the answer in real reviews and articles, not just aggregates.
    """
    if not body.messages:
        raise HTTPException(status_code=400, detail="messages list cannot be empty")

    # Extract the user's last message before opening the session
    all_msgs = [{"role": m.role, "content": m.content} for m in body.messages]
    history = all_msgs[:-1]
    user_message = all_msgs[-1]["content"]

    # Gather structural context + RAG evidence in one session
    with get_db_session() as session:
        db_context, sources = _gather_analyst_context(session)

        # RAG: retrieve the 8 most relevant chunks for this specific question
        rag_section = ""
        try:
            rag_hits = _rag_retrieve(
                query=user_message,
                session=session,
                corpus="all",
                top_k=8,
                pool=20,
            )
            if rag_hits:
                lines = []
                for hit in rag_hits:
                    stype = hit["source_type"].replace("_", " ").title()
                    meta = hit.get("metadata", {})
                    meta_str = ", ".join(
                        f"{k}={v}" for k, v in meta.items() if v is not None
                    )
                    lines.append(f"[{stype}] ({meta_str})\n{hit['text'][:350]}")
                rag_section = _safe_str(
                    "\n\nRETRIEVED EVIDENCE — semantically matched to the question above "
                    "(hybrid search + cross-encoder reranked):\n"
                    + "\n---\n".join(lines)
                )
                sources.append("rag_retrieval")
        except Exception:
            pass  # RAG is additive; structural context remains available

    system_prompt = (
        "You are the AI Market Analyst for the Automotive Intelligence Platform, "
        "an expert system built by TEAMWILL. You have access to live database intelligence "
        "about car brands, reviews, listings, insurance companies, competitor pricing, "
        "opportunity signals, and market articles.\n\n"
        "LIVE DATABASE CONTEXT (structural overview):\n"
        f"{db_context}"
        f"{rag_section}\n\n"
        "INSTRUCTIONS:\n"
        "- Prioritise the RETRIEVED EVIDENCE above when it is relevant — it contains "
        "actual review texts and article excerpts grounded in real data.\n"
        "- Cite specific numbers, brand names, and review quotes from the evidence.\n"
        "- Provide actionable market intelligence insights for TEAMWILL sales reps.\n"
        "- When discussing opportunity signals, explain what drives the scores.\n"
        "- Be concise but thorough. Use bullet points for clarity.\n"
        "- If asked something not covered by the data, say so honestly.\n"
        "- Format responses with markdown for readability.\n"
    )

    try:
        reply_text = _call_groq(system_prompt, user_message, history)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Groq API error: {str(exc)[:300]}")

    return AnalystChatResponse(reply=reply_text, context_used=sources)


# ---------------------------------------------------------------------------
# POST /api/analyst/summarize — stateless, cached AI summaries
# ---------------------------------------------------------------------------

class SummarizeRequest(BaseModel):
    context: str = ""
    type: str = Field(..., pattern="^(overview|opportunity|brand|market_news)$")

class SummarizeResponse(BaseModel):
    summary: str
    generated_at: str

# Simple in-memory cache: key → (summary, timestamp)
_summary_cache: dict[str, tuple[str, float]] = {}
_CACHE_TTL = 600  # 10 minutes

_SUMMARIZE_PROMPTS: dict[str, str] = {
    "overview": (
        "Write a 2-sentence weekly market intelligence pulse. "
        "Mention the most notable signal or trend from the data. "
        "Be specific with numbers. Write for a sales executive audience."
    ),
    "opportunity": (
        "Write a 2-sentence business recommendation based on the top opportunity signals. "
        "Name the company with the strongest signal and explain why TEAMWILL should contact them. "
        "Be direct and actionable."
    ),
    "brand": (
        "Write a 2-sentence insight about the specified brand based on review data and sentiment. "
        "Mention specific metrics. If sentiment is negative, frame it as an ERP opportunity for TEAMWILL."
    ),
    "market_news": (
        "Write a 2-sentence summary of the market article landscape. "
        "Mention the top categories and any notable trends in coverage."
    ),
}


@app.post(
    "/api/analyst/summarize",
    response_model=SummarizeResponse,
    tags=["analyst"],
    summary="Generate a short AI summary (cached 10 min)",
)
async def analyst_summarize(body: SummarizeRequest):
    """
    Stateless, one-shot AI summary. Results are cached for 10 minutes.
    Types: overview, opportunity, brand, market_news.
    """
    import time as _time

    cache_key = f"{body.type}:{body.context}"
    now = _time.time()

    # Check cache
    if cache_key in _summary_cache:
        cached_text, cached_at = _summary_cache[cache_key]
        if now - cached_at < _CACHE_TTL:
            return SummarizeResponse(
                summary=cached_text,
                generated_at=datetime.fromtimestamp(cached_at).isoformat(),
            )

    # Gather DB context
    with get_db_session() as session:
        db_context, _ = _gather_analyst_context(session)

    type_instruction = _SUMMARIZE_PROMPTS.get(body.type, _SUMMARIZE_PROMPTS["overview"])
    system_prompt = (
        "You are a concise market intelligence analyst for TEAMWILL's Automotive Intelligence Platform.\n\n"
        f"LIVE DATABASE CONTEXT:\n{db_context}\n\n"
        "RULES:\n"
        "- Maximum 2-3 sentences.\n"
        "- Cite specific numbers from the data.\n"
        "- No markdown formatting, no bullet points — plain prose.\n"
        "- Be direct and insightful.\n"
    )

    user_msg = type_instruction
    if body.context:
        user_msg += f"\n\nAdditional context: {body.context}"

    try:
        reply = _call_groq(system_prompt, user_msg, [])
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Groq API error: {str(exc)[:300]}")

    # Cache result
    _summary_cache[cache_key] = (reply, now)

    return SummarizeResponse(summary=reply, generated_at=datetime.now().isoformat())


# ---------------------------------------------------------------------------
# Source Management — CRUD for review_sources
# ---------------------------------------------------------------------------

class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    base_url: str
    source_type: Optional[str]
    reliability_score: float
    is_active: bool
    region: Optional[str]
    keywords: Optional[List[str]]
    last_scraped_at: Optional[datetime]
    total_records_scraped: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


class SourceCreateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    base_url: str = Field(..., min_length=1)
    source_type: Optional[str] = None
    reliability_score: float = Field(default=0.8, ge=0, le=1)
    is_active: bool = True
    region: Optional[str] = None
    keywords: Optional[List[str]] = None


class SourcePatchIn(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    source_type: Optional[str] = None
    reliability_score: Optional[float] = Field(default=None, ge=0, le=1)
    is_active: Optional[bool] = None
    region: Optional[str] = None
    keywords: Optional[List[str]] = None


def _source_to_out(s: ReviewSource, record_count: int = 0, last_scraped: Optional[datetime] = None) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "base_url": s.base_url,
        "source_type": s.source_type.value if s.source_type else None,
        "reliability_score": float(s.reliability_score),
        "is_active": s.is_active,
        "region": s.region,
        "keywords": s.keywords,
        "last_scraped_at": last_scraped or s.last_scraped_at,
        "total_records_scraped": record_count if record_count else s.total_records_scraped,
        "created_at": s.created_at,
        "updated_at": s.updated_at,
    }


def _compute_source_stats(session) -> dict:
    """Compute live record counts and last-scraped timestamps per source_id."""
    from sqlalchemy import union_all, literal_column

    # Aggregate counts and max scraped_at from all tables with source_id FK
    tables = [CarReview, InsuranceReview, CarListing, MarketTrendArticle, CompetitorPricing]
    subqueries = []
    for tbl in tables:
        sq = (
            session.query(
                tbl.source_id.label("source_id"),
                func.count().label("cnt"),
                func.max(tbl.scraped_at).label("last_at"),
            )
            .filter(tbl.source_id.isnot(None))
            .group_by(tbl.source_id)
            .subquery()
        )
        subqueries.append(
            session.query(
                sq.c.source_id,
                sq.c.cnt,
                sq.c.last_at,
            )
        )

    combined = union_all(*[q.statement for q in subqueries]).subquery()
    rows = (
        session.query(
            combined.c.source_id,
            func.sum(combined.c.cnt).label("total"),
            func.max(combined.c.last_at).label("last_scraped"),
        )
        .group_by(combined.c.source_id)
        .all()
    )
    return {r.source_id: (int(r.total), r.last_scraped) for r in rows}


@app.get(
    "/api/sources",
    response_model=List[SourceOut],
    tags=["sources"],
    summary="List all scraping sources",
)
def list_sources(include_deleted: bool = False):
    with get_db_session() as session:
        q = session.query(ReviewSource)
        if not include_deleted:
            q = q.filter(ReviewSource.deleted_at.is_(None))
        sources = q.order_by(ReviewSource.name).all()
        stats = _compute_source_stats(session)
        result = []
        for s in sources:
            cnt, last = stats.get(s.id, (0, None))
            result.append(_source_to_out(s, record_count=cnt, last_scraped=last))
        return result


@app.post(
    "/api/sources",
    response_model=SourceOut,
    tags=["sources"],
    summary="Create a new scraping source",
    status_code=201,
)
def create_source(body: SourceCreateIn):
    from database.enums import SourceType as STEnum
    with get_db_session() as session:
        existing = session.query(ReviewSource).filter(ReviewSource.name == body.name).first()
        if existing:
            raise HTTPException(status_code=409, detail=f"Source '{body.name}' already exists")

        st = None
        if body.source_type:
            try:
                st = STEnum(body.source_type)
            except ValueError:
                raise HTTPException(status_code=422, detail=f"Invalid source_type: {body.source_type}")

        src = ReviewSource(
            name=body.name,
            base_url=body.base_url,
            source_type=st,
            reliability_score=body.reliability_score,
            is_active=body.is_active,
            region=body.region,
            keywords=body.keywords,
        )
        session.add(src)
        session.flush()
        return _source_to_out(src)


@app.patch(
    "/api/sources/{source_id}",
    response_model=SourceOut,
    tags=["sources"],
    summary="Update a scraping source",
)
def update_source(source_id: UUID, body: SourcePatchIn):
    from database.enums import SourceType as STEnum
    with get_db_session() as session:
        src = session.query(ReviewSource).filter(ReviewSource.id == source_id).first()
        if not src:
            raise HTTPException(status_code=404, detail="Source not found")

        patch = body.model_dump(exclude_unset=True)
        for key, val in patch.items():
            if key == "source_type" and val is not None:
                try:
                    val = STEnum(val)
                except ValueError:
                    raise HTTPException(status_code=422, detail=f"Invalid source_type: {val}")
            setattr(src, key, val)

        session.flush()
        return _source_to_out(src)


@app.delete(
    "/api/sources/{source_id}",
    tags=["sources"],
    summary="Soft-delete a scraping source",
    status_code=204,
)
def delete_source(source_id: UUID):
    with get_db_session() as session:
        src = session.query(ReviewSource).filter(ReviewSource.id == source_id).first()
        if not src:
            raise HTTPException(status_code=404, detail="Source not found")
        src.deleted_at = datetime.now()
        session.flush()
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Pipeline Trigger — run scrapers as background subprocesses
# ---------------------------------------------------------------------------

_SCRAPER_SCRIPTS: Dict[str, str] = {
    "reviews": "scripts/run_reviews_ingest.py",
    "listings": "scripts/run_listings_ingest.py",
    "articles": "scripts/run_rss_ingest.py",
}

# Track running processes: run_id → { process, scraper, started_at }
_running_pipelines: Dict[str, Dict] = {}


class TriggerRequest(BaseModel):
    scraper: str = Field(..., pattern=r"^(reviews|listings|articles|all)$")


class TriggerResponse(BaseModel):
    run_id: str
    status: str
    scraper: str


class PipelineStatusOut(BaseModel):
    run_id: str
    status: str
    scraper: str
    records_scraped: int
    records_stored: int
    started_at: Optional[str]
    finished_at: Optional[str]
    duration_seconds: Optional[int]
    error_message: Optional[str]


def _run_scraper_subprocess(run_id: str, scraper_key: str, script_path: str):
    """Run a scraper script in a subprocess and update PipelineRun when done."""
    from database.enums import PipelineStatus as PS

    python_exe = os.path.join(_PROJECT_ROOT, ".venv", "Scripts", "python.exe")
    if not os.path.exists(python_exe):
        python_exe = sys.executable

    full_script = os.path.join(_PROJECT_ROOT, script_path)

    try:
        proc = subprocess.Popen(
            [python_exe, full_script],
            cwd=_PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        _running_pipelines[run_id]["pid"] = proc.pid
        proc.wait()
        return_code = proc.returncode

        with get_db_session() as session:
            run = session.query(PipelineRun).filter(PipelineRun.id == run_id).first()
            if run:
                run.finished_at = datetime.now(timezone.utc)
                if return_code == 0:
                    run.status = PS.SUCCESS
                else:
                    run.status = PS.FAILED
                    stdout_tail = ""
                    if proc.stdout:
                        try:
                            stdout_tail = proc.stdout.read().decode("utf-8", errors="replace")[-500:]
                        except Exception:
                            pass
                    run.error_message = f"Exit code {return_code}. {stdout_tail}"
                session.flush()
    except Exception as exc:
        with get_db_session() as session:
            run = session.query(PipelineRun).filter(PipelineRun.id == run_id).first()
            if run:
                run.finished_at = datetime.now(timezone.utc)
                run.status = PS.FAILED
                run.error_message = str(exc)[:500]
                session.flush()
    finally:
        _running_pipelines.pop(run_id, None)


def _run_all_scrapers(run_id: str):
    """Run all scrapers sequentially in one background thread."""
    from database.enums import PipelineStatus as PS

    python_exe = os.path.join(_PROJECT_ROOT, ".venv", "Scripts", "python.exe")
    if not os.path.exists(python_exe):
        python_exe = sys.executable

    had_failure = False
    for key, script in _SCRAPER_SCRIPTS.items():
        full_script = os.path.join(_PROJECT_ROOT, script)
        try:
            proc = subprocess.Popen(
                [python_exe, full_script],
                cwd=_PROJECT_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )
            _running_pipelines[run_id]["pid"] = proc.pid
            _running_pipelines[run_id]["current_scraper"] = key
            proc.wait()
            if proc.returncode != 0:
                had_failure = True
        except Exception:
            had_failure = True

    with get_db_session() as session:
        run = session.query(PipelineRun).filter(PipelineRun.id == run_id).first()
        if run:
            run.finished_at = datetime.now(timezone.utc)
            run.status = PS.PARTIAL if had_failure else PS.SUCCESS
            if had_failure:
                run.error_message = "One or more scrapers failed"
            session.flush()

    _running_pipelines.pop(run_id, None)


@app.post(
    "/api/pipeline/trigger",
    response_model=TriggerResponse,
    tags=["pipeline"],
    summary="Trigger a scraping pipeline run",
)
def trigger_pipeline(body: TriggerRequest):
    from database.enums import PipelineStatus as PS

    with get_db_session() as session:
        run = PipelineRun(
            task_name=f"manual_{body.scraper}",
            started_at=datetime.now(timezone.utc),
            status=PS.RUNNING,
        )
        session.add(run)
        session.flush()
        run_id = str(run.id)

    _running_pipelines[run_id] = {
        "scraper": body.scraper,
        "started_at": datetime.now(timezone.utc),
    }

    if body.scraper == "all":
        t = threading.Thread(target=_run_all_scrapers, args=(run_id,), daemon=True)
    else:
        script = _SCRAPER_SCRIPTS[body.scraper]
        t = threading.Thread(target=_run_scraper_subprocess, args=(run_id, body.scraper, script), daemon=True)

    t.start()

    return TriggerResponse(run_id=run_id, status="started", scraper=body.scraper)


@app.get(
    "/api/pipeline/status/{run_id}",
    response_model=PipelineStatusOut,
    tags=["pipeline"],
    summary="Get status of a pipeline run",
)
def pipeline_run_status(run_id: UUID):
    with get_db_session() as session:
        run = session.query(PipelineRun).filter(PipelineRun.id == run_id).first()
        if not run:
            raise HTTPException(status_code=404, detail="Pipeline run not found")

        duration = None
        if run.started_at:
            end = run.finished_at or datetime.now(timezone.utc)
            duration = int((end - run.started_at).total_seconds())

        # Get scraper name from in-memory tracker or task_name
        scraper = "unknown"
        rid = str(run_id)
        if rid in _running_pipelines:
            scraper = _running_pipelines[rid].get("current_scraper", _running_pipelines[rid].get("scraper", "unknown"))
        elif run.task_name.startswith("manual_"):
            scraper = run.task_name.replace("manual_", "")

        return PipelineStatusOut(
            run_id=str(run.id),
            status=run.status.value if run.status else "unknown",
            scraper=scraper,
            records_scraped=run.records_scraped or 0,
            records_stored=run.records_stored or 0,
            started_at=run.started_at.isoformat() if run.started_at else None,
            finished_at=run.finished_at.isoformat() if run.finished_at else None,
            duration_seconds=duration,
            error_message=run.error_message,
        )


@app.get(
    "/api/pipeline/events/{run_id}",
    tags=["pipeline"],
    summary="SSE stream for pipeline run progress — pushes status every second until done",
)
async def pipeline_events(run_id: UUID):
    import json as _json
    import asyncio

    async def _generate():
        rid = str(run_id)
        while True:
            with get_db_session() as session:
                run = session.query(PipelineRun).filter(PipelineRun.id == rid).first()
                if not run:
                    yield 'data: {"error": "run not found"}\n\n'
                    return

                duration = None
                if run.started_at:
                    end = run.finished_at or datetime.now(timezone.utc)
                    duration = int((end - run.started_at).total_seconds())

                scraper = "unknown"
                if rid in _running_pipelines:
                    scraper = _running_pipelines[rid].get(
                        "current_scraper",
                        _running_pipelines[rid].get("scraper", "unknown"),
                    )
                elif run.task_name.startswith("manual_"):
                    scraper = run.task_name.replace("manual_", "")

                status = run.status.value if run.status else "unknown"
                payload = _json.dumps({
                    "run_id": rid,
                    "status": status,
                    "scraper": scraper,
                    "records_scraped": run.records_scraped or 0,
                    "records_stored": run.records_stored or 0,
                    "duration_seconds": duration,
                    "error_message": run.error_message,
                })
                yield f"data: {payload}\n\n"

                if status != "running":
                    return

            await asyncio.sleep(1)

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Global real-time event stream (SSE broadcast)
# ---------------------------------------------------------------------------

import asyncio as _asyncio
import json as _json_mod

# Registry of connected client queues — one per open SSE connection
_sse_clients: list[_asyncio.Queue] = []


async def _broadcast(event: dict) -> None:
    """Push an event dict to every connected SSE client."""
    for q in list(_sse_clients):
        try:
            q.put_nowait(event)
        except _asyncio.QueueFull:
            pass


@app.get(
    "/api/events/stream",
    tags=["events"],
    summary="Global SSE stream — pipeline completions, new signals, heartbeat",
)
async def global_event_stream():
    """
    Persistent Server-Sent Events stream.

    Emits:
      {"type": "connected"}                          — on connect
      {"type": "heartbeat"}                          — every 25 s (keep-alive)
      {"type": "pipeline_complete", "component": str,
       "records": int, "status": str}               — when a pipeline run finishes
      {"type": "opportunity_update", "strong": int,
       "moderate": int, "total": int,
       "top_entity": str, "top_score": float}        — when signals are rescored
      {"type": "data_update", "entity": str,
       "count": int}                                 — when new reviews/articles land
    """
    queue: _asyncio.Queue = _asyncio.Queue(maxsize=50)
    _sse_clients.append(queue)

    # Snapshot of DB state at connection time — used to detect changes
    _last_seen: dict = {}

    async def _seed_snapshot():
        with get_db_session() as s:
            _last_seen["pipeline_ts"] = (
                s.query(func.max(PipelineRun.finished_at))
                .filter(PipelineRun.status.in_(["success", "failed", "partial"]))
                .scalar()
            )
            _last_seen["signal_ts"] = s.query(func.max(OpportunitySignal.updated_at)).scalar()
            _last_seen["review_count"] = s.query(func.count(CarReview.id)).scalar()

    async def _poll():
        """Poll DB every 3 s and push events when something changes."""
        while True:
            await _asyncio.sleep(3)
            try:
                with get_db_session() as s:
                    # ── Pipeline completions ──────────────────────────────
                    latest_run_ts = (
                        s.query(func.max(PipelineRun.finished_at))
                        .filter(PipelineRun.status.in_(["success", "failed", "partial"]))
                        .scalar()
                    )
                    if latest_run_ts and latest_run_ts != _last_seen.get("pipeline_ts"):
                        run = (
                            s.query(PipelineRun)
                            .filter(PipelineRun.finished_at == latest_run_ts)
                            .first()
                        )
                        if run:
                            await _broadcast({
                                "type": "pipeline_complete",
                                "component": run.task_name or "unknown",
                                "records": (run.records_stored or 0) + (run.records_scraped or 0),
                                "status": run.status.value if run.status else "unknown",
                            })
                        _last_seen["pipeline_ts"] = latest_run_ts

                    # ── Opportunity signal updates ────────────────────────
                    latest_signal_ts = s.query(func.max(OpportunitySignal.updated_at)).scalar()
                    if latest_signal_ts and latest_signal_ts != _last_seen.get("signal_ts"):
                        strong = s.query(func.count(OpportunitySignal.id)).filter(
                            OpportunitySignal.signal_strength == "strong"
                        ).scalar() or 0
                        moderate = s.query(func.count(OpportunitySignal.id)).filter(
                            OpportunitySignal.signal_strength == "moderate"
                        ).scalar() or 0
                        top = (
                            s.query(OpportunitySignal)
                            .order_by(OpportunitySignal.overall_score.desc())
                            .first()
                        )
                        await _broadcast({
                            "type": "opportunity_update",
                            "strong": strong,
                            "moderate": moderate,
                            "total": strong + moderate,
                            "top_entity": top.entity_name if top else "",
                            "top_score": float(top.overall_score) if top else 0.0,
                        })
                        _last_seen["signal_ts"] = latest_signal_ts

                    # ── New reviews landed ────────────────────────────────
                    review_count = s.query(func.count(CarReview.id)).scalar() or 0
                    if review_count != _last_seen.get("review_count"):
                        delta = review_count - (_last_seen.get("review_count") or 0)
                        if delta > 0:
                            await _broadcast({
                                "type": "data_update",
                                "entity": "car_reviews",
                                "count": delta,
                            })
                        _last_seen["review_count"] = review_count

            except Exception:
                pass  # Never crash the poll loop

    async def _generate():
        await _seed_snapshot()
        poll_task = _asyncio.create_task(_poll())
        try:
            yield f'data: {_json_mod.dumps({"type": "connected"})}\n\n'
            heartbeat = 0
            while True:
                try:
                    event = await _asyncio.wait_for(queue.get(), timeout=5.0)
                    yield f'data: {_json_mod.dumps(event)}\n\n'
                except _asyncio.TimeoutError:
                    heartbeat += 5
                    if heartbeat >= 25:
                        yield f'data: {_json_mod.dumps({"type": "heartbeat"})}\n\n'
                        heartbeat = 0
        except GeneratorExit:
            pass
        finally:
            poll_task.cancel()
            if queue in _sse_clients:
                _sse_clients.remove(queue)

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ---------------------------------------------------------------------------
# Keyword Monitoring — CRUD + search trigger
# ---------------------------------------------------------------------------

class KeywordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    keyword: str
    region: Optional[str]
    is_active: bool
    last_searched_at: Optional[datetime]
    results_count: int
    created_at: Optional[datetime]


class KeywordCreateIn(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=200)
    region: Optional[str] = None


class KeywordSearchResult(BaseModel):
    articles_found: int
    articles_inserted: int
    articles_duplicate: int
    keywords_searched: int


@app.get(
    "/api/keywords",
    response_model=List[KeywordOut],
    tags=["keywords"],
    summary="List all search keywords",
)
def list_keywords():
    with get_db_session() as session:
        keywords = session.query(SearchKeyword).order_by(SearchKeyword.keyword).all()
        return [KeywordOut.model_validate(k) for k in keywords]


@app.post(
    "/api/keywords",
    response_model=KeywordOut,
    tags=["keywords"],
    summary="Add a search keyword",
    status_code=201,
)
def create_keyword(body: KeywordCreateIn):
    with get_db_session() as session:
        existing = session.query(SearchKeyword).filter(
            SearchKeyword.keyword == body.keyword
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail=f"Keyword '{body.keyword}' already exists")

        kw = SearchKeyword(keyword=body.keyword, region=body.region)
        session.add(kw)
        session.flush()
        return KeywordOut.model_validate(kw)


@app.delete(
    "/api/keywords/{keyword_id}",
    tags=["keywords"],
    summary="Delete a search keyword",
    status_code=204,
)
def delete_keyword(keyword_id: UUID):
    with get_db_session() as session:
        kw = session.query(SearchKeyword).filter(SearchKeyword.id == keyword_id).first()
        if not kw:
            raise HTTPException(status_code=404, detail="Keyword not found")
        session.delete(kw)
        session.flush()
    return Response(status_code=204)


@app.post(
    "/api/keywords/search-now",
    response_model=KeywordSearchResult,
    tags=["keywords"],
    summary="Trigger immediate keyword search",
)
def keyword_search_now():
    from scrapers.keyword_scraper import run_keyword_search
    metrics = run_keyword_search(max_articles_per_keyword=15)
    return KeywordSearchResult(
        articles_found=metrics["articles_found"],
        articles_inserted=metrics["articles_inserted"],
        articles_duplicate=metrics["articles_duplicate"],
        keywords_searched=metrics["keywords_searched"],
    )


# ---------------------------------------------------------------------------
# Atlas Magazine scraper endpoint
# ---------------------------------------------------------------------------

class AtlasMagazineResult(BaseModel):
    fetched: int
    inserted: int
    duplicate: int
    errors: int


@app.post(
    "/api/scrape/atlas-magazine",
    response_model=AtlasMagazineResult,
    tags=["scraping"],
    summary="Scrape Atlas Magazine RSS feed (MENA insurance news)",
)
def scrape_atlas_magazine():
    """Fetch the Atlas Magazine RSS feed and store new articles as MarketTrendArticles."""
    from scrapers.atlas_magazine_scraper import run_atlas_magazine_scraper
    metrics = run_atlas_magazine_scraper()
    return AtlasMagazineResult(**metrics)


# ---------------------------------------------------------------------------
# Automobile.tn scraper endpoint
# ---------------------------------------------------------------------------

class AutomobileTnResult(BaseModel):
    brands_scraped: int
    models_found: int
    inserted: int
    duplicate: int
    errors: int


@app.post(
    "/api/scrape/automobile-tn",
    response_model=AutomobileTnResult,
    tags=["scraping"],
    summary="Scrape automobile.tn for new-car prices in Tunisia (TND)",
)
def scrape_automobile_tn():
    """Scrape automobile.tn brand pages and store new car listings with TND prices."""
    from scrapers.automobile_tn_scraper import run_automobile_tn_scraper
    metrics = run_automobile_tn_scraper()
    return AutomobileTnResult(**metrics)


# ---------------------------------------------------------------------------
# RSS news scrapers — Motor1, InsideEVs, Insurance Journal, Business News TN,
#                     L'Economiste Maghrebin
# ---------------------------------------------------------------------------

class RssFeedResult(BaseModel):
    source: str
    fetched: int
    inserted: int
    duplicate: int
    errors: int


class RssAllResult(BaseModel):
    results: List[RssFeedResult]
    total_inserted: int


@app.post(
    "/api/scrape/rss-news",
    response_model=RssAllResult,
    tags=["scraping"],
    summary="Run all 5 RSS news scrapers (Motor1, InsideEVs, Insurance Journal, Business News TN, L'Economiste)",
)
def scrape_rss_news_all():
    """Fetch all five news RSS feeds and store new articles."""
    from scrapers.rss_news_scraper import run_all_rss_scrapers
    results = run_all_rss_scrapers()
    total = sum(r.get("inserted", 0) for r in results)
    return RssAllResult(results=[RssFeedResult(**r) for r in results], total_inserted=total)


@app.post(
    "/api/scrape/rss-news/{source_slug}",
    response_model=RssFeedResult,
    tags=["scraping"],
    summary="Run a single RSS scraper by slug",
)
def scrape_rss_news_single(source_slug: str):
    """
    Run one RSS scraper. Valid slugs:
    motor1 | insideevs | insurance-journal | business-news-tn | economiste-maghrebin
    """
    from scrapers.rss_news_scraper import (
        run_motor1_scraper, run_insideevs_scraper, run_insurance_journal_scraper,
        run_business_news_tn_scraper, run_economiste_maghrebin_scraper,
    )
    slug_map = {
        "motor1": run_motor1_scraper,
        "insideevs": run_insideevs_scraper,
        "insurance-journal": run_insurance_journal_scraper,
        "business-news-tn": run_business_news_tn_scraper,
        "economiste-maghrebin": run_economiste_maghrebin_scraper,
    }
    runner = slug_map.get(source_slug)
    if not runner:
        raise HTTPException(status_code=404, detail=f"Unknown slug '{source_slug}'. Valid: {list(slug_map)}")
    return RssFeedResult(**runner())


# ---------------------------------------------------------------------------
# Google Places scraper endpoint
# ---------------------------------------------------------------------------

class GooglePlacesResult(BaseModel):
    fetched: int = 0
    inserted_insurance: int = 0
    inserted_car: int = 0
    errors: int = 0
    not_found: int = 0
    error: Optional[str] = None


@app.post(
    "/api/scrape/google-places",
    response_model=GooglePlacesResult,
    tags=["scraping"],
    summary="Scrape Google Places reviews for TN insurance companies and car dealers",
)
def scrape_google_places(include_insurance: bool = True, include_cars: bool = True):
    """
    Requires GOOGLE_PLACES_API_KEY in .env.
    Returns metrics with inserted review counts.
    """
    from scrapers.google_places_scraper import run_google_places_scraper
    result = run_google_places_scraper(include_insurance=include_insurance, include_cars=include_cars)
    return GooglePlacesResult(**result)


# ---------------------------------------------------------------------------
# Trustpilot insurance scraper endpoint
# ---------------------------------------------------------------------------

class TrustpilotInsuranceResult(BaseModel):
    fetched: int
    inserted: int
    duplicate: int
    errors: int
    by_company: dict


@app.post(
    "/api/scrape/trustpilot-insurance",
    response_model=TrustpilotInsuranceResult,
    tags=["scraping"],
    summary="Scrape Trustpilot reviews for EU insurance companies (Groupama, AXA, Allianz, Generali, Munich Re)",
)
def scrape_trustpilot_insurance(pages_per_company: int = Query(5, ge=1, le=20)):
    """Fetch Trustpilot customer reviews for major EU insurers active in MENA/TN markets."""
    from scrapers.trustpilot_insurance_scraper import run_trustpilot_insurance_scraper
    return TrustpilotInsuranceResult(**run_trustpilot_insurance_scraper(pages_per_company=pages_per_company))


# ---------------------------------------------------------------------------
# NHTSA Complaints scraper — free, no key required
# ---------------------------------------------------------------------------

class NhtsaResult(BaseModel):
    fetched: int
    inserted: int
    duplicate: int
    skipped: int
    errors: int
    by_brand: Dict[str, Any]


@app.post(
    "/api/scrape/nhtsa-complaints",
    response_model=NhtsaResult,
    tags=["scraping"],
    summary="Fetch NHTSA consumer complaints for all car brands/models (free, no key needed)",
)
def scrape_nhtsa_complaints(years_back: int = Query(3, ge=1, le=10)):
    """
    Pull real consumer complaints from the US NHTSA public API.
    Complaints are stored as CarReview rows (verified=True, rating=null).
    No API key required.
    """
    from scrapers.nhtsa_complaints_scraper import run_nhtsa_complaints_scraper
    return NhtsaResult(**run_nhtsa_complaints_scraper(years_back=years_back))


# ---------------------------------------------------------------------------
# Reddit scraper — free OAuth script app
# ---------------------------------------------------------------------------

class RedditResult(BaseModel):
    fetched: int
    inserted: int
    duplicate: int
    errors: int


@app.post(
    "/api/scrape/reddit",
    response_model=RedditResult,
    tags=["scraping"],
    summary="Scrape Reddit posts from insurance and automotive subreddits",
)
def scrape_reddit(
    include_insurance: bool = Query(True),
    include_cars: bool = Query(True),
):
    """
    Fetch Reddit posts from r/Insurance, r/CarInsurance, r/cars, etc.
    Requires REDDIT_CLIENT_ID + REDDIT_CLIENT_SECRET in .env.
    Register free at https://www.reddit.com/prefs/apps (type: script).
    """
    from scrapers.reddit_scraper import run_reddit_scraper
    result = run_reddit_scraper(include_insurance=include_insurance, include_cars=include_cars)
    if "error" in result:
        raise HTTPException(status_code=503, detail=result["error"])
    return RedditResult(**result)


# ---------------------------------------------------------------------------
# NewsAPI scraper — free developer key
# ---------------------------------------------------------------------------

class NewsApiResult(BaseModel):
    fetched: int
    inserted: int
    duplicate: int
    errors: int


@app.post(
    "/api/scrape/newsapi",
    response_model=NewsApiResult,
    tags=["scraping"],
    summary="Fetch news articles from NewsAPI.org for insurance and automotive topics",
)
def scrape_newsapi(
    include_insurance: bool = Query(True),
    include_cars: bool = Query(True),
):
    """
    Fetch recent news from NewsAPI.org (free dev tier: 100 req/day).
    Requires NEWS_API_KEY in .env.
    Register free at https://newsapi.org/register.
    """
    from scrapers.newsapi_scraper import run_newsapi_scraper
    result = run_newsapi_scraper(include_insurance=include_insurance, include_cars=include_cars)
    if "error" in result:
        raise HTTPException(status_code=503, detail=result["error"])
    return NewsApiResult(**result)


# ---------------------------------------------------------------------------
# newsdata.io scraper — real-time news with free API key
# ---------------------------------------------------------------------------

class NewsdataResult(BaseModel):
    fetched: int
    inserted: int
    duplicate: int
    errors: int


@app.post(
    "/api/scrape/newsdata",
    response_model=NewsdataResult,
    tags=["scraping"],
    summary="Fetch news articles from newsdata.io for insurance and automotive topics",
)
def scrape_newsdata(
    include_insurance: bool = Query(True),
    include_cars: bool = Query(True),
):
    """
    Fetch recent news from newsdata.io (free tier: 200 credits/day, 10 results/request).
    Requires NEWSDATA_API_KEY in .env.
    Articles are stored as MarketTrendArticles and surface in:
    - /api/articles (Market Pulse page)
    - /api/company/{type}/{id}/news (Company Radar)
    - Weekly Brief latest radar sidebar
    """
    from scrapers.newsdata_scraper import run_newsdata_scraper
    result = run_newsdata_scraper(include_insurance=include_insurance, include_cars=include_cars)
    if "error" in result:
        raise HTTPException(status_code=503, detail=result["error"])
    return NewsdataResult(**result)


# ---------------------------------------------------------------------------
# Company news feed — recent articles relevant to a company profile
# ---------------------------------------------------------------------------

class CompanyNewsItem(BaseModel):
    id: UUID
    title: str
    source_url: str
    publication_date: Optional[str]
    category: Optional[str]
    region: Optional[str]
    source_name: Optional[str]


@app.get(
    "/api/company/{company_type}/{company_id}/news",
    response_model=List[CompanyNewsItem],
    tags=["company-radar"],
    summary="Recent news articles relevant to a company profile",
)
def company_news(company_type: str, company_id: UUID, limit: int = Query(5, ge=1, le=20)):
    """
    Return the most recent scraped articles relevant to a company's sector.

    Article selection strategy:
    - PRIORITY SLOTS (up to 2): articles specifically about ERP/management systems,
      managerial/organisational problems, or mechanical/engine issues — not just brand mentions.
    - REMAINING SLOTS: best general brand/sector articles (name mention → recency).
    - TN companies get TN-region articles ranked first across both pools.
    """
    from sqlalchemy import case, or_, and_

    # Keywords that mark a "deep topic" article (ERP / org problems / mechanical)
    TOPIC_KEYWORDS = [
        "%erp%", "%management system%", "%fleet management%", "%leasing software%",
        "%organizational%", "%organisational%", "%managerial%", "%operational failure%",
        "%digital transformation%", "%process automation%", "%system integration%",
        "%engine%", "%mechanical%", "%recall%", "%defect%", "%breakdown%",
        "%transmission%", "%powertrain%", "%gearbox%", "%motor failure%",
    ]

    def _topic_filter():
        return or_(
            *[MarketTrendArticle.title.ilike(kw) for kw in TOPIC_KEYWORDS],
            *[func.coalesce(MarketTrendArticle.body_text, "").ilike(kw) for kw in TOPIC_KEYWORDS[:10]],
        )

    with get_db_session() as session:
        entity_name: Optional[str] = None
        entity_region: Optional[str] = None

        if company_type == "car":
            entity = session.get(CarBrand, company_id)
            if not entity:
                raise HTTPException(status_code=404, detail="Car brand not found")
            entity_name = entity.name
            entity_region = entity.region
            category_filter = MarketTrendArticle.category.in_(
                ["automotive", "EV", "ERP", "InsurTech", "Keyword Search", "Technology", "Regulation", "Market"]
            )
        elif company_type == "insurance":
            entity = session.get(InsuranceCompany, company_id)
            if not entity:
                raise HTTPException(status_code=404, detail="Insurance company not found")
            entity_name = entity.name
            entity_region = getattr(entity, "region", None)
            category_filter = MarketTrendArticle.category.in_(
                ["insurance", "Insurance", "ERP", "InsurTech", "business", "Technology", "Market"]
            )
        else:
            raise HTTPException(status_code=400, detail="company_type must be 'car' or 'insurance'")

        base_q = (
            session.query(MarketTrendArticle, ReviewSource.name.label("source_name"))
            .outerjoin(ReviewSource, MarketTrendArticle.source_id == ReviewSource.id)
            .filter(MarketTrendArticle.data_origin == "scraped")
        )

        is_tn_company = entity_region in ("TN", "tn") if entity_region else False
        tn_priority = case((MarketTrendArticle.region == "TN", 0), else_=1)

        # ── PASS 1: semantic topic search (RAG) ───────────────────────────────
        # Finds ERP/management/mechanical articles that are ALSO relevant to
        # this specific brand or sector — prevents generic ERP articles from
        # flooding slots for brands they have nothing to do with.
        topic_rows = []
        try:
            import numpy as np
            from sqlalchemy import text as _t

            # Sector categories that are legitimate for this entity type
            if company_type == "car":
                _sector_cats = {
                    "automotive", "EV", "ERP", "InsurTech", "Technology",
                    "Regulation", "Market", "Keyword Search",
                }
                topic_query_text = (
                    f"{entity_name} automotive fleet ERP management system "
                    f"engine recall defect breakdown digital transformation"
                )
            else:
                _sector_cats = {
                    "insurance", "Insurance", "ERP", "InsurTech",
                    "business", "Technology", "Market",
                }
                topic_query_text = (
                    f"{entity_name} insurance claims ERP management system "
                    f"operational difficulties digital transformation"
                )

            topic_emb = _embed_query(topic_query_text)
            q_vec = np.array(topic_emb, dtype=np.float32)
            brand_lower = entity_name.lower()

            # Fetch scraped articles with embeddings + category + title snippet
            fetch_sql = _t("""
                SELECT id::text AS id, embedding,
                       CASE WHEN region = 'TN' THEN 0 ELSE 1 END AS tn_rank,
                       category,
                       lower(coalesce(title,'')) AS title_lc,
                       lower(left(coalesce(body_text,''), 400)) AS body_lc
                FROM market_trend_articles
                WHERE embedding IS NOT NULL AND data_origin = 'scraped'
            """)
            cand_rows = session.execute(fetch_sql).fetchall()
            if cand_rows:
                scored = []
                for cr in cand_rows:
                    # Only consider articles in this entity's sector OR
                    # that explicitly mention the brand name
                    in_sector = (cr.category or "") in _sector_cats
                    brand_hit = brand_lower in cr.title_lc or brand_lower in cr.body_lc
                    if not (in_sector or brand_hit):
                        continue
                    emb_vec = np.array(cr.embedding, dtype=np.float32)
                    sim = float(q_vec @ emb_vec)
                    scored.append((cr.id, sim, cr.tn_rank))

                if is_tn_company:
                    scored.sort(key=lambda x: (x[2], -x[1]))
                else:
                    scored.sort(key=lambda x: -x[1])

                top_ids = [s[0] for s in scored[:4]]
                if top_ids:
                    id_to_row = {
                        str(art.id): (art, sn)
                        for art, sn in (
                            base_q
                            .filter(MarketTrendArticle.id.in_(
                                [UUID(i) for i in top_ids]
                            ))
                            .all()
                        )
                    }
                    topic_rows = [
                        id_to_row[sid] for sid in top_ids if sid in id_to_row
                    ][:2]
        except Exception:
            pass

        # Fallback: ILIKE keyword matching if RAG returned nothing
        if not topic_rows:
            topic_q = base_q.filter(_topic_filter())
            if is_tn_company:
                topic_rows = (
                    topic_q
                    .order_by(tn_priority, MarketTrendArticle.publication_date.desc().nullslast())
                    .limit(2)
                    .all()
                )
            else:
                topic_rows = (
                    topic_q
                    .order_by(MarketTrendArticle.publication_date.desc().nullslast())
                    .limit(2)
                    .all()
                )

        topic_ids = {art.id for art, _ in topic_rows}
        topic_slots_filled = len(topic_rows)  # may be 0-2
        remaining = limit - topic_slots_filled

        # ── PASS 2: general brand/sector articles (excluding already selected) ─
        general_q = base_q.filter(
            category_filter,
            ~MarketTrendArticle.id.in_(topic_ids) if topic_ids else True,
        )
        if entity_name:
            name_match = case(
                (MarketTrendArticle.title.ilike(f"%{entity_name}%"), 0),
                else_=1,
            )
            if is_tn_company:
                general_rows = (
                    general_q
                    .order_by(name_match, tn_priority, MarketTrendArticle.publication_date.desc().nullslast())
                    .limit(remaining)
                    .all()
                )
            else:
                general_rows = (
                    general_q
                    .order_by(name_match, MarketTrendArticle.publication_date.desc().nullslast())
                    .limit(remaining)
                    .all()
                )
        else:
            general_rows = (
                general_q
                .order_by(MarketTrendArticle.publication_date.desc().nullslast())
                .limit(remaining)
                .all()
            )

        # Topic articles first (signals), then general
        all_rows = list(topic_rows) + list(general_rows)

        return [
            CompanyNewsItem(
                id=art.id,
                title=art.title,
                source_url=art.source_url,
                publication_date=art.publication_date.isoformat() if art.publication_date else None,
                category=art.category,
                region=art.region,
                source_name=source_name,
            )
            for art, source_name in all_rows
        ]


# ---------------------------------------------------------------------------
# ML Dimensions endpoint — scoring breakdown for visualization
# ---------------------------------------------------------------------------

class MLArticlePoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    title: str
    similarity: float
    pub_date: Optional[str]
    category: Optional[str]
    days_old: int
    recency_weight: float


class MLTrendPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    period: str
    avg_sentiment: Optional[float]
    review_count: int
    neg_pct: Optional[float]
    regression_predicted: Optional[float]
    poly_predicted: Optional[float]


class MLSectorPeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    value: float
    is_current: bool


class MLDimensionsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    entity_name: str
    entity_type: str
    total_score: float
    article_score: float
    article_max: int
    article_percentile: float
    article_count: int
    top_articles: List[MLArticlePoint]
    trend_score: float
    trend_max: int
    trend_slope: float
    trend_r_squared: float
    trend_direction: str
    trend_percentile: float
    trend_series: List[MLTrendPoint]
    trend_method: str
    mk_trend: Optional[str]
    mk_p_value: Optional[float]
    mk_significant: bool
    poly_acceleration: float
    poly_concavity: str
    trend_min_reviews: int
    trend_months_filtered: int
    trend_clean_r_squared: float
    presence_score: float
    presence_max: int
    review_count: int
    presence_percentile: float
    sector_presence_peers: List[MLSectorPeer]
    intensity_score: float
    intensity_max: int
    negative_pct: float
    intensity_percentile: float
    sector_avg_negative_pct: float
    sector_intensity_peers: List[MLSectorPeer]


@app.get(
    "/api/company/{company_type}/{company_id}/ml-dimensions",
    response_model=MLDimensionsOut,
    tags=["company-radar"],
    summary="ML scoring dimension breakdown for visualization",
)
def company_ml_dimensions(company_type: str, company_id: UUID):
    """Return all 4 ML scoring dimensions with full data for chart rendering."""
    entity_type_db = "insurance" if company_type == "insurance" else "brand"

    with get_db_session() as session:
        signal = (
            session.query(OpportunitySignal)
            .filter_by(entity_type=entity_type_db, entity_id=company_id)
            .first()
        )
        if not signal:
            raise HTTPException(
                status_code=404,
                detail="No ML score found. Trigger /api/opportunities/recompute first.",
            )

        r = signal.score_reasoning or {}
        art  = r.get("article_signal", {})
        trnd = r.get("trend", {})
        pres = r.get("market_presence", {})
        intn = r.get("complaint_intensity", {})

        # Sector peers for distribution charts
        peers = (
            session.query(OpportunitySignal)
            .filter(OpportunitySignal.entity_type == entity_type_db)
            .all()
        )

        def _peer_review_count(p):
            return float((p.score_reasoning or {}).get("market_presence", {}).get("review_count", 0))

        def _peer_neg_pct(p):
            return float((p.score_reasoning or {}).get("complaint_intensity", {}).get("negative_pct", 0))

        presence_peers = sorted(
            [MLSectorPeer(name=p.entity_name, value=_peer_review_count(p), is_current=str(p.entity_id) == str(company_id)) for p in peers],
            key=lambda x: x.value, reverse=True,
        )[:15]

        intensity_peers = sorted(
            [MLSectorPeer(name=p.entity_name, value=_peer_neg_pct(p), is_current=str(p.entity_id) == str(company_id)) for p in peers],
            key=lambda x: x.value, reverse=True,
        )[:15]

        return MLDimensionsOut(
            entity_name=signal.entity_name,
            entity_type=entity_type_db,
            total_score=float(signal.overall_score),
            article_score=float(art.get("score", 0)),
            article_max=35,
            article_percentile=float(art.get("percentile", 0)),
            article_count=int(art.get("article_count", 0)),
            top_articles=[MLArticlePoint(**a) for a in art.get("top_articles", [])],
            trend_score=float(trnd.get("score", 0)),
            trend_max=25,
            trend_slope=float(trnd.get("slope", 0)),
            trend_r_squared=float(trnd.get("r_squared", 0)),
            trend_direction=str(trnd.get("direction", "unknown")),
            trend_percentile=float(trnd.get("percentile", 50)),
            trend_series=[MLTrendPoint(**{k: p.get(k) for k in MLTrendPoint.model_fields}) for p in trnd.get("time_series", [])],
            trend_method=str(trnd.get("method_used", "linear")),
            mk_trend=trnd.get("mk_trend"),
            mk_p_value=trnd.get("mk_p_value"),
            mk_significant=bool(trnd.get("mk_significant", False)),
            poly_acceleration=float(trnd.get("poly_acceleration", 0.0)),
            poly_concavity=str(trnd.get("poly_concavity", "linear")),
            trend_min_reviews=int(trnd.get("min_reviews_threshold", 3)),
            trend_months_filtered=int(trnd.get("months_filtered", 0)),
            trend_clean_r_squared=float(trnd.get("clean_r_squared", trnd.get("r_squared", 0.0))),
            presence_score=float(pres.get("score", 0)),
            presence_max=20,
            review_count=int(pres.get("review_count", 0)),
            presence_percentile=float(pres.get("percentile", 0)),
            sector_presence_peers=presence_peers,
            intensity_score=float(intn.get("score", 0)),
            intensity_max=20,
            negative_pct=float(intn.get("negative_pct", 0)),
            intensity_percentile=float(intn.get("percentile", 0)),
            sector_avg_negative_pct=float(intn.get("sector_avg_negative_pct", 0)),
            sector_intensity_peers=intensity_peers,
        )


# ---------------------------------------------------------------------------
# Article summary endpoint (Groq-powered storytelling summary)
# ---------------------------------------------------------------------------

class ArticleSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    article_id: str
    title: str
    summary: str
    source_url: str
    publication_date: Optional[str]
    source_name: Optional[str]


@app.get(
    "/api/article/{article_id}/summary",
    response_model=ArticleSummaryOut,
    tags=["company-radar"],
    summary="Generate a storytelling summary of a news article using Groq",
)
def article_summary(article_id: UUID):
    groq_key = os.environ.get("GROQ_API_KEY", "")
    if not groq_key:
        raise HTTPException(status_code=503, detail="GROQ_API_KEY not configured.")

    with get_db_session() as session:
        row = (
            session.query(MarketTrendArticle, ReviewSource.name.label("source_name"))
            .outerjoin(ReviewSource, MarketTrendArticle.source_id == ReviewSource.id)
            .filter(MarketTrendArticle.id == article_id)
            .first()
        )
        if not row:
            raise HTTPException(status_code=404, detail="Article not found")

        art, source_name = row
        content = _safe_str((art.body_text or "").strip())
        title_safe = _safe_str(art.title or "")

        if content:
            prompt_body = f"Article title: {title_safe}\n\nFull article content:\n{content[:4000]}"
        else:
            prompt_body = f"Article title: {title_safe}"

        # RAG: retrieve real customer reviews that corroborate or challenge this article's topic.
        # This grounds the hook sentence and sales angle in actual customer language.
        customer_voice_section = ""
        try:
            rag_query = f"{art.title} {(art.body_text or '')[:200]}"
            rag_hits = _rag_retrieve(
                query=rag_query,
                session=session,
                corpus="car_reviews",
                top_k=3,
                pool=15,
            )
            if rag_hits:
                voices = []
                for hit in rag_hits:
                    meta = hit.get("metadata", {})
                    rating_str = f"{meta['rating']}★" if meta.get("rating") else ""
                    brand_str = f"{meta.get('brand','')} {meta.get('model','')}".strip()
                    label = f"{brand_str} {rating_str}".strip()
                    voices.append(f'- "{hit["text"][:220]}" [{label}]')
                customer_voice_section = (
                    "\n\nCUSTOMER VOICE — real reviews semantically matched to this article's topic "
                    "(use these to make the hook and sales angle more concrete):\n"
                    + "\n".join(voices)
                )
        except Exception:
            pass  # additive; article body alone is still valid input

    system_prompt = (
        "You are a market intelligence writer for TEAMWILL, a B2B company selling ERP and leasing software "
        "to car insurers and dealerships in Tunisia and Europe. "
        "Your audience is a sales executive about to cold-call an insurance company or car dealer.\n\n"
        "YOUR JOB: Reframe ANY article through the lens of: what does this mean for car insurance premiums, "
        "vehicle sales, ERP adoption, or the operational health of insurers and dealerships?\n\n"
        "OUTPUT FORMAT — follow this EXACT structure, no deviations:\n\n"
        "Line 1 — HOOK: One punchy sentence that grabs the sales exec's attention. "
        "Frame a risk, opportunity, or tension. Be specific and bold. "
        "Use **double asterisks** around the key term. "
        "Example: \u2018**ERP failures** in the insurance sector just hit a 5‑year high — is your prospect next?\u2019\n"
        "Line 2 — Exactly the literal text: ---\n"
        "Line 3 — Bullet with emoji \U0001F4CA: The single most striking FACT or number from the article. Bold the key figure.\n"
        "Line 4 — Bullet with emoji \U0001F50D: The CONTEXT — why this matters for car insurance or automotive sales. Bold 1-2 terms.\n"
        "Line 5 — Bullet with emoji \U0001F4A1: The SALES ANGLE — one concrete, quotable line the rep can say on a live call. Bold the pitch term.\n\n"
        "RULES:\n"
        "- Bold (**word**) the 4-6 most impactful terms across all lines: brand names, metrics, issue types, geographies.\n"
        "- Never use generic openers like 'In today\'s market' or 'It is important'.\n"
        "- Use exact numbers, company names, countries from the article. No vague claims.\n"
        "- No extra lines, no headers, no markdown except **bold** and the --- separator."
    )

    user_message = _safe_str(
        f"{prompt_body}"
        f"{customer_voice_section}\n\n"
        "Write the structured brief: hook line, then ---, then 3 emoji bullet points. "
        "Bold the key figures and terms. Be sharp and specific."
    )

    client = Groq(api_key=groq_key)
    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": _safe_str(system_prompt)},
            {"role": "user", "content": user_message},
        ],
        max_tokens=450,
        temperature=0.5,   # balanced nucleus: abstractive summarization, faithful + fluent
        top_p=0.90,        # nucleus sampling — Holtzman et al. (2020)
    )
    summary_text = completion.choices[0].message.content.strip()

    return ArticleSummaryOut(
        article_id=str(art.id),
        title=art.title,
        summary=summary_text,
        source_url=art.source_url,
        publication_date=art.publication_date.isoformat() if art.publication_date else None,
        source_name=source_name,
    )


# ---------------------------------------------------------------------------
# ML Clustering endpoints
# ---------------------------------------------------------------------------

class ClusterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    cluster_id: int
    cluster_label: str
    erp_module: str
    description: Optional[str]
    color_hex: str
    company_count: int
    avg_negative_pct: Optional[float]
    avg_review_count: Optional[float]


class ClusteredCompanyOut(BaseModel):
    company_id: UUID
    company_name: str
    sector: str
    region: Optional[str]
    cluster_id: int
    cluster_label: str
    erp_module: str
    color_hex: Optional[str] = None


class MlMetricsOut(BaseModel):
    model_name: str
    silhouette_score: Optional[float]
    davies_bouldin_score: Optional[float]
    inertia: Optional[float]
    k_value: int
    n_companies: int
    quality_grade: str
    cluster_stability_json: Optional[Dict[str, Any]]
    created_at: datetime


@app.get(
    "/api/ml/clusters",
    response_model=List[ClusterOut],
    tags=["ml"],
    summary="Get all ML cluster metadata",
)
def list_ml_clusters():
    with get_db_session() as session:
        rows = (
            session.query(MlClusterMetadata)
            .order_by(MlClusterMetadata.cluster_id)
            .all()
        )
        return [ClusterOut.model_validate(r) for r in rows]


@app.get(
    "/api/ml/companies",
    response_model=List[ClusteredCompanyOut],
    tags=["ml"],
    summary="Get all companies with their cluster assignment",
)
def list_ml_companies():
    results: List[ClusteredCompanyOut] = []
    with get_db_session() as session:
        # Build a lookup from cluster_id → color_hex
        meta_rows = session.query(MlClusterMetadata).all()
        color_map = {m.cluster_id: m.color_hex for m in meta_rows}

        # Car brands with cluster
        brands = (
            session.query(CarBrand)
            .filter(CarBrand.cluster_id.isnot(None))
            .all()
        )
        for b in brands:
            results.append(ClusteredCompanyOut(
                company_id=b.id,
                company_name=b.name,
                sector="automotive",
                region=b.region,
                cluster_id=b.cluster_id,
                cluster_label=b.cluster_label or "",
                erp_module=b.erp_module or "",
                color_hex=color_map.get(b.cluster_id),
            ))

        # Insurance companies with cluster
        companies = (
            session.query(InsuranceCompany)
            .filter(InsuranceCompany.cluster_id.isnot(None))
            .all()
        )
        for c in companies:
            results.append(ClusteredCompanyOut(
                company_id=c.id,
                company_name=c.name,
                sector="insurance",
                region=c.region,
                cluster_id=c.cluster_id,
                cluster_label=c.cluster_label or "",
                erp_module=c.erp_module or "",
                color_hex=color_map.get(c.cluster_id),
            ))

    return results


@app.get(
    "/api/ml/metrics",
    response_model=MlMetricsOut,
    tags=["ml"],
    summary="Get the latest ML clustering metrics",
)
def get_ml_metrics():
    with get_db_session() as session:
        metric = (
            session.query(MlModelMetric)
            .order_by(MlModelMetric.created_at.desc())
            .first()
        )
        
        if not metric:
            raise HTTPException(status_code=404, detail="No ML metrics found")
            
        sil_score = float(metric.silhouette_score) if metric.silhouette_score else 0.0
        
        # Calculate quality grade based on silhouette score
        if sil_score >= 0.7:
            grade = "A"
        elif sil_score >= 0.5:
            grade = "B+"
        elif sil_score >= 0.3:
            grade = "B"
        else:
            grade = "C"
            
        return MlMetricsOut(
            model_name=metric.model_name,
            silhouette_score=sil_score,
            davies_bouldin_score=float(metric.davies_bouldin_score) if metric.davies_bouldin_score else None,
            inertia=float(metric.inertia) if metric.inertia else None,
            k_value=metric.k_value,
            n_companies=metric.n_companies,
            quality_grade=grade,
            cluster_stability_json=metric.cluster_stability_json,
            created_at=metric.created_at
        )


# ---------------------------------------------------------------------------
# ERP Vendor Intelligence
# ---------------------------------------------------------------------------

class ErpVendorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    product_name: str
    target_sector: str
    target_region: str
    website: Optional[str] = None
    notes: Optional[str] = None
    data_origin: str
    created_at: datetime


@app.get(
    "/api/erp-vendors",
    response_model=List[ErpVendorOut],
    tags=["erp"],
    summary="List ERP vendors in insurance/automotive markets",
)
def list_erp_vendors(
    sector: Optional[str] = Query(None, description="Filter by target_sector: insurance, automotive, both"),
    region: Optional[str] = Query(None, description="Filter by target_region: TN, EU, MENA, global"),
):
    from database.models import ErpVendor
    with get_db_session() as session:
        q = session.query(ErpVendor)
        if sector:
            q = q.filter(ErpVendor.target_sector == sector)
        if region:
            q = q.filter(ErpVendor.target_region == region)
        vendors = q.order_by(ErpVendor.name).all()
        return [ErpVendorOut.model_validate(v) for v in vendors]


# ===========================================================================
# Company Radar — unified search + full company profiles
# ===========================================================================

class CompanySearchResult(BaseModel):
    id: UUID
    name: str
    type: str              # "car" or "insurance"
    sector: str            # "Automotive" or "Insurance"
    region: Optional[str]
    score: Optional[float]
    data_origin: Optional[str]


class ComplaintItem(BaseModel):
    label: str
    count: int
    pct: float


class SentimentMonth(BaseModel):
    month: str
    negative_pct: float
    avg_rating: Optional[float]


class RealQuote(BaseModel):
    text: str
    rating: Optional[float]
    date: Optional[str]
    sentiment: str


class ScoringBreakdown(BaseModel):
    article_signal: float
    sentiment_trend: float
    market_presence: float
    complaint_intensity: float


class CompanyProfile(BaseModel):
    id: UUID
    name: str
    type: str
    sector: str
    region: Optional[str]
    country: Optional[str]
    score: Optional[float]
    score_percentile: Optional[int]
    data_origin: Optional[str]
    cluster_id: Optional[int]
    cluster_label: Optional[str]
    cluster_color: Optional[str]
    erp_module_primary: Optional[str]
    erp_module_secondary: Optional[str]
    prospect_type: str
    review_count: int
    negative_pct: float
    avg_rating: Optional[float]
    top_complaints: List[ComplaintItem]
    sentiment_trend: List[SentimentMonth]
    real_quotes: List[RealQuote]
    why_now: str
    scoring_breakdown: Optional[ScoringBreakdown]
    data_note: Optional[str] = None


# ---------------------------------------------------------------------------
# GET /api/search/companies — unified autocomplete
# ---------------------------------------------------------------------------

@app.get(
    "/api/search/companies",
    response_model=List[CompanySearchResult],
    tags=["company-radar"],
    summary="Unified company search across car brands and insurance companies",
)
def search_companies(q: str = Query("", description="Search query (min 2 chars)")):
    """Search both car_brands and insurance_companies by name (ILIKE). Returns max 10 results sorted by opportunity score desc."""
    if len(q.strip()) < 2:
        return []

    pattern = f"%{q.strip()}%"

    with get_db_session() as session:
        results: List[CompanySearchResult] = []

        # Car brands
        car_brands = (
            session.query(CarBrand)
            .filter(CarBrand.name.ilike(pattern), CarBrand.is_active.is_(True))
            .all()
        )
        for b in car_brands:
            signal = (
                session.query(OpportunitySignal)
                .filter(OpportunitySignal.entity_id == b.id)
                .first()
            )
            results.append(CompanySearchResult(
                id=b.id,
                name=b.name,
                type="car",
                sector="Automotive",
                region=b.region,
                score=float(signal.overall_score) if signal else None,
                data_origin=signal.score_reasoning.get("data_origin") if signal and signal.score_reasoning else None,
            ))

        # Insurance companies
        ins_companies = (
            session.query(InsuranceCompany)
            .filter(InsuranceCompany.name.ilike(pattern), InsuranceCompany.is_active.is_(True))
            .all()
        )
        for c in ins_companies:
            signal = (
                session.query(OpportunitySignal)
                .filter(OpportunitySignal.entity_id == c.id)
                .first()
            )
            results.append(CompanySearchResult(
                id=c.id,
                name=c.name,
                type="insurance",
                sector="Insurance",
                region=c.region,
                score=float(signal.overall_score) if signal else None,
                data_origin=signal.score_reasoning.get("data_origin") if signal and signal.score_reasoning else None,
            ))

        # Sort by score desc (None last)
        results.sort(key=lambda r: r.score if r.score is not None else -1, reverse=True)
        return results[:10]


# ---------------------------------------------------------------------------
# Helpers for company profile building
# ---------------------------------------------------------------------------

def _get_cluster_color(cluster_id: Optional[int], session) -> Optional[str]:
    """Look up cluster color from ml_cluster_metadata."""
    if cluster_id is None:
        return None
    meta = (
        session.query(MlClusterMetadata)
        .filter(MlClusterMetadata.cluster_id == cluster_id)
        .first()
    )
    return meta.color_hex if meta else None


def _derive_prospect_type(avg_rating: Optional[float], negative_pct: float, cluster_id: Optional[int], top_complaints: List[ComplaintItem]) -> str:
    """Derive prospect type from complaint patterns, cluster, and rating."""
    complaint_labels = [c.label.lower() for c in top_complaints]
    has_process_complaints = any(
        kw in label for label in complaint_labels
        for kw in ["billing", "process", "data", "pricing", "policy"]
    )

    if avg_rating is not None and avg_rating < 2.5 and negative_pct > 60:
        return "ERP_FAILING"
    if cluster_id == 0:  # Critical Service Failures
        return "ERP_FAILING"
    if has_process_complaints:
        return "NO_ERP"
    if cluster_id == 2:  # Emerging Market Entrants
        return "NO_ERP"
    return "OPERATIONAL_GAPS"


def _compute_why_now(negative_pct: float, trend_months: List[SentimentMonth], cluster_id: Optional[int]) -> str:
    """Compute the why-now narrative from data."""
    prefix = "Critical service failures detected. " if cluster_id == 0 else ""

    # Compare last 2 months vs previous 2 months
    if len(trend_months) >= 4:
        recent = trend_months[:2]  # most recent
        prior = trend_months[2:4]
        recent_avg = sum(m.negative_pct for m in recent) / len(recent)
        prior_avg = sum(m.negative_pct for m in prior) / len(prior)
        if recent_avg > prior_avg and prior_avg > 0:
            change_pct = round((recent_avg - prior_avg) / prior_avg * 100)
            return f"{prefix}Complaint volume rising {change_pct}% over last 60 days. Declining customer satisfaction signals urgent operational gaps."

    if negative_pct > 65:
        return f"{prefix}Sustained high complaint rate ({negative_pct:.0f}% negative reviews). Company shows no signs of self-correction."

    if negative_pct > 40:
        return f"{prefix}Elevated complaint rate at {negative_pct:.0f}% negative. Operational gaps becoming visible to customers."

    return f"{prefix}Company showing early warning signals. Proactive engagement recommended before complaints escalate."


def _compute_scoring_breakdown(signal: Optional[Any]) -> Optional[ScoringBreakdown]:
    """Extract scoring breakdown from opportunity signal score_reasoning JSONB."""
    if not signal or not signal.score_reasoning:
        return None
    r = signal.score_reasoning
    return ScoringBreakdown(
        article_signal=r.get("article_signal", {}).get("score", r.get("teamwill_fit", {}).get("score", 0)),
        sentiment_trend=r.get("trend", {}).get("score", 0),
        market_presence=r.get("market_presence", {}).get("score", 0),
        complaint_intensity=r.get("complaint_intensity", {}).get("score", 0),
    )


# ---------------------------------------------------------------------------
# GET /api/company/car/{brand_id} — full car brand profile
# ---------------------------------------------------------------------------

@app.get(
    "/api/company/car/{brand_id}",
    response_model=CompanyProfile,
    tags=["company-radar"],
    summary="Full car brand profile for Company Radar",
)
def car_brand_profile(brand_id: UUID):
    """Complete pre-call sales intelligence dossier for a car brand."""
    from database.enums import SentimentLabel
    from database.models import Topic, ComplaintType

    with get_db_session() as session:
        brand = session.get(CarBrand, brand_id)
        if not brand:
            raise HTTPException(status_code=404, detail="Car brand not found")

        # Get all reviews for this brand via car_models
        model_ids = [m.id for m in session.query(CarModel.id).filter(CarModel.brand_id == brand_id).all()]

        review_count = 0
        neg_count = 0
        total_nlp = 0
        all_ratings: List[float] = []

        if model_ids:
            review_count = (
                session.query(func.count(CarReview.id))
                .filter(CarReview.model_id.in_(model_ids))
                .scalar()
            ) or 0

            avg_rat = (
                session.query(func.avg(CarReview.rating))
                .filter(CarReview.model_id.in_(model_ids), CarReview.rating.isnot(None))
                .scalar()
            )
            avg_rating = round(float(avg_rat), 2) if avg_rat else None

            # NLP sentiment counts
            pos = (
                session.query(func.count(CarReviewNlp.id))
                .join(CarReview, CarReviewNlp.review_id == CarReview.id)
                .filter(CarReview.model_id.in_(model_ids),
                        CarReviewNlp.sentiment_label == SentimentLabel.POSITIVE)
                .scalar()
            ) or 0
            neu = (
                session.query(func.count(CarReviewNlp.id))
                .join(CarReview, CarReviewNlp.review_id == CarReview.id)
                .filter(CarReview.model_id.in_(model_ids),
                        CarReviewNlp.sentiment_label == SentimentLabel.NEUTRAL)
                .scalar()
            ) or 0
            neg_count = (
                session.query(func.count(CarReviewNlp.id))
                .join(CarReview, CarReviewNlp.review_id == CarReview.id)
                .filter(CarReview.model_id.in_(model_ids),
                        CarReviewNlp.sentiment_label == SentimentLabel.NEGATIVE)
                .scalar()
            ) or 0
            total_nlp = pos + neu + neg_count
        else:
            avg_rating = None

        negative_pct = round(neg_count / total_nlp * 100, 1) if total_nlp > 0 else 0.0

        # Top complaints by topic
        top_complaints: List[ComplaintItem] = []
        if model_ids and total_nlp > 0:
            topic_counts = (
                session.query(Topic.topic_label, func.count(CarReviewNlp.id).label("cnt"))
                .join(CarReviewNlp, CarReviewNlp.topic_id == Topic.id)
                .join(CarReview, CarReviewNlp.review_id == CarReview.id)
                .filter(
                    CarReview.model_id.in_(model_ids),
                    CarReviewNlp.sentiment_label == SentimentLabel.NEGATIVE,
                )
                .group_by(Topic.topic_label)
                .order_by(func.count(CarReviewNlp.id).desc())
                .limit(5)
                .all()
            )
            for label, cnt in topic_counts:
                top_complaints.append(ComplaintItem(
                    label=label.replace("_", " ").title() if label else "General",
                    count=cnt,
                    pct=round(cnt / neg_count * 100, 1) if neg_count > 0 else 0.0,
                ))

        # Sentiment trend — monthly from brand_reputation_scores
        trend_rows = (
            session.query(BrandReputationScore)
            .filter(BrandReputationScore.brand_id == brand_id,
                    BrandReputationScore.data_origin == "scraped")
            .order_by(BrandReputationScore.period_date.desc())
            .limit(6)
            .all()
        )
        sentiment_trend: List[SentimentMonth] = []
        for tr in trend_rows:
            # Compute negative_pct for this period from sentiment_trends if available
            st = (
                session.query(SentimentTrend)
                .filter(SentimentTrend.brand_id == brand_id,
                        SentimentTrend.period_date == tr.period_date,
                        SentimentTrend.data_origin == "scraped")
                .first()
            )
            if st:
                total_st = st.positive_count + st.neutral_count + st.negative_count
                neg_pct_month = round(st.negative_count / total_st * 100, 1) if total_st > 0 else 0.0
            else:
                neg_pct_month = 0.0
            sentiment_trend.append(SentimentMonth(
                month=tr.period_date.strftime("%Y-%m"),
                negative_pct=neg_pct_month,
                avg_rating=round(float(tr.avg_rating), 2) if tr.avg_rating else None,
            ))

        # Real quotes — 3 most negative reviews
        real_quotes: List[RealQuote] = []
        if model_ids:
            neg_reviews = (
                session.query(CarReview)
                .join(CarReviewNlp, CarReviewNlp.review_id == CarReview.id)
                .filter(
                    CarReview.model_id.in_(model_ids),
                    CarReviewNlp.sentiment_label == SentimentLabel.NEGATIVE,
                    func.length(CarReview.review_text) > 80,
                )
                .order_by(CarReview.rating.asc().nullslast(), CarReview.review_date.desc().nullslast())
                .limit(3)
                .all()
            )
            for rev in neg_reviews:
                real_quotes.append(RealQuote(
                    text=rev.review_text[:300] if rev.review_text else "",
                    rating=float(rev.rating) if rev.rating else None,
                    date=rev.review_date.strftime("%Y-%m-%d") if rev.review_date else None,
                    sentiment="NEGATIVE",
                ))

        # Opportunity signal
        signal = (
            session.query(OpportunitySignal)
            .filter(OpportunitySignal.entity_id == brand_id)
            .first()
        )
        score = float(signal.overall_score) if signal else None
        percentile = signal.sector_percentile if signal else None
        data_origin = signal.score_reasoning.get("data_origin") if signal and signal.score_reasoning else None

        # Cluster info
        cluster_color = _get_cluster_color(brand.cluster_id, session)
        prospect_type = _derive_prospect_type(avg_rating, negative_pct, brand.cluster_id, top_complaints)
        why_now = _compute_why_now(negative_pct, sentiment_trend, brand.cluster_id)
        scoring = _compute_scoring_breakdown(signal)

        # ERP module
        erp_primary = brand.erp_module
        if signal and signal.score_reasoning:
            erp_primary = signal.score_reasoning.get("erp_module_recommendation") or erp_primary
        erp_secondary = "Integrated ERP Suite" if erp_primary != "Integrated ERP Suite" else "Advanced Analytics & Reporting"

        return CompanyProfile(
            id=brand.id,
            name=brand.name,
            type="car",
            sector="Automotive",
            region=brand.region,
            country=brand.country_of_origin,
            score=score,
            score_percentile=percentile,
            data_origin=data_origin,
            cluster_id=brand.cluster_id,
            cluster_label=brand.cluster_label,
            cluster_color=cluster_color,
            erp_module_primary=erp_primary or "Customer Service Management",
            erp_module_secondary=erp_secondary,
            prospect_type=prospect_type,
            review_count=review_count,
            negative_pct=negative_pct,
            avg_rating=avg_rating,
            top_complaints=top_complaints,
            sentiment_trend=sentiment_trend,
            real_quotes=real_quotes,
            why_now=why_now,
            scoring_breakdown=scoring,
        )


# ---------------------------------------------------------------------------
# GET /api/company/insurance/{company_id} — full insurance company profile
# ---------------------------------------------------------------------------

@app.get(
    "/api/company/insurance/{company_id}",
    response_model=CompanyProfile,
    tags=["company-radar"],
    summary="Full insurance company profile for Company Radar",
)
def insurance_company_profile(company_id: UUID):
    """Complete pre-call sales intelligence dossier for an insurance company."""
    from database.enums import SentimentLabel
    from database.models import Topic

    with get_db_session() as session:
        company = session.get(InsuranceCompany, company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Insurance company not found")

        # Reviews
        review_count = (
            session.query(func.count(InsuranceReview.id))
            .filter(InsuranceReview.company_id == company_id)
            .scalar()
        ) or 0

        avg_rat = (
            session.query(func.avg(InsuranceReview.rating))
            .filter(InsuranceReview.company_id == company_id,
                    InsuranceReview.rating.isnot(None))
            .scalar()
        )
        avg_rating = round(float(avg_rat), 2) if avg_rat else None

        # NLP sentiment
        pos = (
            session.query(func.count(InsuranceReviewNlp.id))
            .join(InsuranceReview, InsuranceReviewNlp.review_id == InsuranceReview.id)
            .filter(InsuranceReview.company_id == company_id,
                    InsuranceReviewNlp.sentiment_label == SentimentLabel.POSITIVE)
            .scalar()
        ) or 0
        neu = (
            session.query(func.count(InsuranceReviewNlp.id))
            .join(InsuranceReview, InsuranceReviewNlp.review_id == InsuranceReview.id)
            .filter(InsuranceReview.company_id == company_id,
                    InsuranceReviewNlp.sentiment_label == SentimentLabel.NEUTRAL)
            .scalar()
        ) or 0
        neg_count = (
            session.query(func.count(InsuranceReviewNlp.id))
            .join(InsuranceReview, InsuranceReviewNlp.review_id == InsuranceReview.id)
            .filter(InsuranceReview.company_id == company_id,
                    InsuranceReviewNlp.sentiment_label == SentimentLabel.NEGATIVE)
            .scalar()
        ) or 0
        total_nlp = pos + neu + neg_count
        negative_pct = round(neg_count / total_nlp * 100, 1) if total_nlp > 0 else 0.0

        # Top complaints by topic
        top_complaints: List[ComplaintItem] = []
        if total_nlp > 0:
            topic_counts = (
                session.query(Topic.topic_label, func.count(InsuranceReviewNlp.id).label("cnt"))
                .join(InsuranceReviewNlp, InsuranceReviewNlp.topic_id == Topic.id)
                .join(InsuranceReview, InsuranceReviewNlp.review_id == InsuranceReview.id)
                .filter(
                    InsuranceReview.company_id == company_id,
                    InsuranceReviewNlp.sentiment_label == SentimentLabel.NEGATIVE,
                )
                .group_by(Topic.topic_label)
                .order_by(func.count(InsuranceReviewNlp.id).desc())
                .limit(5)
                .all()
            )
            for label, cnt in topic_counts:
                top_complaints.append(ComplaintItem(
                    label=label.replace("_", " ").title() if label else "General",
                    count=cnt,
                    pct=round(cnt / neg_count * 100, 1) if neg_count > 0 else 0.0,
                ))

        # Sentiment trend — monthly from reviews directly (insurance has no brand_reputation_scores via brand_id)
        sentiment_trend: List[SentimentMonth] = []
        if review_count > 0:
            monthly = (
                session.query(
                    func.date_trunc("month", InsuranceReview.review_date).label("m"),
                    func.avg(InsuranceReview.rating).label("ar"),
                    func.count(InsuranceReview.id).label("total"),
                )
                .filter(InsuranceReview.company_id == company_id,
                        InsuranceReview.review_date.isnot(None))
                .group_by(func.date_trunc("month", InsuranceReview.review_date))
                .order_by(func.date_trunc("month", InsuranceReview.review_date).desc())
                .limit(6)
                .all()
            )
            for m_date, ar, total in monthly:
                # Count negatives in this month
                neg_m = (
                    session.query(func.count(InsuranceReviewNlp.id))
                    .join(InsuranceReview, InsuranceReviewNlp.review_id == InsuranceReview.id)
                    .filter(
                        InsuranceReview.company_id == company_id,
                        InsuranceReviewNlp.sentiment_label == SentimentLabel.NEGATIVE,
                        func.date_trunc("month", InsuranceReview.review_date) == m_date,
                    )
                    .scalar()
                ) or 0
                sentiment_trend.append(SentimentMonth(
                    month=m_date.strftime("%Y-%m") if m_date else "unknown",
                    negative_pct=round(neg_m / total * 100, 1) if total > 0 else 0.0,
                    avg_rating=round(float(ar), 2) if ar else None,
                ))

        # Real quotes
        real_quotes: List[RealQuote] = []
        if review_count > 0:
            neg_reviews = (
                session.query(InsuranceReview)
                .join(InsuranceReviewNlp, InsuranceReviewNlp.review_id == InsuranceReview.id)
                .filter(
                    InsuranceReview.company_id == company_id,
                    InsuranceReviewNlp.sentiment_label == SentimentLabel.NEGATIVE,
                    func.length(InsuranceReview.review_text) > 80,
                )
                .order_by(InsuranceReview.rating.asc().nullslast(), InsuranceReview.review_date.desc().nullslast())
                .limit(3)
                .all()
            )
            for rev in neg_reviews:
                real_quotes.append(RealQuote(
                    text=rev.review_text[:300] if rev.review_text else "",
                    rating=float(rev.rating) if rev.rating else None,
                    date=rev.review_date.strftime("%Y-%m-%d") if rev.review_date else None,
                    sentiment="NEGATIVE",
                ))

        # Opportunity signal
        signal = (
            session.query(OpportunitySignal)
            .filter(OpportunitySignal.entity_id == company_id)
            .first()
        )
        score = float(signal.overall_score) if signal else None
        percentile = signal.sector_percentile if signal else None
        sr = signal.score_reasoning if signal else None
        data_origin = sr.get("data_origin") if sr else None

        # Cluster
        cluster_color = _get_cluster_color(company.cluster_id, session)
        prospect_type = _derive_prospect_type(avg_rating, negative_pct, company.cluster_id, top_complaints)
        why_now = _compute_why_now(negative_pct, sentiment_trend, company.cluster_id)
        scoring = _compute_scoring_breakdown(signal)

        # ERP module
        erp_primary = company.erp_module
        if sr:
            erp_primary = sr.get("erp_module_recommendation") or erp_primary
        erp_secondary = "Integrated ERP Suite" if erp_primary != "Integrated ERP Suite" else "Claims Management System"

        # Data note for analyst-sourced TN companies
        data_note = None
        if data_origin == "analyst" or review_count == 0:
            data_note = "Intelligence based on market analysis. No Trustpilot data available for this company."

        return CompanyProfile(
            id=company.id,
            name=company.name,
            type="insurance",
            sector="Insurance",
            region=company.region,
            country=company.country,
            score=score,
            score_percentile=percentile,
            data_origin=data_origin,
            cluster_id=company.cluster_id,
            cluster_label=company.cluster_label,
            cluster_color=cluster_color,
            erp_module_primary=erp_primary or "Claims Management System",
            erp_module_secondary=erp_secondary,
            prospect_type=prospect_type,
            review_count=review_count,
            negative_pct=negative_pct,
            avg_rating=avg_rating,
            top_complaints=top_complaints,
            sentiment_trend=sentiment_trend,
            real_quotes=real_quotes,
            why_now=why_now,
            scoring_breakdown=scoring,
            data_note=data_note,
        )


# ── Narrative Briefing Endpoints ───────────────────────────────────────────

_BRIEFING_TEAMWILL_COUNTRIES = frozenset({
    "France", "Tunisia", "Morocco", "Spain", "United Kingdom",
    "Belgium", "Germany", "Portugal", "Singapore", "United States", "Italy",
})


class BriefingLeadOut(BaseModel):
    entity_id: str
    entity_name: str
    entity_type: str
    v2_overall_score: Optional[float] = None
    v2_tier: Optional[str] = None
    evidence_strength: Optional[str] = None
    sub_segment: Optional[str] = None
    parent_company: Optional[str] = None
    headquarters_country: Optional[str] = None
    teamwill_relationship: str
    latest_action_headline: Optional[str] = None
    latest_action_type: Optional[str] = None
    latest_action_date: Optional[str] = None
    latest_action_url: Optional[str] = None
    source_urls: List[str] = []
    is_fallback: bool = False
    fallback_reason: Optional[str] = None
    scorer_run_at: Optional[str] = None


class BriefingThemeEntity(BaseModel):
    entity_id: str
    entity_name: str
    entity_type: str
    v2_tier: Optional[str] = None


class BriefingThemeOut(BaseModel):
    theme_id: str
    title: str
    narrative: str
    entities: List[BriefingThemeEntity]
    source_urls: List[str] = []


class BriefingContrarianOut(BaseModel):
    entity_id: str
    entity_name: str
    entity_type: str
    v1_score: float
    v2_score: Optional[float] = None
    v2_tier: Optional[str] = None
    top_penalty: Optional[str] = None
    lock_in_vendor: Optional[str] = None
    has_data: bool = True


@app.get(
    "/api/briefing/lead",
    response_model=BriefingLeadOut,
    tags=["briefing"],
    summary="Lead entity for the narrative briefing page",
)
def briefing_lead():
    """Primary lead-story entity: engage-tier + high evidence + Sofico or recent leadership change."""
    with get_db_session() as session:
        is_fallback = False
        fallback_reason = None

        row = session.execute(text("""
            SELECT
                o.entity_id::text AS entity_id,
                o.entity_name,
                o.entity_type,
                o.v2_overall_score,
                o.v2_tier,
                o.v2_reasoning,
                o.v2_computed_at
            FROM opportunity_signals o
            LEFT JOIN company_tech_stack ts
                ON ts.entity_id = o.entity_id
               AND ts.vendor ILIKE '%sofico%'
            LEFT JOIN company_action_signals s
                ON s.entity_id = o.entity_id
               AND s.signal_type = 'leadership_change'
               AND s.signal_date >= NOW() - INTERVAL '90 days'
            WHERE o.v2_tier = 'engage'
              AND o.v2_reasoning IS NOT NULL
              AND (o.v2_reasoning->'data_quality'->>'evidence_strength' = 'high')
              AND (ts.entity_id IS NOT NULL OR s.entity_id IS NOT NULL)
            GROUP BY o.entity_id, o.entity_name, o.entity_type,
                     o.v2_overall_score, o.v2_tier, o.v2_reasoning, o.v2_computed_at
            ORDER BY o.v2_overall_score DESC NULLS LAST
            LIMIT 1
        """)).fetchone()

        if row is None:
            is_fallback = True
            fallback_reason = (
                "No entities currently meet the lead-story criteria "
                "(engage tier + high evidence + active leadership signal OR Sofico relationship). "
                "Showing highest-V2-score engage entity instead."
            )
            row = session.execute(text("""
                SELECT entity_id::text AS entity_id, entity_name, entity_type,
                       v2_overall_score, v2_tier, v2_reasoning, v2_computed_at
                FROM opportunity_signals
                WHERE v2_tier = 'engage' AND v2_overall_score IS NOT NULL
                ORDER BY v2_overall_score DESC NULLS LAST
                LIMIT 1
            """)).fetchone()

        if row is None:
            return BriefingLeadOut(
                entity_id="", entity_name="No data", entity_type="",
                teamwill_relationship="",
                is_fallback=True,
                fallback_reason="No engage-tier entities found in the database.",
            )

        eid = row.entity_id
        reasoning = row.v2_reasoning or {}
        evidence_strength = (reasoning.get("data_quality") or {}).get("evidence_strength")

        prof = session.execute(text("""
            SELECT sub_segment, parent_company, headquarters_country, source_urls
            FROM company_profile WHERE entity_id::text = :eid LIMIT 1
        """), {"eid": eid}).fetchone()

        sub_segment = prof.sub_segment if prof else None
        parent_company = prof.parent_company if prof else None
        hq_country = prof.headquarters_country if prof else None
        profile_sources: list = (prof.source_urls or []) if prof else []

        has_sofico = session.execute(text("""
            SELECT 1 FROM company_tech_stack
            WHERE entity_id::text = :eid AND vendor ILIKE '%sofico%' LIMIT 1
        """), {"eid": eid}).fetchone()

        if has_sofico:
            teamwill_rel = "TEAMWILL is a Sofico-certified partner"
        elif hq_country and hq_country in _BRIEFING_TEAMWILL_COUNTRIES:
            teamwill_rel = f"TEAMWILL operates in {hq_country}"
        else:
            teamwill_rel = "TEAMWILL covers this market"

        action = session.execute(text("""
            SELECT headline, signal_type, signal_date, source_url
            FROM company_action_signals
            WHERE entity_id::text = :eid
            ORDER BY signal_date DESC NULLS LAST
            LIMIT 1
        """), {"eid": eid}).fetchone()

        axes = reasoning.get("axes") or {}
        recovery_items = (axes.get("recovery") or {}).get("evidence_items") or []
        seen_urls: set = set()
        source_urls: list = []
        for item in recovery_items:
            url = item.get("source_url")
            if url and url not in seen_urls:
                source_urls.append(url)
                seen_urls.add(url)
        if action and action.source_url and action.source_url not in seen_urls:
            source_urls.append(action.source_url)
            seen_urls.add(action.source_url)
        for url in profile_sources:
            if url and url not in seen_urls:
                source_urls.append(url)
                seen_urls.add(url)
        source_urls = source_urls[:3]

        return BriefingLeadOut(
            entity_id=eid,
            entity_name=row.entity_name,
            entity_type=row.entity_type,
            v2_overall_score=float(row.v2_overall_score) if row.v2_overall_score is not None else None,
            v2_tier=row.v2_tier,
            evidence_strength=evidence_strength,
            sub_segment=sub_segment,
            parent_company=parent_company,
            headquarters_country=hq_country,
            teamwill_relationship=teamwill_rel,
            latest_action_headline=action.headline if action else None,
            latest_action_type=action.signal_type if action else None,
            latest_action_date=action.signal_date.isoformat() if (action and action.signal_date) else None,
            latest_action_url=action.source_url if action else None,
            source_urls=source_urls,
            is_fallback=is_fallback,
            fallback_reason=fallback_reason,
            scorer_run_at=row.v2_computed_at.isoformat() if row.v2_computed_at else None,
        )


@app.get(
    "/api/briefing/themes",
    response_model=List[BriefingThemeOut],
    tags=["briefing"],
    summary="Auto-detected thematic patterns for the narrative briefing",
)
def briefing_themes():
    """Detect up to 3 entity clusters: leadership wave, shared vendor, or sub-segment."""
    with get_db_session() as session:
        themes: list = []

        # ── Theme 1: Leadership transitions in the same country (12 months) ──
        lead_row = session.execute(text("""
            SELECT
                p.headquarters_country,
                array_agg(DISTINCT o.entity_id::text) AS entity_ids,
                array_agg(DISTINCT s.source_url)      AS source_urls,
                COUNT(DISTINCT o.entity_id)            AS cnt
            FROM company_action_signals s
            JOIN company_profile p ON p.entity_id = s.entity_id
            JOIN opportunity_signals o ON o.entity_id = s.entity_id
            WHERE s.signal_type = 'leadership_change'
              AND s.signal_date >= NOW() - INTERVAL '12 months'
              AND p.headquarters_country IS NOT NULL
              AND o.v2_tier IN ('engage', 'develop')
            GROUP BY p.headquarters_country
            HAVING COUNT(DISTINCT o.entity_id) >= 2
            ORDER BY cnt DESC
            LIMIT 1
        """)).fetchone()

        if lead_row:
            ent_rows = session.execute(text("""
                SELECT entity_id::text, entity_name, entity_type, v2_tier
                FROM opportunity_signals
                WHERE entity_id::text = ANY(:ids)
                ORDER BY v2_overall_score DESC NULLS LAST
            """), {"ids": list(lead_row.entity_ids)}).fetchall()

            names = [r.entity_name for r in ent_rows[:3]]
            country = lead_row.headquarters_country
            if len(names) >= 2:
                name_list = ", ".join(names[:-1]) + f" and {names[-1]}"
                narrative = (
                    f"{name_list} have all seen C-suite transitions in {country} within the past 12 months. "
                    f"Leadership changes are the strongest buying-window signal in enterprise software: "
                    f"new executives audit vendor relationships within 90 days at a majority of companies. "
                    f"TEAMWILL's regional footprint in {country} makes first-call access straightforward. "
                    f"The window is open now — it narrows as the new leadership settles."
                )
            else:
                narrative = (
                    f"{names[0]} has seen a leadership transition in {country} "
                    f"that matches TEAMWILL's outreach window criteria."
                )
            src_urls = [u for u in (lead_row.source_urls or []) if u][:3]
            themes.append(BriefingThemeOut(
                theme_id=f"leadership_{country.lower().replace(' ', '_')}",
                title=f"{country} leadership wave",
                narrative=narrative,
                entities=[BriefingThemeEntity(
                    entity_id=r.entity_id, entity_name=r.entity_name,
                    entity_type=r.entity_type, v2_tier=r.v2_tier,
                ) for r in ent_rows[:3]],
                source_urls=src_urls,
            ))

        # ── Theme 2: Shared Sofico/Miles vendor ──────────────────────────────
        if len(themes) < 3:
            vendor_row = session.execute(text("""
                SELECT
                    ts.vendor,
                    array_agg(DISTINCT o.entity_id::text) AS entity_ids,
                    array_agg(DISTINCT ts.source_url)     AS source_urls,
                    COUNT(DISTINCT o.entity_id)           AS cnt
                FROM company_tech_stack ts
                JOIN opportunity_signals o ON o.entity_id = ts.entity_id
                WHERE (ts.vendor ILIKE '%sofico%' OR ts.vendor ILIKE '%miles%')
                  AND o.v2_tier IN ('engage', 'develop')
                GROUP BY ts.vendor
                HAVING COUNT(DISTINCT o.entity_id) >= 2
                ORDER BY cnt DESC
                LIMIT 1
            """)).fetchone()

            if vendor_row:
                ent_rows = session.execute(text("""
                    SELECT entity_id::text, entity_name, entity_type, v2_tier
                    FROM opportunity_signals
                    WHERE entity_id::text = ANY(:ids)
                    ORDER BY v2_overall_score DESC NULLS LAST
                """), {"ids": list(vendor_row.entity_ids)}).fetchall()

                names = [r.entity_name for r in ent_rows[:3]]
                vendor = vendor_row.vendor
                if len(names) >= 2:
                    narrative = (
                        f"{names[0]} and {names[1]} both run on {vendor}. "
                        f"Shared infrastructure creates a referral corridor — "
                        f"a TEAMWILL win at one entity becomes a warm introduction at the other. "
                        f"TEAMWILL's Sofico-certified partnership is the door-opener: both counterparts "
                        f"know the integration story before the first call. "
                        f"Combined, these entities represent a multi-year expansion footprint."
                    )
                else:
                    narrative = (
                        f"{names[0]} is on {vendor}, creating a Sofico integration entry point "
                        f"for TEAMWILL."
                    )
                src_urls = [u for u in (vendor_row.source_urls or []) if u][:3]
                themes.append(BriefingThemeOut(
                    theme_id=f"shared_vendor_{vendor.lower().replace(' ', '_')[:20]}",
                    title=f"Captive auto-finance corridor ({vendor})",
                    narrative=narrative,
                    entities=[BriefingThemeEntity(
                        entity_id=r.entity_id, entity_name=r.entity_name,
                        entity_type=r.entity_type, v2_tier=r.v2_tier,
                    ) for r in ent_rows[:3]],
                    source_urls=src_urls,
                ))

        # ── Theme 3: Same sub_segment in TEAMWILL geography ──────────────────
        if len(themes) < 3:
            seg_row = session.execute(text("""
                SELECT
                    p.sub_segment,
                    array_agg(DISTINCT o.entity_id::text) AS entity_ids,
                    array_agg(DISTINCT p.headquarters_country) AS countries,
                    COUNT(DISTINCT o.entity_id) AS cnt
                FROM company_profile p
                JOIN opportunity_signals o ON o.entity_id = p.entity_id
                WHERE p.sub_segment IS NOT NULL
                  AND p.headquarters_country = ANY(ARRAY[
                      'France','Tunisia','Morocco','Spain','United Kingdom',
                      'Belgium','Germany','Portugal','Italy'
                  ])
                  AND o.v2_tier IN ('engage', 'develop')
                GROUP BY p.sub_segment
                HAVING COUNT(DISTINCT o.entity_id) >= 2
                ORDER BY cnt DESC
                LIMIT 1
            """)).fetchone()

            if seg_row:
                ent_rows = session.execute(text("""
                    SELECT entity_id::text, entity_name, entity_type, v2_tier
                    FROM opportunity_signals
                    WHERE entity_id::text = ANY(:ids)
                    ORDER BY v2_overall_score DESC NULLS LAST
                """), {"ids": list(seg_row.entity_ids)}).fetchall()

                names = [r.entity_name for r in ent_rows[:3]]
                seg = seg_row.sub_segment
                countries = [c for c in (seg_row.countries or []) if c][:2]
                country_str = " and ".join(countries) if countries else "TEAMWILL geographies"
                if len(names) >= 2:
                    name_list = ", ".join(names[:-1]) + f" and {names[-1]}"
                    narrative = (
                        f"Within the {seg} sub-segment, {name_list} "
                        f"both show elevated V2 scores in {country_str}. "
                        f"Sector-specific pain tends to be systemic — the operational pressures "
                        f"driving complaints at one player affect peers on the same infrastructure cycle. "
                        f"TEAMWILL's product portfolio maps directly to {seg} operational needs, "
                        f"making a vertical play more efficient than isolated single-entity outreach."
                    )
                else:
                    narrative = (
                        f"{names[0]} is in the {seg} sub-segment with high V2 scores "
                        f"in {country_str}."
                    )
                themes.append(BriefingThemeOut(
                    theme_id=f"segment_{seg.lower().replace(' ', '_')[:25]}",
                    title=f"{seg} sector cluster",
                    narrative=narrative,
                    entities=[BriefingThemeEntity(
                        entity_id=r.entity_id, entity_name=r.entity_name,
                        entity_type=r.entity_type, v2_tier=r.v2_tier,
                    ) for r in ent_rows[:3]],
                    source_urls=[],
                ))

        return themes


@app.get(
    "/api/briefing/contrarian",
    response_model=BriefingContrarianOut,
    tags=["briefing"],
    summary="Largest V1→V2 negative demotion — the trap V2 caught",
)
def briefing_contrarian():
    """Entity with the largest V1-to-V2 score drop, demoted from high V1 to watch/develop."""
    with get_db_session() as session:
        row = session.execute(text("""
            SELECT
                entity_id::text AS entity_id,
                entity_name,
                entity_type,
                overall_score    AS v1,
                v2_overall_score AS v2,
                v2_tier,
                v2_reasoning
            FROM opportunity_signals
            WHERE overall_score >= 70
              AND v2_tier IN ('watch', 'develop')
              AND v2_reasoning->'axes'->'reachability'->'penalties' IS NOT NULL
            ORDER BY (overall_score - COALESCE(v2_overall_score, 0)) DESC NULLS LAST
            LIMIT 1
        """)).fetchone()

        if row is None:
            return BriefingContrarianOut(
                entity_id="", entity_name="", entity_type="",
                v1_score=0, has_data=False,
            )

        reasoning = row.v2_reasoning or {}
        axes = reasoning.get("axes") or {}
        reach = axes.get("reachability") or {}
        penalties = reach.get("penalties") or []

        top_penalty: Optional[str] = None
        lock_in_vendor: Optional[str] = None
        if penalties:
            top_p = penalties[0] if isinstance(penalties, list) else None
            if isinstance(top_p, dict):
                top_penalty = top_p.get("reason") or top_p.get("label") or str(top_p)
                lock_in_vendor = top_p.get("vendor") or top_p.get("competitor")
            elif isinstance(top_p, str):
                top_penalty = top_p

        if not lock_in_vendor:
            vendor_row = session.execute(text("""
                SELECT vendor FROM company_tech_stack
                WHERE entity_id::text = :eid
                ORDER BY detected_date DESC NULLS LAST
                LIMIT 1
            """), {"eid": row.entity_id}).fetchone()
            if vendor_row:
                lock_in_vendor = vendor_row.vendor

        return BriefingContrarianOut(
            entity_id=row.entity_id,
            entity_name=row.entity_name,
            entity_type=row.entity_type,
            v1_score=float(row.v1),
            v2_score=float(row.v2) if row.v2 is not None else None,
            v2_tier=row.v2_tier,
            top_penalty=top_penalty,
            lock_in_vendor=lock_in_vendor,
            has_data=True,
        )


@app.get(
    "/api/briefing/scorer_run",
    tags=["briefing"],
    summary="Timestamp of the most recent V2 scorer run",
)
def briefing_scorer_run():
    """Returns the latest v2_computed_at timestamp across all opportunity signals."""
    with get_db_session() as session:
        row = session.execute(text("""
            SELECT MAX(v2_computed_at) AS last_run
            FROM opportunity_signals
            WHERE v2_computed_at IS NOT NULL
        """)).fetchone()
        return {"last_run": row.last_run.isoformat() if (row and row.last_run) else None}


import pandas as pd
import numpy as np

@app.get(
    "/api/deal-intelligence",
    tags=["deal-intelligence"],
    summary="Market Positioning & Deal Intelligence Data",
)
def deal_intelligence():
    comp_path = os.path.join(_PROJECT_ROOT, "data", "aaTeamwill_competitors.csv")
    erp_path = os.path.join(_PROJECT_ROOT, "data", "aaTeamwill_erp_solutions.csv")
    
    try:
        df_comp = pd.read_csv(comp_path)
        df_erp = pd.read_csv(erp_path)
        
        # Competitors Grouped by Tier & Overlap Threat
        df_comp['is_high_threat'] = df_comp['overlap_with_teamwill_score'] >= 4
        
        def get_domain_focus(tier):
            if tier == 'Niche Specialist': return 9
            if tier == 'Tier 3 Local/Boutique': return 7
            if tier == 'Tier 2 Regional': return 5
            return 2 # Tier 1 Global
            
        df_comp['domain_focus_score'] = df_comp['competitor_tier'].apply(get_domain_focus)
        df_comp['estimated_revenue_usd_millions'] = pd.to_numeric(df_comp['estimated_revenue_usd_millions'], errors='coerce').fillna(50)
        
        # 1. Teamwill Filter Hook (Certified ERPs)
        teamwill_certified_erps = [
            "Sofico", "Sofico Miles", "Alfa Systems", "Solifi", "FIS Ambit", "Cassiopae", "APAK", "Ekip", "Cegid", "Dolibarr", "ERPNext"
        ]
        def is_certified(name):
            if not name or pd.isna(name): return False
            n = str(name).lower()
            for cert in teamwill_certified_erps:
                if cert.lower() in n: return True
            return False
            
        df_erp['is_teamwill_certified'] = df_erp['erp_name'].apply(is_certified) | df_erp['vendor'].apply(is_certified)
        
        # Helper: calculate market crowding for Chart 3
        def count_competitor_partnerships(row):
            erp_name = str(row['erp_name']).lower()
            vendor = str(row['vendor']).lower()
            count = 0
            for p in df_comp['erp_partnerships'].dropna():
                pl = p.lower()
                # Basic string match against competitor erp_partnerships
                if vendor in pl or (len(erp_name) > 4 and erp_name in pl):
                    count += 1
            return count
            
        df_erp['competitor_partnership_count'] = df_erp.apply(count_competitor_partnerships, axis=1)

        # 2. Stronghold Saturation Filter
        country_saturation = {
            "France": 0, "Tunisia": 0, "Morocco": 0, 
            "UK": 0, "Germany": 0, "US": 0
        }
        for _, row in df_comp.iterrows():
            geo = str(row['geographic_presence']).lower() + " " + str(row['headquarters_country']).lower()
            if "france" in geo or "paris" in geo: country_saturation["France"] += 1
            if "tunisia" in geo or "tunis" in geo: country_saturation["Tunisia"] += 1
            if "morocco" in geo: country_saturation["Morocco"] += 1
            if "uk" in geo or "united kingdom" in geo or "london" in geo: country_saturation["UK"] += 1
            if "germany" in geo or "munich" in geo: country_saturation["Germany"] += 1
            if "us" in geo or "united states" in geo or "america" in geo: country_saturation["US"] += 1

        saturation_list = [{"country": k, "density": v} for k, v in country_saturation.items()]
        
        # Replace NaN with None for JSON serialization
        df_comp = df_comp.replace({np.nan: None})
        competitors = df_comp.to_dict('records')
        
        df_erp = df_erp.replace({np.nan: None})
        erp_data = df_erp.to_dict('records')
        
        return {
            "teamwill_stats": {
                "revenue_bracket": "€100M",
                "experts": "800+",
                "countries": 11,
                "certified_erps": 7
            },
            "competitors": competitors,
            "erp_solutions": erp_data,
            "regional_saturation": saturation_list
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

