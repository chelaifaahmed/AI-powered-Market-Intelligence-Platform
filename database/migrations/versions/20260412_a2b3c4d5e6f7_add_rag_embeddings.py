"""add_rag_embeddings

Adds JSONB embedding columns to the three corpora used by the RAG layer:
market_trend_articles, car_reviews, and insurance_reviews.

Storage: JSONB float array (768 values, L2-normalised BGE-base-en-v1.5 output).
Search:  Cosine similarity computed via numpy in Python (dot product of L2-norm
         vectors). At 2 500 rows × 768 dims, in-memory search completes in <5ms
         — no pgvector server extension required.
BM25:    GIN index on tsvector(title || body) for full-text hybrid retrieval.

Revision ID: a2b3c4d5e6f7
Revises: e6cc055da982
Create Date: 2026-04-12
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, None] = "e6cc055da982"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Embedding column on market_trend_articles (regular table)
    op.add_column(
        "market_trend_articles",
        sa.Column(
            "embedding", JSONB, nullable=True,
            comment="BAAI/bge-base-en-v1.5 embedding (768-dim list, L2-normalised) for RAG retrieval."
        ),
    )

    # 2. Embedding column on car_reviews parent table
    #    PostgreSQL 14+: ADD COLUMN on parent propagates to all partitions.
    op.add_column(
        "car_reviews",
        sa.Column(
            "embedding", JSONB, nullable=True,
            comment="BAAI/bge-base-en-v1.5 embedding (768-dim list, L2-normalised) for RAG retrieval."
        ),
    )

    # 3. Embedding column on insurance_reviews parent table
    op.add_column(
        "insurance_reviews",
        sa.Column(
            "embedding", JSONB, nullable=True,
            comment="BAAI/bge-base-en-v1.5 embedding (768-dim list, L2-normalised) for RAG retrieval."
        ),
    )

    # 4. GIN index on market_trend_articles for BM25 / full-text hybrid retrieval.
    #    Enables fast @@ plainto_tsquery() without a full table scan.
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_mta_fts "
        "ON market_trend_articles "
        "USING gin (to_tsvector('english', coalesce(title,'') || ' ' || coalesce(body_text,'')))"
    )

    # 5. Sparse B-tree index: quickly find rows where embedding IS NOT NULL
    #    (used by the incremental indexer to skip already-embedded rows).
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_mta_has_embedding "
        "ON market_trend_articles ((embedding IS NOT NULL)) "
        "WHERE embedding IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_mta_has_embedding")
    op.execute("DROP INDEX IF EXISTS idx_mta_fts")
    op.drop_column("insurance_reviews", "embedding")
    op.drop_column("car_reviews", "embedding")
    op.drop_column("market_trend_articles", "embedding")
