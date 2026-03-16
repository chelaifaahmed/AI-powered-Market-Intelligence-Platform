"""NLP orchestration pipeline for structured automotive intelligence records."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy import exists
from sqlalchemy.orm import Session

from database.enums import EntityDomain, SentimentLabel
from database.models import (
    ArticleNlpResult,
    CarReview,
    CarReviewNlp,
    ComplaintType,
    InsuranceReview,
    InsuranceReviewNlp,
    MarketTrendArticle,
    Topic,
)
from nlp.complaint_classifier import classify_complaints
from nlp.keyword_extractor import extract_keywords
from nlp.sentiment_analyzer import analyze_sentiment
from nlp.topic_classifier import classify_topics

logger = logging.getLogger("nlp.pipeline")

_MODEL_VERSION = "rule-nlp-v1"


class NlpPipeline:
    """Production-safe NLP pipeline for reviews and articles."""

    def __init__(self, session: Session, model_version: str = _MODEL_VERSION):
        self.session = session
        self.model_version = model_version

    def process_car_reviews(self, limit: int = 100) -> Dict[str, float]:
        started = datetime.now(timezone.utc)
        metrics = {
            "records_processed": 0,
            "records_failed": 0,
            "records_skipped": 0,
            "processing_time_seconds": 0.0,
        }

        rows = (
            self.session.query(CarReview)
            .filter(~exists().where(CarReviewNlp.review_id == CarReview.id))
            .order_by(CarReview.scraped_at.asc())
            .limit(limit)
            .all()
        )

        for review in rows:
            try:
                text = f"{review.review_title or ''} {review.review_text or ''}".strip()
                if not text:
                    metrics["records_skipped"] += 1
                    continue
                sentiment_label, sentiment_score = analyze_sentiment(text)
                topics = classify_topics(text)
                keywords = extract_keywords(text, limit=10)
                complaints = classify_complaints(text)

                topic = self._get_or_create_topic(topics[0], EntityDomain.AUTOMOTIVE)
                complaint = self._get_or_create_complaint(complaints[0], EntityDomain.AUTOMOTIVE) if complaints else None

                row = CarReviewNlp(
                    review_id=review.id,
                    sentiment_label=SentimentLabel[sentiment_label.upper()],
                    sentiment_score=Decimal(f"{sentiment_score:.4f}"),
                    complaint_type_id=complaint.id if complaint else None,
                    topic_id=topic.id if topic else None,
                    model_version=self.model_version,
                )
                self.session.add(row)
                self.session.flush()
                logger.info(
                    "NLP car_review processed id=%s sentiment=%s topics=%s keywords=%s",
                    review.id,
                    sentiment_label,
                    topics,
                    keywords,
                )
                metrics["records_processed"] += 1
            except Exception:
                self.session.rollback()
                logger.exception("Failed NLP processing for car_review id=%s", review.id)
                metrics["records_failed"] += 1

        self.session.commit()
        metrics["processing_time_seconds"] = (datetime.now(timezone.utc) - started).total_seconds()
        return metrics

    def process_insurance_reviews(self, limit: int = 100) -> Dict[str, float]:
        started = datetime.now(timezone.utc)
        metrics = {
            "records_processed": 0,
            "records_failed": 0,
            "records_skipped": 0,
            "processing_time_seconds": 0.0,
        }

        rows = (
            self.session.query(InsuranceReview)
            .filter(~exists().where(InsuranceReviewNlp.review_id == InsuranceReview.id))
            .order_by(InsuranceReview.scraped_at.asc())
            .limit(limit)
            .all()
        )

        for review in rows:
            try:
                text = f"{review.review_title or ''} {review.review_text or ''}".strip()
                if not text:
                    metrics["records_skipped"] += 1
                    continue
                sentiment_label, sentiment_score = analyze_sentiment(text)
                topics = classify_topics(text)
                keywords = extract_keywords(text, limit=10)
                complaints = classify_complaints(text)

                topic = self._get_or_create_topic(topics[0], EntityDomain.INSURANCE)
                complaint = self._get_or_create_complaint(complaints[0], EntityDomain.INSURANCE) if complaints else None

                row = InsuranceReviewNlp(
                    review_id=review.id,
                    sentiment_label=SentimentLabel[sentiment_label.upper()],
                    sentiment_score=Decimal(f"{sentiment_score:.4f}"),
                    complaint_type_id=complaint.id if complaint else None,
                    topic_id=topic.id if topic else None,
                    model_version=self.model_version,
                )
                self.session.add(row)
                self.session.flush()
                logger.info(
                    "NLP insurance_review processed id=%s sentiment=%s topics=%s keywords=%s",
                    review.id,
                    sentiment_label,
                    topics,
                    keywords,
                )
                metrics["records_processed"] += 1
            except Exception:
                self.session.rollback()
                logger.exception("Failed NLP processing for insurance_review id=%s", review.id)
                metrics["records_failed"] += 1

        self.session.commit()
        metrics["processing_time_seconds"] = (datetime.now(timezone.utc) - started).total_seconds()
        return metrics

    def process_articles(self, limit: int = 100) -> Dict[str, float]:
        started = datetime.now(timezone.utc)
        metrics = {
            "records_processed": 0,
            "records_failed": 0,
            "records_skipped": 0,
            "processing_time_seconds": 0.0,
        }

        rows = (
            self.session.query(MarketTrendArticle)
            .filter(~exists().where(ArticleNlpResult.article_id == MarketTrendArticle.id))
            .order_by(MarketTrendArticle.scraped_at.asc())
            .limit(limit)
            .all()
        )

        for article in rows:
            try:
                text = f"{article.title or ''} {article.body_text or ''}".strip()
                if not text:
                    metrics["records_skipped"] += 1
                    continue
                sentiment_label, sentiment_score = analyze_sentiment(text)
                topics = classify_topics(text)
                keywords = extract_keywords(text, limit=10)

                topic = self._get_or_create_topic(topics[0], EntityDomain.GENERAL)
                summary_text = f"topics={', '.join(topics)}; keywords={', '.join(keywords)}"

                row = ArticleNlpResult(
                    article_id=article.id,
                    sentiment_label=SentimentLabel[sentiment_label.upper()],
                    sentiment_score=Decimal(f"{sentiment_score:.4f}"),
                    topic_id=topic.id if topic else None,
                    summary_text=summary_text,
                    model_version=self.model_version,
                )
                self.session.add(row)
                self.session.flush()
                logger.info(
                    "NLP article processed id=%s sentiment=%s topics=%s keywords=%s",
                    article.id,
                    sentiment_label,
                    topics,
                    keywords,
                )
                metrics["records_processed"] += 1
            except Exception:
                self.session.rollback()
                logger.exception("Failed NLP processing for article id=%s", article.id)
                metrics["records_failed"] += 1

        self.session.commit()
        metrics["processing_time_seconds"] = (datetime.now(timezone.utc) - started).total_seconds()
        return metrics

    def _get_or_create_topic(self, label: str, domain: EntityDomain) -> Optional[Topic]:
        topic = (
            self.session.query(Topic)
            .filter(Topic.topic_label == label)
            .filter(Topic.domain == domain)
            .filter(Topic.model_version == self.model_version)
            .first()
        )
        if topic:
            return topic

        topic = Topic(
            topic_label=label,
            top_words=label.split(),
            domain=domain,
            model_version=self.model_version,
        )
        self.session.add(topic)
        self.session.flush()
        return topic

    def _get_or_create_complaint(self, category: str, domain: EntityDomain) -> ComplaintType:
        code = category.lower().strip().replace(" ", "_")
        row = self.session.query(ComplaintType).filter_by(code=code).first()
        if row:
            return row

        row = ComplaintType(code=code, label=category.replace("_", " ").title(), domain=domain)
        self.session.add(row)
        self.session.flush()
        return row
