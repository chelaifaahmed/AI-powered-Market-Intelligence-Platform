"""
analytics/rag_indexer.py
------------------------
Batch embedding pipeline for the RAG layer.

Embeds MarketTrendArticle, CarReview, and InsuranceReview rows that have
no embedding yet, using BAAI/bge-base-en-v1.5 (768-dim, L2-normalised).

Design:
  - Incremental: only processes rows where embedding IS NULL. Safe to re-run.
  - Batch size 64 for efficient CPU throughput (~30 it/s on a modern laptop).
  - BGE does NOT require a prefix for passages (only for queries).
  - Embeddings are L2-normalised, so cosine similarity = dot product (faster search).

Usage:
    python -m analytics.rag_indexer                      # embed all corpora
    python -m analytics.rag_indexer --corpus articles    # articles only
    python -m analytics.rag_indexer --corpus car_reviews
    python -m analytics.rag_indexer --corpus insurance_reviews
    python -m analytics.rag_indexer --batch-size 32      # slower machines
"""

from __future__ import annotations

import argparse
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

from database.connection import get_db_session
from database.models import CarReview, InsuranceReview, MarketTrendArticle

MODEL_NAME = "BAAI/bge-base-en-v1.5"
DEFAULT_BATCH = 64


# ---------------------------------------------------------------------------
# Text builders — controls what gets embedded for each corpus
# ---------------------------------------------------------------------------

def _article_text(art: MarketTrendArticle) -> str:
    parts = [art.title or ""]
    if art.body_text:
        parts.append(art.body_text[:700])
    return " ".join(parts).strip()


def _car_review_text(rev: CarReview) -> str:
    parts = []
    if rev.review_title:
        parts.append(rev.review_title)
    parts.append(rev.review_text[:500])
    return " ".join(parts).strip()


def _insurance_review_text(rev: InsuranceReview) -> str:
    parts = []
    if rev.review_title:
        parts.append(rev.review_title)
    parts.append(rev.review_text[:500])
    return " ".join(parts).strip()


# ---------------------------------------------------------------------------
# Per-corpus embedding runners
# ---------------------------------------------------------------------------

def embed_articles(model, batch_size: int) -> int:
    embedded = 0
    with get_db_session() as session:
        rows = (
            session.query(MarketTrendArticle)
            .filter(MarketTrendArticle.embedding.is_(None))
            .order_by(MarketTrendArticle.scraped_at.desc())
            .all()
        )
        if not rows:
            print("  [articles] all rows already embedded — skipping.")
            return 0

        print(f"  [articles] embedding {len(rows)} rows ...")
        texts = [_article_text(r) for r in rows]

        for i in range(0, len(rows), batch_size):
            batch_rows = rows[i : i + batch_size]
            batch_texts = texts[i : i + batch_size]
            embeddings = model.encode(
                batch_texts, normalize_embeddings=True, show_progress_bar=False
            )
            for row, emb in zip(batch_rows, embeddings):
                row.embedding = emb.tolist()
            session.flush()
            embedded += len(batch_rows)
            print(f"    [{embedded}/{len(rows)}] done")

    print(f"  [articles] {embedded} rows embedded.")
    return embedded


def embed_car_reviews(model, batch_size: int) -> int:
    embedded = 0
    with get_db_session() as session:
        rows = (
            session.query(CarReview)
            .filter(CarReview.embedding.is_(None))
            .order_by(CarReview.scraped_at.desc())
            .all()
        )
        if not rows:
            print("  [car_reviews] all rows already embedded — skipping.")
            return 0

        print(f"  [car_reviews] embedding {len(rows)} rows ...")
        texts = [_car_review_text(r) for r in rows]

        for i in range(0, len(rows), batch_size):
            batch_rows = rows[i : i + batch_size]
            batch_texts = texts[i : i + batch_size]
            embeddings = model.encode(
                batch_texts, normalize_embeddings=True, show_progress_bar=False
            )
            for row, emb in zip(batch_rows, embeddings):
                row.embedding = emb.tolist()
            session.flush()
            embedded += len(batch_rows)
            print(f"    [{embedded}/{len(rows)}] done")

    print(f"  [car_reviews] {embedded} rows embedded.")
    return embedded


def embed_insurance_reviews(model, batch_size: int) -> int:
    embedded = 0
    with get_db_session() as session:
        rows = (
            session.query(InsuranceReview)
            .filter(InsuranceReview.embedding.is_(None))
            .order_by(InsuranceReview.scraped_at.desc())
            .all()
        )
        if not rows:
            print("  [insurance_reviews] all rows already embedded — skipping.")
            return 0

        print(f"  [insurance_reviews] embedding {len(rows)} rows ...")
        texts = [_insurance_review_text(r) for r in rows]

        for i in range(0, len(rows), batch_size):
            batch_rows = rows[i : i + batch_size]
            batch_texts = texts[i : i + batch_size]
            embeddings = model.encode(
                batch_texts, normalize_embeddings=True, show_progress_bar=False
            )
            for row, emb in zip(batch_rows, embeddings):
                row.embedding = emb.tolist()
            session.flush()
            embedded += len(batch_rows)
            print(f"    [{embedded}/{len(rows)}] done")

    print(f"  [insurance_reviews] {embedded} rows embedded.")
    return embedded


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Incremental RAG embedding indexer for the TEAMWILL platform."
    )
    parser.add_argument(
        "--corpus",
        choices=["articles", "car_reviews", "insurance_reviews", "all"],
        default="all",
        help="Which corpus to embed (default: all).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH,
        help=f"Encoding batch size (default: {DEFAULT_BATCH}). Lower for slow CPUs.",
    )
    args = parser.parse_args()

    print(f"Loading embedding model: {MODEL_NAME} ...")
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(MODEL_NAME)
    print("Model loaded.\n")

    total = 0
    if args.corpus in ("articles", "all"):
        total += embed_articles(model, args.batch_size)
    if args.corpus in ("car_reviews", "all"):
        total += embed_car_reviews(model, args.batch_size)
    if args.corpus in ("insurance_reviews", "all"):
        total += embed_insurance_reviews(model, args.batch_size)

    print(f"\nDone. Total rows embedded this run: {total}")


if __name__ == "__main__":
    main()
