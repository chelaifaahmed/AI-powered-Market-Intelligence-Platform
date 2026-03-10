"""
database/enums.py
-----------------
PostgreSQL-native ENUM type definitions for the platform.

All string status / label / category fields that have a closed set of
values are backed by a PostgreSQL ENUM so that invalid values are
rejected at the database level, not just at the ORM level.
"""

import enum

from sqlalchemy import Enum as SAEnum


# ---------------------------------------------------------------------------
# Scraping Infrastructure Enums
# ---------------------------------------------------------------------------

class TaskStatus(str, enum.Enum):
    QUEUED    = "QUEUED"
    RUNNING   = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED    = "FAILED"
    DEAD      = "DEAD"


class RunStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED  = "FAILED"
    PARTIAL = "PARTIAL"
    TIMEOUT = "TIMEOUT"


class ScrapeLogStatus(str, enum.Enum):
    SUCCESS      = "success"
    FAILED       = "failed"
    SKIPPED      = "skipped"
    RATE_LIMITED = "rate_limited"
    TIMEOUT      = "timeout"


class PipelineStatus(str, enum.Enum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED  = "failed"
    PARTIAL = "partial"


# ---------------------------------------------------------------------------
# Automotive Domain Enums
# ---------------------------------------------------------------------------

class ListingCondition(str, enum.Enum):
    NEW       = "new"
    USED      = "used"
    CERTIFIED = "certified"


class PriceType(str, enum.Enum):
    MSRP          = "MSRP"
    DEALER_LISTED = "dealer_listed"
    AUCTION       = "auction"
    ESTIMATED     = "estimated"


class EngineType(str, enum.Enum):
    ICE    = "ICE"
    EV     = "EV"
    HYBRID = "Hybrid"
    PHEV   = "PHEV"
    FCEV   = "FCEV"


# ---------------------------------------------------------------------------
# Insurance Domain Enums
# ---------------------------------------------------------------------------

class CoverageType(str, enum.Enum):
    COMPREHENSIVE           = "comprehensive"
    THIRD_PARTY             = "third_party"
    THIRD_PARTY_FIRE_THEFT  = "third_party_fire_theft"
    LIABILITY               = "liability"
    OTHER                   = "other"


# ---------------------------------------------------------------------------
# NLP / Sentiment Enums
# ---------------------------------------------------------------------------

class SentimentLabel(str, enum.Enum):
    POSITIVE = "positive"
    NEUTRAL  = "neutral"
    NEGATIVE = "negative"


# ---------------------------------------------------------------------------
# Shared Domain Enums
# ---------------------------------------------------------------------------

class EntityDomain(str, enum.Enum):
    AUTOMOTIVE = "automotive"
    INSURANCE  = "insurance"
    GENERAL    = "general"


class ReviewType(str, enum.Enum):
    CAR       = "car"
    INSURANCE = "insurance"
    ARTICLE   = "article"


class SourceType(str, enum.Enum):
    AUTOMOTIVE_REVIEW = "automotive_review"
    NEWS_BLOG         = "news_blog"
    MARKETPLACE       = "marketplace"
    INSURANCE_REVIEW  = "insurance_review"
    FORUM             = "forum"
    PRICING_PAGE      = "pricing_page"
    TREND_ARTICLE     = "trend_article"


class KpiGranularity(str, enum.Enum):
    DAILY   = "daily"
    WEEKLY  = "weekly"
    MONTHLY = "monthly"




# ---------------------------------------------------------------------------
# SQLAlchemy column type helpers
# (use these directly in mapped_column() calls)
# ---------------------------------------------------------------------------

def pg_enum(enum_class: type, **kwargs) -> SAEnum:
    """
    Returns a PostgreSQL-native ENUM column type.
    name= defaults to the snake_case version of the enum class name.
    """
    name = kwargs.pop(
        "name",
        "".join(
            ["_" + c.lower() if c.isupper() else c for c in enum_class.__name__]
        ).lstrip("_"),
    )
    return SAEnum(
        enum_class,
        name=name,
        create_constraint=True,
        native_enum=True,
        **kwargs,
    )
