"""Parser pipeline orchestration from raw_pages to structured domain tables."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from parsers.html_cleaner import clean_html
from parsers.dom_extractor import extract_dom
from parsers.schema_extractor import extract_from_schema, map_to_schema
from parsers.llm_extractor import extract_with_llm
from parsers.normalizer import normalize_record
from parsers.validator import validate_record
from parsers.deduplicator import compute_content_hash, deduplicate_record

from database.enums import PipelineStatus
from database.models import (
    CarBrand,
    CarListing,
    CarModel,
    CarReview,
    CompetitorPricing,
    DataQualityLog,
    InsuranceCompany,
    InsuranceReview,
    MarketTrendArticle,
    PipelineRun,
    RawPage,
    ReviewSource,
    ScrapingError,
    ScrapingRun,
)

logger = logging.getLogger("parsers.automotive_pipeline")


class ParserPipeline:
    """Batch parser pipeline with resilient per-page processing."""

    def __init__(self, session: Session, enable_llm: bool = False):
        self.session = session
        self.enable_llm = enable_llm

    def process_raw_page(self, raw_page: RawPage) -> Dict[str, Any]:
        """Process one raw page through full parser stages."""
        if not raw_page.raw_html:
            self._log_data_quality(raw_page, "unknown", "raw_html is empty", {})
            raw_page.parse_error = "raw_html is empty"
            raw_page.is_parsed = True
            return {"status": "rejected", "reason": "raw_html is empty"}

        clean_text, stripped_html = clean_html(raw_page.raw_html)
        dom_data = extract_dom(stripped_html, raw_page.source_url)
        schema_entities = extract_from_schema(raw_page.raw_html)
        mapped = map_to_schema(dom_data, schema_entities, raw_page.source_url)

        if self.enable_llm and (not dom_data.get("title") or not dom_data.get("body_text")):
            llm_data = extract_with_llm(clean_text) or {}
            if llm_data.get("summary") and not mapped["record"].get("body_text"):
                mapped["record"]["body_text"] = llm_data.get("summary")
            if llm_data.get("vehicle_brand") and not mapped["record"].get("brand"):
                mapped["record"]["brand"] = llm_data.get("vehicle_brand")
            if llm_data.get("vehicle_model") and not mapped["record"].get("model"):
                mapped["record"]["model"] = llm_data.get("vehicle_model")
            if llm_data.get("rating") and not mapped["record"].get("rating"):
                mapped["record"]["rating"] = llm_data.get("rating")

        normalized = normalize_record(mapped["record"])

        is_valid, reason = validate_record(normalized)
        if not is_valid:
            self._log_data_quality(raw_page, mapped["entity_type"], reason, normalized)
            raw_page.parse_error = reason
            raw_page.is_parsed = True
            return {"status": "rejected", "reason": reason, "entity_type": mapped["entity_type"]}

        duplicate = self._is_duplicate(mapped["entity_type"], normalized)
        if duplicate:
            raw_page.parse_error = "duplicate record"
            raw_page.is_parsed = True
            return {"status": "duplicate", "entity_type": mapped["entity_type"]}

        self._store_record(mapped["entity_type"], normalized)
        raw_page.parse_error = None
        raw_page.is_parsed = True
        return {"status": "stored", "entity_type": mapped["entity_type"]}

    def process_batch(self, limit: int = 100) -> Dict[str, Any]:
        """Process unparsed raw pages in batches and persist pipeline metrics."""
        started = datetime.now(timezone.utc)
        metrics = {
            "pages_processed": 0,
            "records_extracted": 0,
            "records_rejected": 0,
            "duplicates_detected": 0,
            "processing_time_seconds": 0.0,
        }

        pipeline_run = PipelineRun(
            task_name="parser_pipeline_batch",
            started_at=started,
            status=PipelineStatus.RUNNING,
            records_scraped=0,
            records_stored=0,
        )
        self.session.add(pipeline_run)
        self.session.flush()

        pages = (
            self.session.query(RawPage)
            .filter(RawPage.is_parsed.is_(False))
            .order_by(RawPage.scraped_at.asc())
            .limit(limit)
            .all()
        )

        for page in pages:
            metrics["pages_processed"] += 1
            page_id = page.id
            page_source_url = page.source_url
            page_task_id = page.scrape_task_id
            try:
                result = self.process_raw_page(page)
                status = result.get("status")
                if status == "stored":
                    metrics["records_extracted"] += 1
                elif status == "duplicate":
                    metrics["duplicates_detected"] += 1
                else:
                    metrics["records_rejected"] += 1
                self.session.flush()
            except Exception as exc:
                metrics["records_rejected"] += 1
                self.session.rollback()

                page_for_update = self.session.get(RawPage, page_id)
                if page_for_update is not None:
                    page_for_update.parse_error = str(exc)

                self._log_scraping_error(
                    page_id=page_id,
                    source_url=page_source_url,
                    scrape_task_id=page_task_id,
                    exc=exc,
                )
                logger.exception("Failed parsing raw_page id=%s", page.id)
                self.session.flush()

        finished = datetime.now(timezone.utc)
        metrics["processing_time_seconds"] = (finished - started).total_seconds()

        pipeline_run.finished_at = finished
        pipeline_run.records_scraped = metrics["pages_processed"]
        pipeline_run.records_stored = metrics["records_extracted"]
        pipeline_run.error_message = (
            f"rejected={metrics['records_rejected']};"
            f"duplicates={metrics['duplicates_detected']};"
            f"processing_time_seconds={metrics['processing_time_seconds']:.3f}"
        )

        if metrics["records_rejected"] == 0:
            pipeline_run.status = PipelineStatus.SUCCESS
        elif metrics["records_extracted"] > 0:
            pipeline_run.status = PipelineStatus.PARTIAL
        else:
            pipeline_run.status = PipelineStatus.FAILED

        self.session.commit()
        return metrics

    def process_page(self, raw_html: str, source_url: str) -> Dict[str, Any]:
        """Backward-compatible single-page helper used by previous callers."""
        temp = RawPage(source_url=source_url, raw_html=raw_html, is_parsed=False)
        return self.process_raw_page(temp)

    def _is_duplicate(self, entity_type: str, record: Dict[str, Any]) -> bool:
        title = record.get("title")
        source_url = record.get("source_url") or ""
        content_hash = compute_content_hash(record.get("brand"), record.get("model"), source_url)

        if entity_type == "car_listing":
            # CarListing has a UNIQUE constraint on listing_url — use that directly.
            return (
                self.session.query(CarListing)
                .filter_by(listing_url=source_url)
                .first()
            ) is not None

        if entity_type == "competitor_pricing":
            # CompetitorPricing is an append-only time-series snapshot table.
            # Never skip an insert — always return False.
            return False

        if entity_type == "car_review":
            table_class = CarReview
        elif entity_type == "insurance_review":
            table_class = InsuranceReview
        else:
            table_class = MarketTrendArticle

        return deduplicate_record(
            session=self.session,
            table_class=table_class,
            source_url=source_url,
            title=title,
            content_hash=content_hash,
        )

    def _store_record(self, entity_type: str, record: Dict[str, Any]) -> None:
        source = self._get_or_create_source(record["source_url"])
        content_hash = compute_content_hash(record.get("brand"), record.get("model"), record["source_url"])

        if entity_type == "car_review":
            model = self._get_or_create_car_model(record.get("brand"), record.get("model"))
            row = CarReview(
                model_id=model.id,
                source_id=source.id,
                source_url=record["source_url"],
                review_title=record.get("title"),
                review_text=record.get("body_text") or "No content",
                author=record.get("author"),
                review_date=record.get("publish_date"),
                rating=record.get("rating"),
                content_hash=content_hash,
                is_processed=False,
            )
        elif entity_type == "insurance_review":
            company = self._get_or_create_insurance_company(record.get("brand") or record.get("product_name"))
            row = InsuranceReview(
                company_id=company.id,
                source_id=source.id,
                source_url=record["source_url"],
                review_title=record.get("title"),
                review_text=record.get("body_text") or "No content",
                author=record.get("author"),
                review_date=record.get("publish_date"),
                rating=record.get("rating"),
                content_hash=content_hash,
                is_processed=False,
            )
        elif entity_type == "car_listing":
            model = self._get_or_create_car_model(record.get("brand"), record.get("model"))
            raw_price = record.get("listing_price")
            listed_price = float(raw_price) if raw_price is not None else None
            row = CarListing(
                model_id=model.id,
                source_id=source.id,
                listing_url=record["source_url"],
                dealer_name=(record.get("dealer_name") or record.get("author") or "")[:200] or None,
                listed_price=listed_price,
                currency=record.get("currency") or "EUR",
                city=(record.get("city") or "")[:100] or None,
                country=(record.get("country") or "")[:100] or None,
                listed_at=record.get("publish_date"),
                mileage_km=record.get("mileage_km"),
                is_active=True,
            )
        elif entity_type == "competitor_pricing":
            company = self._get_or_create_insurance_company(
                record.get("brand") or record.get("product_name") or record.get("title")
            )
            raw_price = record.get("listing_price") or record.get("rating")
            price = float(raw_price) if raw_price is not None else None
            if not price or price <= 0:
                raise ValueError("competitor_pricing record has no valid price — skipping")
            snapshot_date = record.get("publish_date") or datetime.now(timezone.utc).date()
            row = CompetitorPricing(
                company_id=company.id,
                source_id=source.id,
                price=price,
                currency=record.get("currency") or "EUR",
                coverage_type=(record.get("coverage_type") or "")[:50] or None,
                region=(record.get("region") or "")[:100] or None,
                snapshot_date=snapshot_date,
            )
        else:
            row = MarketTrendArticle(
                source_id=source.id,
                title=record.get("title") or "Untitled",
                source_url=record["source_url"],
                author=record.get("author"),
                publication_date=record.get("publish_date"),
                body_text=record.get("body_text"),
                content_hash=content_hash,
                is_processed=False,
            )

        self.session.add(row)
        self.session.flush()

    def _get_or_create_source(self, source_url: str) -> ReviewSource:
        parsed = urlparse(source_url)
        base = parsed.netloc or source_url
        source = self.session.query(ReviewSource).filter_by(base_url=base).first()
        if source:
            return source

        source = ReviewSource(name=base, base_url=base)
        self.session.add(source)
        self.session.flush()
        return source

    def _get_or_create_car_model(self, brand_name: Optional[str], model_name: Optional[str]) -> CarModel:
        brand_name = (brand_name or "Unknown Brand")[:100]
        model_name = (model_name or "Unknown Model")[:150]

        brand = self.session.query(CarBrand).filter_by(name=brand_name).first()
        if not brand:
            brand = CarBrand(name=brand_name)
            self.session.add(brand)
            self.session.flush()

        model = (
            self.session.query(CarModel)
            .filter_by(brand_id=brand.id, name=model_name, year=datetime.now().year)
            .first()
        )
        if model:
            return model

        model = CarModel(brand_id=brand.id, name=model_name, year=datetime.now().year)
        self.session.add(model)
        self.session.flush()
        return model

    def _get_or_create_insurance_company(self, company_name: Optional[str]) -> InsuranceCompany:
        name = (company_name or "Unknown Insurance")[:150]
        company = self.session.query(InsuranceCompany).filter_by(name=name).first()
        if company:
            return company

        company = InsuranceCompany(name=name)
        self.session.add(company)
        self.session.flush()
        return company

    def _log_data_quality(self, raw_page: RawPage, entity_type: str, reason: str, payload: Dict[str, Any]) -> None:
        self.session.add(
            DataQualityLog(
                scrape_task_id=raw_page.scrape_task_id,
                source_url=raw_page.source_url,
                raw_data=payload,
                entity_type=entity_type,
                validation_error=reason,
            )
        )

    def _log_scraping_error(self, page_id, source_url: str, scrape_task_id, exc: Exception) -> None:
        if not scrape_task_id:
            logger.warning("Cannot persist scraping_errors row for raw_page=%s without scrape_task_id", page_id)
            return

        run = (
            self.session.query(ScrapingRun)
            .filter(ScrapingRun.task_id == scrape_task_id)
            .order_by(ScrapingRun.created_at.desc())
            .first()
        )
        if run is None:
            logger.warning("No ScrapingRun found for task_id=%s", scrape_task_id)
            return

        self.session.add(
            ScrapingError(
                run_id=run.id,
                task_id=scrape_task_id,
                error_type=type(exc).__name__,
                error_message=str(exc),
                stack_trace=None,
                target_url=source_url,
                is_retryable=True,
            )
        )


class AutomotivePipeline(ParserPipeline):
    """Backward-compatible alias to preserve existing imports."""

    def process_page(self, raw_html: str, source_url: str) -> Dict[str, Any]:
        """
        Processes a single raw page into structured automotive intelligence.
        """
        # 1. Clean HTML
        clean_text, stripped_html = clean_html(raw_html)
        if not clean_text:
            return {"status": "error", "reason": "empty_text"}

        # 2. Extract
        dom_data = extract_from_dom(stripped_html, source_url)
        schema_data = extract_from_schema(raw_html)
        llm_data = extract_with_llm(clean_text)

        # 3. Merge & Normalise
        raw_merged = merge_extractions(schema_data, dom_data, llm_data)
        normalised = normalise_results(raw_merged, source_url)

        # 4. Validate
        is_valid, reason = validate(normalised)
        if not is_valid:
            return {"status": "invalid", "reason": reason}

        return {"status": "success", "data": normalised}
