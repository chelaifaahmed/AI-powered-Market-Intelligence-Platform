"""
scripts/ingest_apify_reddit.py
-------------------------------
Fetches posts from an Apify Reddit scraper dataset and stores them
in the market_trend_articles table as MarketTrendArticle records.

Usage:
    python scripts/ingest_apify_reddit.py --dataset-id <DATASET_ID> --token <APIFY_TOKEN>

Defaults to the latest run's dataset if not specified.
"""
from __future__ import annotations

import argparse
import os
import sys
import urllib.request
import json
from datetime import datetime, timezone, date

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

from database.connection import get_db_session
from database.models import MarketTrendArticle

APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "")
DATASET_ID  = "zAPsavgcbKF5FYzqD"

def _detect_category(title: str, body: str) -> str:
    text = (title + " " + (body or "")).lower()
    if any(k in text for k in ["ev", "electric", "battery", "tesla", "bev", "charging"]):
        return "EV"
    if any(k in text for k in ["insurance", "premium", "claim", "coverage", "policy"]):
        return "Insurance"
    if any(k in text for k in ["erp", "software", "fleet", "leasing", "crm", "sap"]):
        return "Technology"
    if any(k in text for k in ["recall", "defect", "safety", "regulation", "nhtsa"]):
        return "Regulation"
    if any(k in text for k in ["market", "price", "economy", "gdp", "inflation", "fuel", "oil"]):
        return "Market"
    return "Market"

def fetch_items(dataset_id: str, token: str) -> list[dict]:
    url = f"https://api.apify.com/v2/datasets/{dataset_id}/items?token={token}&limit=200"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)

def ingest(items: list[dict]) -> tuple[int, int]:
    inserted = skipped = 0
    with get_db_session() as session:
        existing_urls = {
            row[0] for row in session.query(MarketTrendArticle.source_url).all()
        }
        for item in items:
            if item.get("dataType") != "post":
                continue
            url = item.get("url", "")
            if not url or url in existing_urls:
                skipped += 1
                continue

            title = item.get("title") or "Reddit Post"
            body  = item.get("body") or ""
            author = item.get("username") or "reddit_user"
            community = item.get("communityName") or ""

            scraped_raw = item.get("scrapedAt") or item.get("createdAt")
            try:
                scraped_dt = datetime.fromisoformat(scraped_raw.replace("Z", "+00:00"))
            except Exception:
                scraped_dt = datetime.now(timezone.utc)

            created_raw = item.get("createdAt")
            try:
                pub_date = date.fromisoformat(created_raw[:10])
            except Exception:
                pub_date = date.today()

            category = _detect_category(title, body)
            region   = "Global"
            if any(k in community.lower() for k in ["tunisia", "maghreb", "africa"]):
                region = "TN"

            article = MarketTrendArticle(
                title            = title[:500],
                author           = author[:200],
                publication_date = pub_date,
                body_text        = body[:10000] if body else None,
                source_url       = url,
                category         = category,
                region           = region,
                scraped_at       = scraped_dt,
                data_origin      = "scraped",
            )
            session.add(article)
            existing_urls.add(url)
            inserted += 1

        session.commit()
    return inserted, skipped


def main():
    parser = argparse.ArgumentParser(description="Ingest Apify Reddit data into DB")
    parser.add_argument("--dataset-id", default=DATASET_ID)
    parser.add_argument("--token",      default=APIFY_TOKEN)
    args = parser.parse_args()

    print(f"Fetching from dataset {args.dataset_id} ...")
    items = fetch_items(args.dataset_id, args.token)
    print(f"  → {len(items)} items retrieved")

    inserted, skipped = ingest(items)
    print(f"  → {inserted} articles inserted, {skipped} skipped (duplicates/non-posts)")
    print("Done.")


if __name__ == "__main__":
    main()
