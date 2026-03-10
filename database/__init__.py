"""
database/__init__.py
--------------------
Public API of the database package.
Import everything you need from here.
"""

from database.base import Base, SoftDeleteMixin, TimestampMixin, new_uuid
from database.connection import (
    create_all_tables,
    drop_all_tables,
    get_async_db_session,
    get_async_engine,
    get_db,
    get_db_session,
    get_sync_engine,
    health_check,
)
from database.models import (
    ArticleNlpResult,
    CarBrand,
    CarListing,
    CarModel,
    CarPriceHistory,
    CarReview,
    CarReviewNlp,
    CompetitorPricing,
    ComplaintType,
    DataQualityLog,
    InsuranceCompany,
    InsurancePolicy,
    InsuranceQuoteHistory,
    InsuranceReview,
    InsuranceReviewNlp,
    Keyword,
    KpiMetric,
    MarketTrendArticle,
    PipelineRun,
    RawApiResponse,
    RawPage,
    RawScrapeLog,
    ReviewKeyword,
    ReviewSource,
    ScraperHealthMetric,
    ScrapingError,
    ScrapingTask,
    ScrapingRun,
    Topic,
)

__all__ = [
    # Base & Mixins
    "Base", "TimestampMixin", "SoftDeleteMixin", "new_uuid",
    # Connection utilities
    "get_sync_engine", "get_async_engine",
    "get_db_session", "get_async_db_session", "get_db",
    "create_all_tables", "drop_all_tables", "health_check",
    # Models - Scraping Infrastructure
    "ScrapingTask", "ScrapingRun", "ScrapingError",
    "ScraperHealthMetric", "PipelineRun",
    # Models - Raw Data Storage
    "RawPage", "RawApiResponse", "RawScrapeLog",
    # Models - Automotive
    "ReviewSource", "CarBrand", "CarModel", "CarListing", "CarPriceHistory",
    # Models - Insurance
    "InsuranceCompany", "InsurancePolicy", "InsuranceQuoteHistory", "CompetitorPricing",
    # Models - Feedback
    "ComplaintType", "CarReview", "InsuranceReview", "DataQualityLog",
    # Models - NLP
    "Topic", "CarReviewNlp", "InsuranceReviewNlp", "ArticleNlpResult",
    # Models - Keywords
    "Keyword", "ReviewKeyword",
    # Models - Market Intelligence
    "MarketTrendArticle",
    # Models - Analytics
    "KpiMetric",
]
