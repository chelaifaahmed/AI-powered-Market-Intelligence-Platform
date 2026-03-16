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
import sys
from datetime import date, datetime
from typing import Any, List, Optional
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict

# ---------------------------------------------------------------------------
# Ensure project root is importable
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from database.connection import get_db_session, health_check
from database.models import (
    BrandReputationScore,
    CarBrand,
    CarListing,
    CarModel,
    CarReview,
    CompetitorPricing,
    InsuranceReview,
    MarketTrendArticle,
    PipelineRun,
    SentimentTrend,
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
    allow_methods=["GET"],
    allow_headers=["*"],
)


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


class CarReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    source_url: str
    rating: Optional[float]
    review_title: Optional[str]
    review_text: str
    author: Optional[str]
    review_date: Optional[date]
    scraped_at: datetime


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
    scraped_at: datetime


class ArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    title: str
    author: Optional[str]
    publication_date: Optional[date]
    body_text: Optional[str]
    source_url: str
    scraped_at: datetime


class CompetitorPricingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    price: float
    currency: str
    coverage_type: Optional[str]
    region: Optional[str]
    snapshot_date: date
    scraped_at: datetime


class ReputationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    period_date: date
    avg_rating: Optional[float]
    avg_sentiment_score: Optional[float]
    review_count: int
    computed_at: datetime


class SentimentTrendOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    period_date: date
    positive_count: int
    neutral_count: int
    negative_count: int
    avg_sentiment_score: Optional[float]
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
def brand_reputation(brand_id: UUID):
    """Monthly brand reputation scores (avg rating + avg sentiment) from the analytics layer."""
    with get_db_session() as session:
        brand = session.get(CarBrand, brand_id)
        if not brand:
            raise HTTPException(status_code=404, detail="Brand not found")
        rows = (
            session.query(BrandReputationScore)
            .filter(BrandReputationScore.brand_id == brand_id)
            .order_by(BrandReputationScore.period_date.desc())
            .all()
        )
        return [ReputationOut.model_validate(r) for r in rows]


@app.get("/api/brands/{brand_id}/sentiment", response_model=List[SentimentTrendOut], tags=["analytics"])
def brand_sentiment(brand_id: UUID):
    """Monthly sentiment trend (positive / neutral / negative counts) for a brand."""
    with get_db_session() as session:
        brand = session.get(CarBrand, brand_id)
        if not brand:
            raise HTTPException(status_code=404, detail="Brand not found")
        rows = (
            session.query(SentimentTrend)
            .filter(SentimentTrend.brand_id == brand_id)
            .order_by(SentimentTrend.period_date.desc())
            .all()
        )
        return [SentimentTrendOut.model_validate(r) for r in rows]


# ---- Reviews --------------------------------------------------------------

@app.get("/api/reviews/car", response_model=PagedResponse, tags=["reviews"])
def list_car_reviews(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    brand: Optional[str] = Query(None, description="Filter by brand name (case-insensitive)"),
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


# ---- Listings -------------------------------------------------------------

@app.get("/api/listings", response_model=PagedResponse, tags=["listings"])
def list_car_listings(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    brand: Optional[str] = Query(None, description="Filter by brand name (case-insensitive)"),
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
):
    """Paginated market-trend articles, newest first."""
    with get_db_session() as session:
        total = session.query(MarketTrendArticle).count()
        rows = (
            session.query(MarketTrendArticle)
            .order_by(MarketTrendArticle.scraped_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
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
):
    """Paginated competitor insurance pricing snapshots, newest first."""
    with get_db_session() as session:
        total = session.query(CompetitorPricing).count()
        rows = (
            session.query(CompetitorPricing)
            .order_by(CompetitorPricing.snapshot_date.desc())
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
    """Recent pipeline run audit records, newest first."""
    with get_db_session() as session:
        rows = (
            session.query(PipelineRun)
            .order_by(PipelineRun.created_at.desc())
            .limit(limit)
            .all()
        )
        return [PipelineRunOut.model_validate(r) for r in rows]
