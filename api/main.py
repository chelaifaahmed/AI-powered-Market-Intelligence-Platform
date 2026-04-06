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
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Ensure project root is importable
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

from sqlalchemy import func

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
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

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
    data_origin: str = "seeded"


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
    data_origin: str = "seeded"


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
    data_origin: str = "seeded"


class ArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    title: str
    author: Optional[str]
    publication_date: Optional[date]
    body_text: Optional[str]
    source_url: str
    category: Optional[str]
    region: Optional[str]
    scraped_at: datetime
    data_origin: str = "seeded"


class CompetitorPricingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    price: float
    currency: str
    coverage_type: Optional[str]
    region: Optional[str]
    snapshot_date: date
    scraped_at: datetime
    data_origin: str = "seeded"


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
    origin: Optional[str] = Query("scraped", description="Provenance filter: all | seeded | scraped"),
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
    origin: Optional[str] = Query("scraped", description="Provenance filter: all | seeded | scraped"),
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
    origin: Optional[str] = Query(None, description="Filter by provenance: seeded | scraped | imported"),
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
    origin: Optional[str] = Query(None, description="Filter by provenance: seeded | scraped | imported"),
):
    """Paginated car marketplace listings, newest first."""
    with get_db_session() as session:
        q = session.query(CarListing)
        if brand:
            q = (
                q.join(CarModel, CarListing.model_id == CarModel.id)
                 .join(CarBrand, CarModel.brand_id == CarBrand.id)
                 .filter(CarBrand.name.ilike(f"%{brand}%"))
            )
        if origin:
            q = q.filter(CarListing.data_origin == origin)
        total = q.count()
        rows = q.order_by(CarListing.scraped_at.desc()).offset(offset).limit(limit).all()
        return PagedResponse(
            total=total,
            limit=limit,
            offset=offset,
            items=[ListingOut.model_validate(r) for r in rows],
        )


# ---- Articles -------------------------------------------------------------

@app.get("/api/articles", response_model=PagedResponse, tags=["articles"])
def list_articles(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    category: Optional[str] = Query(None, description="Filter by category: EV, Market, Technology, Manufacturing, Regulation, Insurance"),
    region: Optional[str] = Query(None, description="Filter by region"),
    origin: Optional[str] = Query(None, description="Filter by provenance: seeded | scraped | imported"),
):
    """Paginated market-trend articles, newest first. Filterable by category, region, and origin."""
    with get_db_session() as session:
        q = session.query(MarketTrendArticle)
        if category:
            q = q.filter(MarketTrendArticle.category.ilike(category))
        if region:
            q = q.filter(MarketTrendArticle.region.ilike(f"%{region}%"))
        if origin:
            q = q.filter(MarketTrendArticle.data_origin == origin)
        total = q.count()
        rows = q.order_by(MarketTrendArticle.scraped_at.desc()).offset(offset).limit(limit).all()
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

@app.get("/api/data/provenance", tags=["data"], summary="Seeded vs scraped record counts per entity type")
def data_provenance():
    """
    Returns counts of records by data_origin (seeded | scraped | imported)
    for the five main domain tables.  Used by the dashboard to distinguish
    demo data from real intelligence.
    """
    with get_db_session() as session:
        def _origins(model_cls, origin_col="data_origin"):
            col = getattr(model_cls, origin_col)
            rows = session.query(col, func.count()).group_by(col).all()
            return {r[0]: r[1] for r in rows}

        return {
            "car_reviews":         _origins(CarReview),
            "insurance_reviews":   _origins(InsuranceReview),
            "car_listings":        _origins(CarListing),
            "market_articles":     _origins(MarketTrendArticle),
            "competitor_pricings": _origins(CompetitorPricing),
            "nlp_models": {
                row[0]: row[1]
                for row in session.execute(
                    __import__("sqlalchemy").text(
                        "SELECT model_version, COUNT(*) FROM article_nlp_results GROUP BY model_version"
                    )
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
        total_car_reviews       = session.query(CarReview).count()
        total_insurance_reviews = session.query(InsuranceReview).count()
        total_listings          = session.query(CarListing).count()
        total_articles          = session.query(MarketTrendArticle).count()
        total_competitors       = session.query(CompetitorPricing).count()
        total_brands            = session.query(CarBrand).count()

        # Source breakdown for car reviews
        car_reviews_sample = (
            session.query(CarReview.source_url)
            .order_by(CarReview.scraped_at.desc())
            .limit(500)
            .all()
        )
        domain_counts: dict = {}
        for (url,) in car_reviews_sample:
            try:
                d = _urlparse(url).netloc.replace("www.", "")
            except Exception:
                d = "unknown"
            domain_counts[d] = domain_counts.get(d, 0) + 1
        review_sources = sorted(
            [{"source": k, "count": v} for k, v in domain_counts.items()],
            key=lambda x: -x["count"],
        )[:8]

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
    origin: Optional[str] = Query(None, description="Provenance filter for analytics: all | seeded | scraped"),
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
        rows = session.query(CarListing.listed_price, CarListing.mileage_km, CarListing.country).all()

        prices = [r.listed_price for r in rows if r.listed_price is not None]
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
        return [ArticleCategoryOut(category=r.category, count=r.cnt) for r in rows]


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


# ===========================================================================
# AI Market Analyst — Chat endpoint (Groq-powered, LLaMA 3.3 70B)
# ===========================================================================

from groq import Groq

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
        temperature=0.7,
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
    Send a conversation to the AI Market Analyst. The backend gathers live
    database context and forwards to Groq for an intelligence-grade response.
    """
    if not body.messages:
        raise HTTPException(status_code=400, detail="messages list cannot be empty")

    # Gather live DB context
    with get_db_session() as session:
        db_context, sources = _gather_analyst_context(session)

    system_prompt = (
        "You are the AI Market Analyst for the Automotive Intelligence Platform, "
        "an expert system built by TEAMWILL. You have access to live database intelligence "
        "about car brands, reviews, listings, insurance companies, competitor pricing, "
        "opportunity signals, and market articles.\n\n"
        "LIVE DATABASE CONTEXT:\n"
        f"{db_context}\n\n"
        "INSTRUCTIONS:\n"
        "- Answer questions using the live data above. Cite specific numbers.\n"
        "- Provide actionable market intelligence insights.\n"
        "- When discussing opportunity signals, explain what drives the scores.\n"
        "- Be concise but thorough. Use bullet points for clarity.\n"
        "- If asked something not covered by the data, say so honestly.\n"
        "- Format responses with markdown for readability.\n"
    )

    # Split: all messages except last become history, last is the new user message
    all_msgs = [{"role": m.role, "content": m.content} for m in body.messages]
    history = all_msgs[:-1]
    user_message = all_msgs[-1]["content"]

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
    teamwill_fit: float
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
        teamwill_fit=r.get("teamwill_fit", {}).get("score", 0),
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
