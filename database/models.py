"""
database/models.py  (hardened v2)
----------------------------------
Production-grade SQLAlchemy ORM models for the AI-Powered Automotive &
Car Insurance Market Intelligence Platform.

Hardening pass applied:
  Phase 1 - SQLAlchemy Index() objects on all FKs, analytics & partition columns
  Phase 2 - PostgreSQL-native ENUMs for all closed-value string fields
  Phase 3 - Partition safety (NOT NULL on partition keys, partition_by markers)
  Phase 4 - lazy='selectin' on all high-volume relationships
  Phase 5 - Strengthened data-integrity constraints
  Phase 6 - Lineage traceability fields (scraper_version, confidence_score)
  Phase 7 - Table & column comment= metadata
"""

import uuid
from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Date, DateTime, Enum as SAEnum,
    ForeignKey, Index, Integer, Numeric, SmallInteger, String, Text,
    UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, SoftDeleteMixin, TimestampMixin, new_uuid
from database.enums import (
    CoverageType, EntityDomain, KpiGranularity,
    ListingCondition, PipelineStatus, PriceType, ReviewType,
    RunStatus, ScrapeLogStatus, SentimentLabel, SourceType, TaskStatus, pg_enum,
)
# ---------------------------------------------------------------------------
# GROUP B - Scraping Infrastructure (defined first; referenced by Group A)
# ---------------------------------------------------------------------------

class ScrapingTask(Base, TimestampMixin):
    """High-level scraping directive specifying what to scrape, when, and with which priority."""
    __tablename__ = "scraping_tasks"
    __table_args__ = (
        CheckConstraint("priority BETWEEN 1 AND 3", name="chk_task_priority"),
        CheckConstraint("retry_count <= max_retries", name="chk_task_retry_bound"),
        Index("idx_tasks_status", "status"),
        Index("idx_tasks_scheduled", "scheduled_at"),
        Index("idx_tasks_priority_status", "priority", "status"),
        Index("idx_tasks_created", "created_at"),
        {"comment": "Master table of scraping directives - one row per site/task to be scraped."},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=new_uuid,
        comment="Surrogate UUID primary key."
    )
    task_name: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="Human-readable name, e.g. 'caranddriver_reviews_daily'."
    )
    scraper_class: Mapped[str] = mapped_column(
        String(200), nullable=False,
        comment="Fully-qualified Python class path for the scraper."
    )
    target_url_pattern: Mapped[Optional[str]] = mapped_column(Text)
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    priority: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=2,
        comment="1=high, 2=normal, 3=low."
    )
    # Phase 2: PostgreSQL ENUM replaces plain String
    status: Mapped[TaskStatus] = mapped_column(
        pg_enum(TaskStatus, name="task_status"),
        nullable=False, default=TaskStatus.QUEUED,
        comment="Lifecycle state of this task."
    )
    max_retries: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=3)
    retry_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    config_overrides: Mapped[Optional[dict]] = mapped_column(
        JSONB, comment="Per-task overrides for scraper settings (headers, delays, etc.)."
    )

    # Relationships (Phase 4: lazy='selectin' for high-volume children)
    runs: Mapped[List["ScrapingRun"]] = relationship(
        "ScrapingRun", back_populates="task",
        cascade="all, delete-orphan", lazy="selectin"
    )
    raw_pages: Mapped[List["RawPage"]] = relationship(
        "RawPage", back_populates="scrape_task", lazy="selectin"
    )
    raw_api_responses: Mapped[List["RawApiResponse"]] = relationship(
        "RawApiResponse", back_populates="scrape_task", lazy="selectin"
    )
    raw_scrape_logs: Mapped[List["RawScrapeLog"]] = relationship(
        "RawScrapeLog", back_populates="scrape_task", lazy="selectin"
    )


class ScrapingRun(Base):
    """Single execution attempt of a ScrapingTask, including retries."""
    __tablename__ = "scraping_runs"
    __table_args__ = (
        CheckConstraint("records_rejected <= records_extracted", name="chk_run_rejected_bound"),
        CheckConstraint("pages_fetched >= 0", name="chk_run_pages"),
        CheckConstraint("bytes_downloaded >= 0", name="chk_run_bytes"),
        Index("idx_runs_task", "task_id"),
        Index("idx_runs_status", "status"),
        Index("idx_runs_started", "started_at"),
        Index("idx_runs_task_status", "task_id", "status"),
        {"comment": "Each row is one execution attempt of a scraping_task, including automated retries."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scraping_tasks.id", ondelete="CASCADE"), nullable=False
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    # Phase 2: ENUM
    status: Mapped[RunStatus] = mapped_column(
        pg_enum(RunStatus, name="run_status"), nullable=False, default=RunStatus.RUNNING
    )
    pages_fetched: Mapped[int] = mapped_column(Integer, default=0)
    records_extracted: Mapped[int] = mapped_column(Integer, default=0)
    records_rejected: Mapped[int] = mapped_column(Integer, default=0)
    bytes_downloaded: Mapped[int] = mapped_column(BigInteger, default=0)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    exit_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    task: Mapped["ScrapingTask"] = relationship("ScrapingTask", back_populates="runs")
    errors: Mapped[List["ScrapingError"]] = relationship(
        "ScrapingError", back_populates="run",
        cascade="all, delete-orphan", lazy="selectin"
    )
    health_metrics: Mapped[List["ScraperHealthMetric"]] = relationship(
        "ScraperHealthMetric", back_populates="run", lazy="selectin"
    )


class ScrapingError(Base):
    """Exception log per scraping run - every raised exception is persisted here."""
    __tablename__ = "scraping_errors"
    __table_args__ = (
        Index("idx_errors_run", "run_id"),
        Index("idx_errors_task", "task_id"),
        Index("idx_errors_type", "error_type"),
        Index("idx_errors_occurred", "occurred_at"),
        {"comment": "Append-only error log; never update rows."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scraping_runs.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scraping_tasks.id", ondelete="CASCADE"), nullable=False
    )
    error_type: Mapped[Optional[str]] = mapped_column(String(100))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    stack_trace: Mapped[Optional[str]] = mapped_column(Text)
    target_url: Mapped[Optional[str]] = mapped_column(Text)
    is_retryable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    run: Mapped["ScrapingRun"] = relationship("ScrapingRun", back_populates="errors")


class ScraperHealthMetric(Base):
    """Aggregated scraper performance metrics captured after every run."""
    __tablename__ = "scraper_health_metrics"
    __table_args__ = (
        CheckConstraint("success_rate BETWEEN 0 AND 1", name="chk_success_rate"),
        CheckConstraint("error_rate BETWEEN 0 AND 1", name="chk_error_rate"),
        CheckConstraint("success_rate + error_rate <= 1.0001", name="chk_rate_sum"),
        CheckConstraint("avg_response_time_ms >= 0", name="chk_avg_response_time"),
        Index("idx_health_scraper_time", "scraper_name", "measured_at"),
        Index("idx_health_run", "run_id"),
        {"comment": "One row per (run, scraper_name) - used for SLA monitoring dashboards."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    scraper_name: Mapped[str] = mapped_column(String(100), nullable=False)
    run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scraping_runs.id", ondelete="SET NULL")
    )
    avg_response_time_ms: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    success_rate: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))
    error_rate: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))
    rate_limit_hits: Mapped[int] = mapped_column(Integer, default=0)
    robots_blocked_count: Mapped[int] = mapped_column(Integer, default=0)
    measured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    run: Mapped[Optional["ScrapingRun"]] = relationship(
        "ScrapingRun", back_populates="health_metrics"
    )


class PipelineRun(Base):
    """High-level orchestration audit log for all APScheduler / Celery task executions."""
    __tablename__ = "pipeline_runs"
    __table_args__ = (
        Index("idx_pipeline_task", "task_name"),
        Index("idx_pipeline_status", "status"),
        Index("idx_pipeline_start", "started_at"),
        Index("idx_pipeline_task_start", "task_name", "started_at"),
        {"comment": "Orchestration-level audit trail; complements fine-grained scraping_runs."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    task_name: Mapped[str] = mapped_column(String(100), nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    # Phase 2: ENUM
    status: Mapped[PipelineStatus] = mapped_column(
        pg_enum(PipelineStatus, name="pipeline_status"),
        nullable=False, default=PipelineStatus.RUNNING
    )
    records_scraped: Mapped[int] = mapped_column(Integer, default=0)
    records_stored: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationship to granular step metrics
    steps: Mapped[List["PipelineStepRun"]] = relationship(
        "PipelineStepRun", back_populates="pipeline_run",
        cascade="all, delete-orphan", lazy="selectin"
    )


class PipelineStepRun(Base):
    """
    Granular per-stage operational metrics for a pipeline execution.

    One row per pipeline stage per run:
      step_name examples: 'parser', 'nlp_car_reviews', 'nlp_insurance_reviews',
                          'nlp_articles', 'analytics'
    Links optionally to a parent PipelineRun row.
    """
    __tablename__ = "pipeline_step_runs"
    __table_args__ = (
        CheckConstraint("records_seen >= 0",      name="chk_step_seen"),
        CheckConstraint("records_processed >= 0", name="chk_step_processed"),
        CheckConstraint("records_skipped >= 0",   name="chk_step_skipped"),
        CheckConstraint("records_failed >= 0",    name="chk_step_failed"),
        CheckConstraint("records_inserted >= 0",  name="chk_step_inserted"),
        CheckConstraint("error_count >= 0",       name="chk_step_errors"),
        Index("idx_step_name",       "step_name"),
        Index("idx_step_status",     "status"),
        Index("idx_step_created",    "created_at"),
        Index("idx_step_pipeline",   "pipeline_run_id"),
        Index("idx_step_name_start", "step_name", "started_at"),
        {"comment": "Per-stage operational metrics: parser / nlp_* / analytics steps."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    pipeline_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_runs.id", ondelete="SET NULL"),
        comment="Optional link to parent PipelineRun."
    )
    step_name: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="Stage identifier, e.g. 'parser', 'nlp_car_reviews', 'analytics'."
    )
    status: Mapped[PipelineStatus] = mapped_column(
        pg_enum(PipelineStatus, name="pipeline_status"),
        nullable=False, default=PipelineStatus.RUNNING,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[Optional[int]] = mapped_column(
        Integer, comment="Wall-clock duration in milliseconds."
    )
    records_seen: Mapped[int] = mapped_column(
        Integer, default=0, comment="Rows visible to this stage (e.g. unparsed pages)."
    )
    records_processed: Mapped[int] = mapped_column(
        Integer, default=0, comment="Rows fully processed without error."
    )
    records_skipped: Mapped[int] = mapped_column(
        Integer, default=0, comment="Rows skipped (duplicates, empty, already done)."
    )
    records_failed: Mapped[int] = mapped_column(
        Integer, default=0, comment="Rows that caused an error during this stage."
    )
    records_inserted: Mapped[int] = mapped_column(
        Integer, default=0, comment="New rows written to domain tables."
    )
    error_count: Mapped[int] = mapped_column(
        Integer, default=0, comment="Total exception count in this stage."
    )
    step_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB, comment="Arbitrary extra context: batch_limit, enable_llm, etc."
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    pipeline_run: Mapped[Optional["PipelineRun"]] = relationship(
        "PipelineRun", back_populates="steps"
    )


# ---------------------------------------------------------------------------
# GROUP A - Raw Data Storage
# ---------------------------------------------------------------------------

class RawPage(Base):
    """Immutable full HTML dump of every fetched page - source of truth for reprocessing."""
    __tablename__ = "raw_pages"
    __table_args__ = (
        CheckConstraint("http_status_code BETWEEN 100 AND 599", name="chk_raw_page_status"),
        Index("idx_raw_pages_task", "scrape_task_id"),
        Index("idx_raw_pages_domain", "source_domain"),
        Index("idx_raw_pages_scraped", "scraped_at"),
        Index("idx_raw_pages_unparsed", "is_parsed",
              postgresql_where=text("is_parsed = FALSE")),
        Index("idx_raw_pages_hash", "content_hash"),
        {"comment": "Immutable raw HTML archive - rows are never updated after insert."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    scrape_task_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scraping_tasks.id", ondelete="SET NULL"),
        comment="Phase 6: lineage - links raw HTML back to the originating task."
    )
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_domain: Mapped[Optional[str]] = mapped_column(String(200))
    http_status_code: Mapped[Optional[int]] = mapped_column(Integer)
    raw_html: Mapped[Optional[str]] = mapped_column(Text)
    content_hash: Mapped[Optional[str]] = mapped_column(
        String(64), comment="SHA-256 of raw_html for change-detection deduplication."
    )
    # Phase 6: lineage field - which scraper version produced this
    scraper_version: Mapped[Optional[str]] = mapped_column(
        String(50), comment="Version tag of the scraper that produced this row."
    )
    is_parsed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    parse_error: Mapped[Optional[str]] = mapped_column(Text)
    # Phase 3: partition key is NOT NULL
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    scrape_task: Mapped[Optional["ScrapingTask"]] = relationship(
        "ScrapingTask", back_populates="raw_pages"
    )


class RawApiResponse(Base):
    """Raw JSON payload from any structured API or JSON endpoint."""
    __tablename__ = "raw_api_responses"
    __table_args__ = (
        CheckConstraint("http_status_code BETWEEN 100 AND 599", name="chk_api_status"),
        CheckConstraint("response_size_bytes >= 0", name="chk_api_size"),
        Index("idx_raw_api_task", "scrape_task_id"),
        Index("idx_raw_api_scraped", "scraped_at"),
        Index("idx_raw_api_unparsed", "is_parsed",
              postgresql_where=text("is_parsed = FALSE")),
        {"comment": "Raw API response archive - never overwrite, always insert."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    scrape_task_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scraping_tasks.id", ondelete="SET NULL")
    )
    endpoint_url: Mapped[str] = mapped_column(Text, nullable=False)
    request_params: Mapped[Optional[dict]] = mapped_column(JSONB)
    response_headers: Mapped[Optional[dict]] = mapped_column(JSONB)
    response_body: Mapped[Optional[dict]] = mapped_column(JSONB)
    http_status_code: Mapped[Optional[int]] = mapped_column(Integer)
    response_size_bytes: Mapped[Optional[int]] = mapped_column(Integer)
    is_parsed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    scrape_task: Mapped[Optional["ScrapingTask"]] = relationship(
        "ScrapingTask", back_populates="raw_api_responses"
    )


class RawScrapeLog(Base):
    """Per-HTTP-request execution log - one row per scraping attempt."""
    __tablename__ = "raw_scrape_logs"
    __table_args__ = (
        CheckConstraint("attempt_number >= 1", name="chk_log_attempt"),
        CheckConstraint("duration_ms >= 0", name="chk_log_duration"),
        CheckConstraint("bytes_downloaded >= 0", name="chk_log_bytes"),
        Index("idx_scrape_logs_task", "scrape_task_id"),
        Index("idx_scrape_logs_status", "status"),
        Index("idx_scrape_logs_logged", "logged_at"),
        Index("idx_scrape_logs_scraper_status", "scraper_name", "status"),
        {"comment": "Detailed per-request log for rate-limit analysis and debugging."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    scrape_task_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scraping_tasks.id", ondelete="SET NULL")
    )
    scraper_name: Mapped[str] = mapped_column(String(100), nullable=False)
    target_url: Mapped[Optional[str]] = mapped_column(Text)
    attempt_number: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    # Phase 2: ENUM
    status: Mapped[ScrapeLogStatus] = mapped_column(
        pg_enum(ScrapeLogStatus, name="scrape_log_status"),
        nullable=False
    )
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)
    bytes_downloaded: Mapped[Optional[int]] = mapped_column(Integer)
    error_type: Mapped[Optional[str]] = mapped_column(String(100))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    logged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    scrape_task: Mapped[Optional["ScrapingTask"]] = relationship(
        "ScrapingTask", back_populates="raw_scrape_logs"
    )


# ---------------------------------------------------------------------------
# GROUP C - Automotive Domain
# ---------------------------------------------------------------------------

class ReviewSource(Base, TimestampMixin):
    """Lookup table for all data sources - every scraper links its output to a row here."""
    __tablename__ = "review_sources"
    __table_args__ = (
        CheckConstraint("reliability_score BETWEEN 0 AND 1", name="chk_reliability_score"),
        Index("idx_sources_type", "source_type"),
        Index("idx_sources_active", "is_active",
              postgresql_where=text("is_active = TRUE")),
        {"comment": "Central source registry; all scraped rows carry a source_id FK to here."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    # Phase 2: ENUM
    source_type: Mapped[Optional[SourceType]] = mapped_column(
        pg_enum(SourceType, name="source_type"), nullable=True
    )
    reliability_score: Mapped[float] = mapped_column(
        Numeric(4, 3), default=0.800,
        comment="0-1 score representing source data quality / trustworthiness."
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    region: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="Geographic region: EU, TN, US, Global")
    keywords: Mapped[Optional[list]] = mapped_column(ARRAY(Text), nullable=True, comment="Search keywords for this source")
    last_scraped_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    total_records_scraped: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, comment="Soft-delete timestamp")

    car_reviews: Mapped[List["CarReview"]] = relationship(
        "CarReview", back_populates="source", lazy="selectin"
    )
    insurance_reviews: Mapped[List["InsuranceReview"]] = relationship(
        "InsuranceReview", back_populates="source", lazy="selectin"
    )
    market_trend_articles: Mapped[List["MarketTrendArticle"]] = relationship(
        "MarketTrendArticle", back_populates="source", lazy="selectin"
    )


class CarBrand(Base, TimestampMixin, SoftDeleteMixin):
    """Automotive manufacturer entity - top of the automotive hierarchy."""
    __tablename__ = "car_brands"
    __table_args__ = (
        CheckConstraint("founded_year BETWEEN 1800 AND 2100", name="chk_brand_founded_year"),
        Index("idx_brands_name", "name"),
        Index("idx_brands_active", "is_active",
              postgresql_where=text("is_active = TRUE")),
        {"comment": "One row per car manufacturer, e.g. Toyota, BMW."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    country_of_origin: Mapped[Optional[str]] = mapped_column(String(100))
    founded_year: Mapped[Optional[int]] = mapped_column(SmallInteger)
    logo_url: Mapped[Optional[str]] = mapped_column(Text)
    region: Mapped[Optional[str]] = mapped_column(String(20), comment="Geographic region code, e.g. TN, EU, Global")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # ML clustering results
    cluster_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="KMeans cluster assignment")
    cluster_label: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="Human-readable cluster label")
    erp_module: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="Recommended TEAMWILL ERP module")

    # Phase 4: selectin for high-volume child
    models: Mapped[List["CarModel"]] = relationship(
        "CarModel", back_populates="brand",
        cascade="all, delete-orphan", lazy="selectin"
    )


class CarModel(Base, TimestampMixin, SoftDeleteMixin):
    """Car model under a brand, uniquely identified by (brand, name, year)."""
    __tablename__ = "car_models"
    __table_args__ = (
        UniqueConstraint("brand_id", "name", "year", name="uq_model_brand_name_year"),
        CheckConstraint("year BETWEEN 1900 AND 2100", name="chk_model_year"),
        Index("idx_models_brand", "brand_id"),
        Index("idx_models_segment", "segment"),
        Index("idx_models_year", "year"),
        Index("idx_models_engine", "engine_type"),
        Index("idx_models_active", "is_active",
              postgresql_where=text("is_active = TRUE")),
        {"comment": "Specific model-year, e.g. Toyota Corolla 2023."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("car_brands.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    year: Mapped[Optional[int]] = mapped_column(SmallInteger)
    segment: Mapped[Optional[str]] = mapped_column(String(50))
    body_type: Mapped[Optional[str]] = mapped_column(String(50))
    engine_type: Mapped[Optional[str]] = mapped_column(String(50))
    # Phase 8: rich vehicle specification fields
    trim_level: Mapped[Optional[str]] = mapped_column(String(100), comment="e.g. 'SE', 'Sport', 'Long Range'")
    transmission: Mapped[Optional[str]] = mapped_column(String(50), comment="e.g. 'Automatic', 'Manual', 'CVT'")
    drivetrain: Mapped[Optional[str]] = mapped_column(String(50), comment="e.g. 'FWD', 'RWD', 'AWD', '4WD'")
    horsepower_hp: Mapped[Optional[int]] = mapped_column(SmallInteger, comment="Peak power in horsepower")
    torque_nm: Mapped[Optional[int]] = mapped_column(SmallInteger, comment="Peak torque in Newton-metres")
    battery_kwh: Mapped[Optional[float]] = mapped_column(Numeric(6, 2), comment="Usable battery capacity (EVs only)")
    range_km: Mapped[Optional[int]] = mapped_column(SmallInteger, comment="WLTP/EPA range in km (EVs only)")
    doors: Mapped[Optional[int]] = mapped_column(SmallInteger, comment="Number of doors")
    seats: Mapped[Optional[int]] = mapped_column(SmallInteger, comment="Seating capacity")
    msrp_eur: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), comment="Manufacturer suggested retail price in EUR")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    brand: Mapped["CarBrand"] = relationship("CarBrand", back_populates="models")
    # Phase 4: selectin on high-volume relationships
    reviews: Mapped[List["CarReview"]] = relationship(
        "CarReview", back_populates="model",
        cascade="all, delete-orphan", lazy="selectin"
    )
    listings: Mapped[List["CarListing"]] = relationship(
        "CarListing", back_populates="model",
        cascade="all, delete-orphan", lazy="selectin"
    )
    price_history: Mapped[List["CarPriceHistory"]] = relationship(
        "CarPriceHistory", back_populates="model",
        cascade="all, delete-orphan", lazy="selectin"
    )


class CarListing(Base, TimestampMixin):
    """Individual dealer or marketplace listing for a car model."""
    __tablename__ = "car_listings"
    __table_args__ = (
        CheckConstraint("listed_price > 0", name="chk_listing_price"),
        CheckConstraint("mileage_km >= 0", name="chk_mileage"),
        CheckConstraint("char_length(currency) = 3", name="chk_listing_currency_len"),
        Index("idx_listings_model", "model_id"),
        Index("idx_listings_source", "source_id"),
        Index("idx_listings_condition", "condition"),
        Index("idx_listings_price", "listed_price"),
        Index("idx_listings_scraped", "scraped_at"),
        Index("idx_listings_model_scraped", "model_id", "scraped_at"),
        {"comment": "Granular marketplace listings - complement aggregate car_price_history."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    model_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("car_models.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("review_sources.id", ondelete="SET NULL")
    )
    listing_url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    dealer_name: Mapped[Optional[str]] = mapped_column(String(200))
    # Phase 2: ENUM
    condition: Mapped[Optional[ListingCondition]] = mapped_column(
        pg_enum(ListingCondition, name="listing_condition"), nullable=True
    )
    mileage_km: Mapped[Optional[int]] = mapped_column(Integer)
    listed_price: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    # Phase 5: enforce ISO-4217 3-character currency code
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="EUR",
        comment="ISO 4217 currency code (always 3 chars)."
    )
    city: Mapped[Optional[str]] = mapped_column(String(100))
    country: Mapped[Optional[str]] = mapped_column(String(100))
    listed_at: Mapped[Optional[date]] = mapped_column(Date)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Phase 8: richer listing detail
    fuel_type: Mapped[Optional[str]] = mapped_column(String(50), comment="e.g. 'Petrol', 'Diesel', 'Electric', 'Hybrid'")
    transmission: Mapped[Optional[str]] = mapped_column(String(50), comment="e.g. 'Automatic', 'Manual'")
    color: Mapped[Optional[str]] = mapped_column(String(50))
    trim_level: Mapped[Optional[str]] = mapped_column(String(100))
    listing_year: Mapped[Optional[int]] = mapped_column(SmallInteger, comment="Model year of the listed vehicle")
    # Provenance: reference | scraped | imported
    data_origin: Mapped[str] = mapped_column(String(20), nullable=False, default="reference", server_default="reference")

    model: Mapped["CarModel"] = relationship("CarModel", back_populates="listings")


class CarPriceHistory(Base):
    """
    Append-only time-series of price observations per car model.
    Partitioned by scraped_at (yearly RANGE partitioning).
    Phase 3: scraped_at is NOT NULL and is the partition key.
    """
    __tablename__ = "car_price_history"
    __table_args__ = (
        CheckConstraint("listed_price > 0", name="chk_car_price_positive"),
        CheckConstraint("confidence_score BETWEEN 0 AND 1", name="chk_cph_confidence"),
        CheckConstraint("version >= 1", name="chk_cph_version"),
        CheckConstraint("char_length(currency) = 3", name="chk_cph_currency_len"),
        Index("idx_cph_model_scraped", "model_id", "scraped_at"),
        Index("idx_cph_latest", "model_id", "is_latest",
              postgresql_where=text("is_latest = TRUE")),
        Index("idx_cph_source", "source_id"),
        {"postgresql_partition_by": "RANGE (scraped_at)",
         "comment": "One row per price observation; never UPDATE - only INSERT + mark old row is_latest=FALSE."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    model_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("car_models.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("review_sources.id", ondelete="SET NULL")
    )
    listed_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    # Phase 2: ENUM for price_type
    price_type: Mapped[Optional[PriceType]] = mapped_column(
        pg_enum(PriceType, name="price_type"), nullable=True
    )
    confidence_score: Mapped[Optional[float]] = mapped_column(
        Numeric(4, 3),
        comment="Phase 6: 0-1 confidence of price accuracy from source reliability."
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_latest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Phase 3: NOT NULL enforced on the partition key
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    superseded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    model: Mapped["CarModel"] = relationship("CarModel", back_populates="price_history")


# ---------------------------------------------------------------------------
# GROUP D - Insurance Domain
# ---------------------------------------------------------------------------

class InsuranceCompany(Base, TimestampMixin, SoftDeleteMixin):
    """Insurance company entity - top of the insurance hierarchy."""
    __tablename__ = "insurance_companies"
    __table_args__ = (
        CheckConstraint("founded_year BETWEEN 1800 AND 2100", name="chk_insurer_founded"),
        Index("idx_insurers_name", "name"),
        Index("idx_insurers_country", "country"),
        Index("idx_insurers_active", "is_active",
              postgresql_where=text("is_active = TRUE")),
        {"comment": "One row per insurance company, e.g. AXA, Allianz."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    country: Mapped[Optional[str]] = mapped_column(String(100))
    website: Mapped[Optional[str]] = mapped_column(Text)
    founded_year: Mapped[Optional[int]] = mapped_column(SmallInteger)
    region: Mapped[Optional[str]] = mapped_column(String(20), comment="Geographic region code, e.g. TN, EU, Global")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # ML clustering results
    cluster_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="KMeans cluster assignment")
    cluster_label: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="Human-readable cluster label")
    erp_module: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="Recommended TEAMWILL ERP module")

    policies: Mapped[List["InsurancePolicy"]] = relationship(
        "InsurancePolicy", back_populates="company",
        cascade="all, delete-orphan", lazy="selectin"
    )
    reviews: Mapped[List["InsuranceReview"]] = relationship(
        "InsuranceReview", back_populates="company",
        cascade="all, delete-orphan", lazy="selectin"
    )
    competitor_pricings: Mapped[List["CompetitorPricing"]] = relationship(
        "CompetitorPricing", back_populates="company",
        cascade="all, delete-orphan", lazy="selectin"
    )


class InsurancePolicy(Base, TimestampMixin):
    """Insurance policy product offered by a company."""
    __tablename__ = "insurance_policies"
    __table_args__ = (
        CheckConstraint("price_range_min > 0", name="chk_policy_price_min"),
        CheckConstraint(
            "price_range_max IS NULL OR price_range_max >= price_range_min",
            name="chk_policy_price_range",
        ),
        CheckConstraint("char_length(currency) = 3", name="chk_policy_currency_len"),
        Index("idx_policies_company", "company_id"),
        Index("idx_policies_coverage", "coverage_type"),
        Index("idx_policies_source", "source_id"),
        Index("idx_policies_active", "is_active",
              postgresql_where=text("is_active = TRUE")),
        {"comment": "A specific product/tier offered by an insurance_company."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("insurance_companies.id", ondelete="CASCADE"), nullable=False
    )
    policy_name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Phase 2: ENUM
    coverage_type: Mapped[Optional[CoverageType]] = mapped_column(
        pg_enum(CoverageType, name="coverage_type"), nullable=True
    )
    price_range_min: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    price_range_max: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    source_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("review_sources.id", ondelete="SET NULL")
    )
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    company: Mapped["InsuranceCompany"] = relationship(
        "InsuranceCompany", back_populates="policies"
    )
    # Phase 4: selectin on high-volume history
    quote_history: Mapped[List["InsuranceQuoteHistory"]] = relationship(
        "InsuranceQuoteHistory", back_populates="policy",
        cascade="all, delete-orphan", lazy="selectin"
    )
    competitor_pricings: Mapped[List["CompetitorPricing"]] = relationship(
        "CompetitorPricing", back_populates="policy", lazy="selectin"
    )


class InsuranceQuoteHistory(Base):
    """
    Append-only time-series of quote snapshots per insurance policy.
    Partitioned by scraped_at (yearly RANGE partitioning).
    Phase 3: scraped_at is NOT NULL (partition key).
    """
    __tablename__ = "insurance_quote_history"
    __table_args__ = (
        CheckConstraint("quoted_price > 0", name="chk_quote_price"),
        CheckConstraint("confidence_score BETWEEN 0 AND 1", name="chk_iqh_confidence"),
        CheckConstraint("version >= 1", name="chk_iqh_version"),
        CheckConstraint("char_length(currency) = 3", name="chk_iqh_currency_len"),
        CheckConstraint(
            "valid_to IS NULL OR valid_to >= valid_from",
            name="chk_iqh_valid_dates",
        ),
        Index("idx_iqh_policy_scraped", "policy_id", "scraped_at"),
        Index("idx_iqh_latest", "policy_id", "is_latest",
              postgresql_where=text("is_latest = TRUE")),
        Index("idx_iqh_source", "source_id"),
        {"postgresql_partition_by": "RANGE (scraped_at)",
         "comment": "Append-only quote history - use is_latest=TRUE for current prices."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("insurance_policies.id", ondelete="CASCADE"), nullable=False
    )
    quoted_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    coverage_level: Mapped[Optional[str]] = mapped_column(String(50))
    region: Mapped[Optional[str]] = mapped_column(String(100))
    valid_from: Mapped[Optional[date]] = mapped_column(Date)
    valid_to: Mapped[Optional[date]] = mapped_column(Date)
    source_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("review_sources.id", ondelete="SET NULL")
    )
    confidence_score: Mapped[Optional[float]] = mapped_column(
        Numeric(4, 3),
        comment="Phase 6: 0-1 confidence from source reliability."
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_latest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Phase 3: NOT NULL enforced on partition key
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    superseded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    policy: Mapped["InsurancePolicy"] = relationship(
        "InsurancePolicy", back_populates="quote_history"
    )


class CompetitorPricing(Base):
    """Cross-insurer pricing snapshot for market intelligence comparison."""
    __tablename__ = "competitor_pricings"
    __table_args__ = (
        CheckConstraint("price > 0", name="chk_competitor_price"),
        CheckConstraint("char_length(currency) = 3", name="chk_cp_currency_len"),
        Index("idx_cp_company_date", "company_id", "snapshot_date"),
        Index("idx_cp_policy", "policy_id"),
        Index("idx_cp_coverage", "coverage_type"),
        Index("idx_cp_snapshot", "snapshot_date"),
        Index("idx_cp_source", "source_id"),
        {"comment": "Market-level price snapshots across competitors - used for pricing dashboards."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("insurance_companies.id", ondelete="CASCADE"), nullable=False
    )
    policy_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("insurance_policies.id", ondelete="SET NULL")
    )
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    coverage_type: Mapped[Optional[str]] = mapped_column(String(50))
    region: Mapped[Optional[str]] = mapped_column(String(100))
    source_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("review_sources.id", ondelete="SET NULL")
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Provenance: reference | scraped | imported
    data_origin: Mapped[str] = mapped_column(String(20), nullable=False, default="reference", server_default="reference")

    company: Mapped["InsuranceCompany"] = relationship(
        "InsuranceCompany", back_populates="competitor_pricings"
    )
    policy: Mapped[Optional["InsurancePolicy"]] = relationship(
        "InsurancePolicy", back_populates="competitor_pricings"
    )


# ---------------------------------------------------------------------------
# GROUP E - Customer Feedback
# ---------------------------------------------------------------------------

class ComplaintType(Base):
    """Lookup / seed table of normalized complaint categories (e.g. pricing, claims, reliability)."""
    __tablename__ = "complaint_types"
    __table_args__ = (
        Index("idx_complaint_domain", "domain"),
        {"comment": "Seed table - pre-populated at deployment; referenced by NLP results."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    # Phase 2: ENUM
    domain: Mapped[Optional[EntityDomain]] = mapped_column(
        pg_enum(EntityDomain, name="entity_domain"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    car_nlp_results: Mapped[List["CarReviewNlp"]] = relationship(
        "CarReviewNlp", back_populates="complaint_type"
    )
    insurance_nlp_results: Mapped[List["InsuranceReviewNlp"]] = relationship(
        "InsuranceReviewNlp", back_populates="complaint_type"
    )


class CarReview(Base, TimestampMixin):
    """
    Customer or editorial automotive review per car model.
    Partitioned by scraped_at (yearly). Phase 5: content_hash prevents duplicate ingestion.
    """
    __tablename__ = "car_reviews"
    __table_args__ = (
        CheckConstraint("rating BETWEEN 1.0 AND 5.0", name="chk_car_review_rating"),
        CheckConstraint("confidence_score BETWEEN 0 AND 1", name="chk_car_review_confidence"),
        CheckConstraint("char_length(review_text) > 0", name="chk_car_review_nonempty"),
        Index("idx_cr_model", "model_id"),
        Index("idx_cr_source", "source_id"),
        Index("idx_cr_rating", "rating"),
        Index("idx_cr_date", "review_date"),
        Index("idx_cr_model_scraped", "model_id", "scraped_at"),
        Index("idx_cr_unprocessed", "is_processed",
              postgresql_where=text("is_processed = FALSE")),
        Index("idx_cr_hash", "content_hash"),
        {"postgresql_partition_by": "RANGE (scraped_at)",
         "comment": "Partitioned review archive; content_hash deduplicates re-scrapes."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    model_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("car_models.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("review_sources.id", ondelete="SET NULL")
    )
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[Optional[float]] = mapped_column(Numeric(3, 1))
    review_title: Mapped[Optional[str]] = mapped_column(Text)
    review_text: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[Optional[str]] = mapped_column(String(200))
    review_date: Mapped[Optional[date]] = mapped_column(Date)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confidence_score: Mapped[Optional[float]] = mapped_column(
        Numeric(4, 3), comment="Phase 6: 0-1 score derived from source reliability."
    )
    # Phase 5: SHA-256 of source_url+review_text prevents duplicate ingestion
    content_hash: Mapped[Optional[str]] = mapped_column(
        String(64), unique=True,
        comment="SHA-256 deduplication hash - duplicate rows are rejected on insert."
    )
    # Phase 8: editorial detail
    pros: Mapped[Optional[str]] = mapped_column(Text, comment="Comma-separated list of positive highlights")
    cons: Mapped[Optional[str]] = mapped_column(Text, comment="Comma-separated list of drawbacks")
    variant_tested: Mapped[Optional[str]] = mapped_column(String(200), comment="Specific trim/variant reviewed, e.g. 'XLE V6 AWD'")
    is_processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Phase 3: NOT NULL partition key
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Provenance: reference | scraped | imported
    data_origin: Mapped[str] = mapped_column(String(20), nullable=False, default="reference", server_default="reference")
    # RAG: BGE-base-en-v1.5 embedding stored as JSONB float array (768-dim, L2-normalised)
    embedding: Mapped[Optional[list]] = mapped_column(
        JSONB, nullable=True,
        comment="BAAI/bge-base-en-v1.5 embedding for RAG retrieval (768-dim list, L2-normalised)."
    )

    model: Mapped["CarModel"] = relationship("CarModel", back_populates="reviews")
    source: Mapped[Optional["ReviewSource"]] = relationship(
        "ReviewSource", back_populates="car_reviews"
    )
    nlp_results: Mapped[List["CarReviewNlp"]] = relationship(
        "CarReviewNlp", back_populates="review",
        cascade="all, delete-orphan", lazy="selectin"
    )


class InsuranceReview(Base, TimestampMixin):
    """
    Customer review per insurance company.
    Partitioned by scraped_at (yearly). Phase 5: content_hash prevents duplicate ingestion.
    """
    __tablename__ = "insurance_reviews"
    __table_args__ = (
        CheckConstraint("rating BETWEEN 1.0 AND 5.0", name="chk_insurance_review_rating"),
        CheckConstraint("confidence_score BETWEEN 0 AND 1", name="chk_ir_confidence"),
        CheckConstraint("char_length(review_text) > 0", name="chk_ir_nonempty"),
        Index("idx_ir_company", "company_id"),
        Index("idx_ir_source", "source_id"),
        Index("idx_ir_rating", "rating"),
        Index("idx_ir_date", "review_date"),
        Index("idx_ir_company_scraped", "company_id", "scraped_at"),
        Index("idx_ir_unprocessed", "is_processed",
              postgresql_where=text("is_processed = FALSE")),
        Index("idx_ir_hash", "content_hash"),
        {"postgresql_partition_by": "RANGE (scraped_at)",
         "comment": "Partitioned review archive; content_hash deduplicates re-scrapes."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("insurance_companies.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("review_sources.id", ondelete="SET NULL")
    )
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[Optional[float]] = mapped_column(Numeric(3, 1))
    review_title: Mapped[Optional[str]] = mapped_column(Text)
    review_text: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[Optional[str]] = mapped_column(String(200))
    review_date: Mapped[Optional[date]] = mapped_column(Date)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confidence_score: Mapped[Optional[float]] = mapped_column(Numeric(4, 3))
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), unique=True)
    is_processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Provenance: reference | scraped | imported
    data_origin: Mapped[str] = mapped_column(String(20), nullable=False, default="reference", server_default="reference")
    # RAG: BGE-base-en-v1.5 embedding stored as JSONB float array (768-dim, L2-normalised)
    embedding: Mapped[Optional[list]] = mapped_column(
        JSONB, nullable=True,
        comment="BAAI/bge-base-en-v1.5 embedding for RAG retrieval (768-dim list, L2-normalised)."
    )

    company: Mapped["InsuranceCompany"] = relationship(
        "InsuranceCompany", back_populates="reviews"
    )
    source: Mapped[Optional["ReviewSource"]] = relationship(
        "ReviewSource", back_populates="insurance_reviews"
    )
    nlp_results: Mapped[List["InsuranceReviewNlp"]] = relationship(
        "InsuranceReviewNlp", back_populates="review",
        cascade="all, delete-orphan", lazy="selectin"
    )


class DataQualityLog(Base):
    """Append-only dead-letter log for records rejected during Pydantic validation."""
    __tablename__ = "data_quality_log"
    __table_args__ = (
        Index("idx_dql_task", "scrape_task_id"),
        Index("idx_dql_entity", "entity_type"),
        Index("idx_dql_rejected", "rejected_at"),
        {"comment": "Append-only dead-letter queue - never delete rows; used for data quality audits."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    scrape_task_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scraping_tasks.id", ondelete="SET NULL")
    )
    source_url: Mapped[Optional[str]] = mapped_column(Text)
    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB)
    entity_type: Mapped[Optional[str]] = mapped_column(String(50))
    validation_error: Mapped[str] = mapped_column(Text, nullable=False)
    rejected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ---------------------------------------------------------------------------
# GROUP F - NLP & Sentiment
# ---------------------------------------------------------------------------

class Topic(Base):
    """Topic cluster produced by BERTopic - vocabulary of discovered market topics."""
    __tablename__ = "topics"
    __table_args__ = (
        Index("idx_topics_domain", "domain"),
        Index("idx_topics_model", "model_version"),
        {"comment": "Each row is a BERTopic-discovered topic cluster, versioned per model run."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    topic_label: Mapped[str] = mapped_column(String(200), nullable=False)
    top_words: Mapped[Optional[list]] = mapped_column(ARRAY(Text))
    # Phase 2: ENUM for domain
    domain: Mapped[Optional[EntityDomain]] = mapped_column(
        pg_enum(EntityDomain, name="entity_domain"), nullable=True
    )
    model_version: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    car_nlp_results: Mapped[List["CarReviewNlp"]] = relationship(
        "CarReviewNlp", back_populates="topic"
    )
    insurance_nlp_results: Mapped[List["InsuranceReviewNlp"]] = relationship(
        "InsuranceReviewNlp", back_populates="topic"
    )
    article_nlp_results: Mapped[List["ArticleNlpResult"]] = relationship(
        "ArticleNlpResult", back_populates="topic"
    )


class CarReviewNlp(Base):
    """
    NLP enrichment for a single car review.
    UNIQUE (review_id, model_version) supports re-running with updated NLP models.
    """
    __tablename__ = "car_review_nlp"
    __table_args__ = (
        UniqueConstraint("review_id", "model_version", name="uq_car_nlp_review_model"),
        CheckConstraint("sentiment_score BETWEEN -1.0 AND 1.0", name="chk_car_nlp_score"),
        Index("idx_crnlp_review", "review_id"),
        Index("idx_crnlp_sentiment", "sentiment_label"),
        Index("idx_crnlp_complaint", "complaint_type_id"),
        Index("idx_crnlp_topic", "topic_id"),
        Index("idx_crnlp_topic_processed", "topic_id", "processed_at"),
        {"comment": "One NLP result row per (review, model_version); supports model comparison."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("car_reviews.id", ondelete="CASCADE"), nullable=False
    )
    # Phase 2: ENUM
    sentiment_label: Mapped[Optional[SentimentLabel]] = mapped_column(
        pg_enum(SentimentLabel, name="sentiment_label"), nullable=True
    )
    sentiment_score: Mapped[Optional[float]] = mapped_column(Numeric(6, 4))
    complaint_type_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("complaint_types.id", ondelete="SET NULL")
    )
    topic_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.id", ondelete="SET NULL")
    )
    model_version: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="Phase 6: NLP model version tag, e.g. 'distilbert-v1.2'."
    )
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    review: Mapped["CarReview"] = relationship("CarReview", back_populates="nlp_results")
    complaint_type: Mapped[Optional["ComplaintType"]] = relationship(
        "ComplaintType", back_populates="car_nlp_results"
    )
    topic: Mapped[Optional["Topic"]] = relationship(
        "Topic", back_populates="car_nlp_results"
    )


class InsuranceReviewNlp(Base):
    """NLP enrichment for a single insurance review."""
    __tablename__ = "insurance_review_nlp"
    __table_args__ = (
        UniqueConstraint("review_id", "model_version", name="uq_ins_nlp_review_model"),
        CheckConstraint("sentiment_score BETWEEN -1.0 AND 1.0", name="chk_ins_nlp_score"),
        Index("idx_irnlp_review", "review_id"),
        Index("idx_irnlp_sentiment", "sentiment_label"),
        Index("idx_irnlp_complaint", "complaint_type_id"),
        Index("idx_irnlp_topic", "topic_id"),
        Index("idx_irnlp_topic_processed", "topic_id", "processed_at"),
        {"comment": "One NLP result row per (review, model_version); supports model comparison."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("insurance_reviews.id", ondelete="CASCADE"), nullable=False
    )
    # Phase 2: ENUM
    sentiment_label: Mapped[Optional[SentimentLabel]] = mapped_column(
        pg_enum(SentimentLabel, name="sentiment_label"), nullable=True
    )
    sentiment_score: Mapped[Optional[float]] = mapped_column(Numeric(6, 4))
    complaint_type_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("complaint_types.id", ondelete="SET NULL")
    )
    topic_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.id", ondelete="SET NULL")
    )
    model_version: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="Phase 6: NLP model version tag."
    )
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    review: Mapped["InsuranceReview"] = relationship(
        "InsuranceReview", back_populates="nlp_results"
    )
    complaint_type: Mapped[Optional["ComplaintType"]] = relationship(
        "ComplaintType", back_populates="insurance_nlp_results"
    )
    topic: Mapped[Optional["Topic"]] = relationship(
        "Topic", back_populates="insurance_nlp_results"
    )


class ArticleNlpResult(Base):
    """NLP enrichment for a market trend article."""
    __tablename__ = "article_nlp_results"
    __table_args__ = (
        UniqueConstraint("article_id", "model_version", name="uq_anr_article_model"),
        CheckConstraint("sentiment_score BETWEEN -1.0 AND 1.0", name="chk_anr_sentiment_score"),
        Index("idx_anr_article", "article_id"),
        Index("idx_anr_sentiment", "sentiment_label"),
        Index("idx_anr_topic", "topic_id"),
        Index("idx_anr_topic_processed", "topic_id", "processed_at"),
        {"comment": "One NLP result per (article, model_version)."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("market_trend_articles.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Phase 2: ENUM
    sentiment_label: Mapped[Optional[SentimentLabel]] = mapped_column(
        pg_enum(SentimentLabel, name="sentiment_label"), nullable=True
    )
    sentiment_score: Mapped[Optional[float]] = mapped_column(Numeric(6, 4))
    topic_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.id", ondelete="SET NULL")
    )
    summary_text: Mapped[Optional[str]] = mapped_column(Text)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    article: Mapped["MarketTrendArticle"] = relationship(
        "MarketTrendArticle", back_populates="nlp_results"
    )
    topic: Mapped[Optional["Topic"]] = relationship(
        "Topic", back_populates="article_nlp_results"
    )


# ---------------------------------------------------------------------------
# GROUP G - Keywords
# ---------------------------------------------------------------------------

class Keyword(Base):
    """Vocabulary of extracted keywords, organized by domain."""
    __tablename__ = "keywords"
    __table_args__ = (
        Index("idx_keywords_domain", "domain"),
        {"comment": "Keyword vocabulary - terms extracted from reviews and articles by NLP pipeline."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    term: Mapped[str] = mapped_column(
        String(200), nullable=False, unique=True,
        comment="Normalized keyword term (lowercase, stripped)."
    )
    # Phase 2: ENUM
    domain: Mapped[Optional[EntityDomain]] = mapped_column(
        pg_enum(EntityDomain, name="entity_domain"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    review_keywords: Mapped[List["ReviewKeyword"]] = relationship(
        "ReviewKeyword", back_populates="keyword", cascade="all, delete-orphan"
    )


class ReviewKeyword(Base):
    """
    Many-to-many join between keywords and reviews/articles.
    review_type distinguishes 'car', 'insurance', 'article'.
    """
    __tablename__ = "review_keywords"
    __table_args__ = (
        UniqueConstraint(
            "keyword_id", "review_id", "review_type", name="uq_review_keyword"
        ),
        CheckConstraint("score BETWEEN 0 AND 1", name="chk_kw_score"),
        Index("idx_rk_keyword", "keyword_id"),
        # Phase 1: composite analytics index
        Index("idx_rk_entity", "review_type", "review_id"),
        Index("idx_rk_score", "score"),
        {"comment": "Join table connecting keywords to any review type; score = TF-IDF or similar."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    keyword_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("keywords.id", ondelete="CASCADE"), nullable=False
    )
    review_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    # Phase 2: ENUM
    review_type: Mapped[ReviewType] = mapped_column(
        pg_enum(ReviewType, name="review_type"), nullable=False
    )
    score: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    keyword: Mapped["Keyword"] = relationship("Keyword", back_populates="review_keywords")


# ---------------------------------------------------------------------------
# GROUP H - Market Intelligence
# ---------------------------------------------------------------------------

class MarketTrendArticle(Base, TimestampMixin):
    """Scraped industry news or trend article - automotive and insurance intelligence."""
    __tablename__ = "market_trend_articles"
    __table_args__ = (
        CheckConstraint("confidence_score BETWEEN 0 AND 1", name="chk_mta_confidence"),
        Index("idx_mta_source", "source_id"),
        Index("idx_mta_pub_date", "publication_date"),
        Index("idx_mta_scraped", "scraped_at"),
        Index("idx_mta_hash", "content_hash"),
        Index("idx_mta_unprocessed", "is_processed",
              postgresql_where=text("is_processed = FALSE")),
        {"comment": "News and trend article archive; content_hash deduplicates re-scrapes."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    source_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("review_sources.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    author: Mapped[Optional[str]] = mapped_column(String(200))
    publication_date: Mapped[Optional[date]] = mapped_column(Date)
    body_text: Mapped[Optional[str]] = mapped_column(Text)
    tags: Mapped[Optional[list]] = mapped_column(ARRAY(Text))
    # Phase 8: content classification
    category: Mapped[Optional[str]] = mapped_column(String(60), comment="e.g. 'EV', 'Market', 'Sales', 'Technology', 'Regulation'")
    region: Mapped[Optional[str]] = mapped_column(String(100), comment="Geographic focus of the article")
    content_hash: Mapped[Optional[str]] = mapped_column(
        String(64), unique=True,
        comment="SHA-256 deduplication hash."
    )
    is_processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confidence_score: Mapped[Optional[float]] = mapped_column(
        Numeric(4, 3), comment="Phase 6: 0-1 source reliability score."
    )
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Provenance: reference | scraped | imported
    data_origin: Mapped[str] = mapped_column(String(20), nullable=False, default="reference", server_default="reference")
    # RAG: BGE-base-en-v1.5 embedding stored as JSONB float array (768-dim, L2-normalised)
    embedding: Mapped[Optional[list]] = mapped_column(
        JSONB, nullable=True,
        comment="BAAI/bge-base-en-v1.5 embedding for RAG retrieval (768-dim list, L2-normalised)."
    )

    source: Mapped[Optional["ReviewSource"]] = relationship(
        "ReviewSource", back_populates="market_trend_articles"
    )
    nlp_results: Mapped[List["ArticleNlpResult"]] = relationship(
        "ArticleNlpResult", back_populates="article",
        cascade="all, delete-orphan", lazy="selectin"
    )


# ---------------------------------------------------------------------------
# GROUP I - Analytics & KPIs
# ---------------------------------------------------------------------------

class KpiMetric(Base):
    """
    Append-only time-series table for all computed KPIs.
    Partitioned by computed_at (yearly RANGE partitioning).
    Phase 3: computed_at is NOT NULL and is the partition key.
    """
    __tablename__ = "kpi_metrics"
    __table_args__ = (
        CheckConstraint("char_length(kpi_name) > 0", name="chk_kpi_name_nonempty"),
        CheckConstraint("char_length(entity_type) > 0", name="chk_kpi_entity_nonempty"),
        # Phase 1: composite analytics indexes
        Index("idx_kpi_name_computed", "kpi_name", "computed_at"),
        Index("idx_kpi_entity", "entity_type", "entity_id"),
        Index("idx_kpi_granularity", "granularity"),
        {"postgresql_partition_by": "RANGE (computed_at)",
         "comment": "Append-only KPI warehouse - partitioned yearly; never UPDATE rows."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    kpi_name: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="e.g. 'avg_rating', 'brand_sentiment_score', 'market_share'."
    )
    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="Domain entity referencing this KPI, e.g. 'car_model', 'insurance_company'."
    )
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    value: Mapped[float] = mapped_column(Numeric(16, 6), nullable=False)
    # Phase 2: ENUM for granularity
    granularity: Mapped[KpiGranularity] = mapped_column(
        pg_enum(KpiGranularity, name="kpi_granularity"),
        nullable=False, default=KpiGranularity.DAILY
    )
    # Phase 3: NOT NULL on partition key
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # NOTE: 'metadata' is reserved by SQLAlchemy - use extra_metadata instead
    extra_metadata: Mapped[Optional[dict]] = mapped_column(
        "metadata",  # maps to the 'metadata' column in PostgreSQL
        JSONB, comment="Optional extra context: filters, model version, formula used."
    )




class OpportunitySignal(Base, TimestampMixin):
    """
    Sales opportunity score per entity (InsuranceCompany or CarBrand).

    A high overall_score (0–100) means the entity shows public signs of needing
    better software — complaints, dropping satisfaction, low review visibility —
    making it a strong TEAMWILL sales target.

    Computed by ``analytics.opportunity_scorer.compute_opportunity_signals()``.
    """
    __tablename__ = "opportunity_signals"
    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", name="uq_oppsig_entity"),
        CheckConstraint("overall_score BETWEEN 0 AND 100", name="chk_oppsig_overall"),
        CheckConstraint("complaint_score BETWEEN 0 AND 100", name="chk_oppsig_complaint"),
        CheckConstraint("sentiment_drop_score BETWEEN 0 AND 100", name="chk_oppsig_sentiment"),
        CheckConstraint("review_volume_score BETWEEN 0 AND 100", name="chk_oppsig_volume"),
        Index("idx_oppsig_type_score", "entity_type", "overall_score"),
        Index("idx_oppsig_region", "region"),
        Index("idx_oppsig_strength", "signal_strength"),
        {"comment": "Opportunity scores for TEAMWILL sales targeting — higher = more likely to need ERP."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    entity_name: Mapped[str] = mapped_column(String(200), nullable=False)
    region: Mapped[Optional[str]] = mapped_column(String(20))

    overall_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    complaint_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    sentiment_drop_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    review_volume_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)

    top_complaint_types: Mapped[Optional[list]] = mapped_column(ARRAY(String))
    score_reasoning: Mapped[Optional[dict]] = mapped_column(JSONB)
    signal_strength: Mapped[str] = mapped_column(String(20), nullable=False)
    sector_percentile: Mapped[Optional[int]] = mapped_column(
        SmallInteger,
        comment="Distress percentile within sector (0-100). 100 = most distressed.",
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # V2 four-axis scorer columns — populated by analytics.v2_opportunity_scorer
    v2_pain_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    v2_recovery_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    v2_erp_fit_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    v2_reachability_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    v2_overall_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    v2_tier: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    v2_reasoning: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    v2_computed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    intervention_brief: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)


class BrandReputationScore(Base):
    """
    Monthly aggregated reputation score per car brand.

    Computed by ``analytics.aggregators.compute_brand_reputation()``.
    One row per (brand_id, period_date); upserted on every analytics run.
    ``period_date`` is always the first calendar day of the month.
    """
    __tablename__ = "brand_reputation_scores"
    __table_args__ = (
        UniqueConstraint("brand_id", "period_date", "data_origin", name="uq_brs_brand_period_origin"),
        CheckConstraint("review_count >= 0", name="chk_brs_review_count"),
        Index("idx_brs_brand", "brand_id"),
        Index("idx_brs_period", "period_date"),
        Index("idx_brs_brand_period", "brand_id", "period_date"),
        Index("idx_brs_origin", "data_origin"),
        {"comment": "Monthly brand reputation scores — upserted on each analytics run."},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=new_uuid
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("car_brands.id", ondelete="CASCADE"),
        nullable=False,
    )
    period_date: Mapped[date] = mapped_column(
        Date, nullable=False,
        comment="First day of the calendar month this score covers.",
    )
    avg_rating: Mapped[Optional[float]] = mapped_column(
        Numeric(4, 2),
        comment="Mean star rating (1–5) across all reviews for this brand/period.",
    )
    avg_sentiment_score: Mapped[Optional[float]] = mapped_column(
        Numeric(6, 4),
        comment="Mean NLP sentiment score (−1.0 to 1.0) for this brand/period.",
    )
    review_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Total number of reviews included in this aggregation.",
    )
    data_origin: Mapped[str] = mapped_column(
        String(20), nullable=False, default="all", server_default="all",
        comment="Provenance filter: all | reference | scraped",
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
        comment="Timestamp of the analytics run that produced this row.",
    )


class SentimentTrend(Base):
    """
    Monthly breakdown of positive / neutral / negative review counts per brand.

    Paired with ``BrandReputationScore`` for trend-line visualisation.
    One row per (brand_id, period_date); upserted on every analytics run.
    """
    __tablename__ = "sentiment_trends"
    __table_args__ = (
        UniqueConstraint("brand_id", "period_date", "data_origin", name="uq_st_brand_period_origin"),
        CheckConstraint("positive_count >= 0", name="chk_st_positive"),
        CheckConstraint("neutral_count  >= 0", name="chk_st_neutral"),
        CheckConstraint("negative_count >= 0", name="chk_st_negative"),
        Index("idx_st_brand", "brand_id"),
        Index("idx_st_period", "period_date"),
        Index("idx_st_brand_period", "brand_id", "period_date"),
        Index("idx_st_origin", "data_origin"),
        {"comment": "Monthly sentiment distribution per brand — upserted on each analytics run."},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=new_uuid
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("car_brands.id", ondelete="CASCADE"),
        nullable=False,
    )
    period_date: Mapped[date] = mapped_column(Date, nullable=False)
    positive_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    neutral_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    negative_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_sentiment_score: Mapped[Optional[float]] = mapped_column(
        Numeric(6, 4),
        comment="Mean NLP sentiment score (−1.0 to 1.0) for this brand/period.",
    )
    data_origin: Mapped[str] = mapped_column(
        String(20), nullable=False, default="all", server_default="all",
        comment="Provenance filter: all | reference | scraped",
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )


# ---------------------------------------------------------------------------
# GROUP H — Keyword Monitoring
# ---------------------------------------------------------------------------

class SearchKeyword(Base, TimestampMixin):
    """User-defined keywords for automated article discovery via RSS search."""
    __tablename__ = "search_keywords"
    __table_args__ = (
        Index("idx_sk_active", "is_active", postgresql_where=text("is_active = TRUE")),
        {"comment": "Keywords monitored for automated article discovery."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    keyword: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    region: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_searched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    results_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))


# ---------------------------------------------------------------------------
# ERP Vendor Intelligence
# ---------------------------------------------------------------------------

class ErpVendor(Base, TimestampMixin):
    """ERP vendors active in insurance/automotive markets — TEAMWILL's competitive landscape."""
    __tablename__ = "erp_vendors"
    __table_args__ = (
        Index("idx_erp_vendor_sector", "target_sector"),
        Index("idx_erp_vendor_region", "target_region"),
        {"comment": "ERP vendor competitive intelligence for TEAMWILL market positioning."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    target_sector: Mapped[str] = mapped_column(String(50), nullable=False, comment="insurance, automotive, both")
    target_region: Mapped[str] = mapped_column(String(50), nullable=False, comment="TN, EU, MENA, global")
    website: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    data_origin: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'reference'"))


# ---------------------------------------------------------------------------
# ML Clustering
# ---------------------------------------------------------------------------

class MlModelMetric(Base):
    """Quality metrics and evaluation parameters for tracked ML Models (KMeans)."""
    __tablename__ = "ml_model_metrics"
    __table_args__ = (
        Index("idx_mlmm_model", "model_name"),
        {"comment": "Stores analytical metrics like Silhouette score, Davies-Bouldin, and bootstrap stability per ML model run."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False, default="kmeans_clustering")
    silhouette_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 4), nullable=True)
    davies_bouldin_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 4), nullable=True)
    inertia: Mapped[Optional[float]] = mapped_column(Numeric(15, 4), nullable=True)
    k_value: Mapped[int] = mapped_column(Integer, nullable=False)
    n_companies: Mapped[int] = mapped_column(Integer, nullable=False)
    cluster_stability_json: Mapped[Optional[dict]] = mapped_column(
        JSONB, comment="Bootstrap stability percentages per company { company_id: stability_pct }."
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MlClusterMetadata(Base):
    """Metadata for each KMeans cluster — labels, colors, stats."""
    __tablename__ = "ml_cluster_metadata"
    __table_args__ = (
        Index("idx_mlcm_cluster", "cluster_id"),
        {"comment": "One row per KMeans cluster with label, ERP module, and summary stats."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    cluster_id: Mapped[int] = mapped_column(Integer, nullable=False)
    cluster_label: Mapped[str] = mapped_column(String(100), nullable=False)
    erp_module: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    avg_negative_pct: Mapped[Optional[float]] = mapped_column(Numeric(6, 2), nullable=True)
    avg_review_count: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    company_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    color_hex: Mapped[str] = mapped_column(String(7), nullable=False, default="#888888")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

# ---------------------------------------------------------------------------
# GROUP E - Authentication
# ---------------------------------------------------------------------------

class User(Base, TimestampMixin):
    """User table for authentication and access control."""
    __tablename__ = "users"
    __table_args__ = (
        Index("idx_users_email", "email"),
        {"comment": "User accounts with OTP verification."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    verification_code: Mapped[Optional[str]] = mapped_column(String(10))
    code_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

# ---------------------------------------------------------------------------
# Public export - import all models from one location
# ---------------------------------------------------------------------------
__all__ = [
    # Scraping infrastructure
    "ScrapingTask", "ScrapingRun", "ScrapingError",
    "ScraperHealthMetric", "PipelineRun",
    # Raw Data Storage
    "RawPage", "RawApiResponse", "RawScrapeLog",
    # Automotive
    "ReviewSource", "CarBrand", "CarModel",
    "CarListing", "CarPriceHistory",
    # Insurance
    "InsuranceCompany", "InsurancePolicy",
    "InsuranceQuoteHistory", "CompetitorPricing",
    # Feedback
    "ComplaintType", "CarReview", "InsuranceReview", "DataQualityLog",
    # NLP
    "Topic", "CarReviewNlp", "InsuranceReviewNlp", "ArticleNlpResult",
    # Keywords
    "Keyword", "ReviewKeyword",
    # Market Intelligence
    "MarketTrendArticle",
    # Analytics
    "KpiMetric", "BrandReputationScore", "SentimentTrend",
    # Opportunity Scoring
    "OpportunitySignal",
    # Keyword Monitoring
    "SearchKeyword",
    # ML Evaluation
    "MlModelMetric",
    # ML Clustering
    "MlClusterMetadata",
    # Auth
    "User",
]
