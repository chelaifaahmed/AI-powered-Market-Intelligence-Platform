"""
scripts/import_yelp_neutrals.py
--------------------------------
Streams the HuggingFace yelp_review_full dataset, filters for:
  - 3-star reviews (label=2 → neutral sentiment)
  - Automotive/insurance keywords in the review text

Inserts matching reviews as CarReview (or InsuranceReview) rows with
  data_origin='scraped', rating=3.0  so build_training_set.py picks them up.

Usage:
    python -m scripts.import_yelp_neutrals --target 300
"""
from __future__ import annotations

import argparse
import hashlib
import re

from datasets import load_dataset
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

CAR_KEYWORDS = re.compile(
    r"\b(car|vehicle|truck|suv|sedan|dealership|dealer|auto|mechanic|"
    r"repair|oil change|tire|engine|transmission|lease|test drive|"
    r"salesman|service center|service department|collision|bodywork|"
    r"bmw|toyota|honda|ford|chevrolet|hyundai|volkswagen|nissan|mazda|"
    r"audi|mercedes|tesla|fiat|renault|peugeot|kia|dodge|jeep|ram|"
    r"automotive|car wash|windshield|battery|brakes|exhaust)\b",
    re.IGNORECASE,
)


_DB_URL = "postgresql+psycopg2://postgres:@localhost:5432/automotive_intelligence"


def _get_source_id(session, name: str) -> int:
    row = session.execute(text("SELECT id FROM review_sources WHERE name=:n"), {"n": name}).fetchone()
    if row:
        return row[0]
    result = session.execute(
        text("INSERT INTO review_sources "
             "(id, name, base_url, reliability_score, is_active, total_records_scraped, created_at, updated_at) "
             "VALUES (gen_random_uuid(), :n, :u, 0.8, true, 0, NOW(), NOW()) RETURNING id"),
        {"n": name, "u": "https://www.yelp.com"}
    )
    session.commit()
    return result.fetchone()[0]


def _get_generic_model_id(session) -> str:
    """Return the ID of a 'Generic / Dealership' placeholder car model, creating it if needed."""
    row = session.execute(
        text("SELECT id FROM car_models WHERE name='Generic / Dealership' LIMIT 1")
    ).fetchone()
    if row:
        return row[0]
    # Check what columns car_models has
    cols = session.execute(
        text("SELECT column_name FROM information_schema.columns WHERE table_name='car_models'")
    ).fetchall()
    col_names = {r[0] for r in cols}
    # Build minimal insert
    # Use first available brand_id as placeholder
    brand_row = session.execute(text("SELECT id FROM car_brands LIMIT 1")).fetchone()
    brand_id = str(brand_row[0]) if brand_row else None
    fields = ["id", "brand_id", "name", "is_active", "created_at", "updated_at"]
    vals = ["gen_random_uuid()", f"'{brand_id}'", "'Generic / Dealership'", "true", "NOW()", "NOW()"]
    if "data_origin" in col_names:
        fields.append("data_origin")
        vals.append("'seeded'")
    sql = f"INSERT INTO car_models ({', '.join(fields)}) VALUES ({', '.join(vals)}) RETURNING id"
    result = session.execute(text(sql))
    session.commit()
    return result.fetchone()[0]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=300,
                    help="How many neutral reviews to import (default 300)")
    ap.add_argument("--min-len", type=int, default=40,
                    help="Minimum review text length (default 40 chars)")
    args = ap.parse_args()

    engine = create_engine(_DB_URL, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)

    print(f"[import_yelp_neutrals] streaming yelp_review_full, target={args.target} neutral reviews")
    ds = load_dataset("yelp_review_full", split="train", streaming=True)

    car_count = 0
    scanned = 0

    with Session() as session:
        car_source_id = _get_source_id(session, "Yelp")
        generic_model_id = _get_generic_model_id(session)

        for item in ds:
            scanned += 1
            if scanned % 50_000 == 0:
                print(f"  scanned {scanned:,}, inserted={car_count}")

            if car_count >= args.target:
                break

            label = item.get("label")
            text_body = (item.get("text") or "").strip()

            # 3-star only (neutral), long enough
            if label != 2 or len(text_body) < args.min_len:
                continue

            if not CAR_KEYWORDS.search(text_body):
                continue

            content_hash = hashlib.sha256(text_body.encode("utf-8")).hexdigest()

            # Avoid duplicates
            exists = session.execute(
                text("SELECT 1 FROM car_reviews WHERE content_hash=:h LIMIT 1"),
                {"h": content_hash}
            ).fetchone()
            if exists:
                continue

            session.execute(
                text("""
                    INSERT INTO car_reviews
                        (id, model_id, source_id, source_url, rating, review_text,
                         data_origin, is_processed, scraped_at, created_at, updated_at,
                         content_hash, is_verified, confidence_score)
                    VALUES
                        (gen_random_uuid(), :mid, :sid, 'https://www.yelp.com', 3.0, :txt,
                         'scraped', false, NOW(), NOW(), NOW(),
                         :ch, false, 1.0)
                    ON CONFLICT DO NOTHING
                """),
                {"mid": generic_model_id, "sid": car_source_id, "txt": text_body[:3000], "ch": content_hash}
            )
            car_count += 1

            if car_count % 50 == 0:
                session.commit()
                print(f"  committed: {car_count}")

        session.commit()

    print(f"\n[import_yelp_neutrals] Done — inserted {car_count} neutral reviews")
    print(f"  scanned {scanned:,} total yelp reviews")


if __name__ == "__main__":
    main()
