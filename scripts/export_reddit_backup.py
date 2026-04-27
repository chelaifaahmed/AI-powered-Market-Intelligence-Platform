"""
scripts/export_reddit_backup.py
--------------------------------
Exports all Reddit-sourced data (articles, car reviews, insurance reviews)
from the database to a local JSON backup file.

Run this to create a permanent local copy of all scraped Reddit data.
Re-import later with: python scripts/import_reddit_backup.py
"""
import os, sys, json
from datetime import datetime

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

from database.connection import get_db_session
from database.models import MarketTrendArticle, CarReview, InsuranceReview, CarModel, CarBrand, InsuranceCompany


def serialize(obj) -> dict:
    d = {}
    for col in obj.__class__.__table__.columns:
        val = getattr(obj, col.name, None)
        d[col.name] = str(val) if val is not None else None
    return d


def main():
    backup = {
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "source": "reddit.com (via Apify scraper)",
        "articles": [],
        "car_reviews": [],
        "insurance_reviews": [],
    }

    with get_db_session() as session:
        # Reddit articles
        arts = session.query(MarketTrendArticle).filter(
            MarketTrendArticle.source_url.like('%reddit.com%')
        ).all()
        backup["articles"] = [serialize(a) for a in arts]
        print(f"Articles (Reddit): {len(arts)}")

        # All scraped articles (not just reddit — covers future sources)
        all_scraped = session.query(MarketTrendArticle).filter(
            MarketTrendArticle.data_origin == 'scraped'
        ).all()
        backup["all_scraped_articles"] = [serialize(a) for a in all_scraped]
        print(f"All scraped articles: {len(all_scraped)}")

        # Scraped car reviews
        car_revs = session.query(CarReview).filter(
            CarReview.data_origin == 'scraped'
        ).all()
        # Enrich with brand/model name
        car_dicts = []
        for cr in car_revs:
            d = serialize(cr)
            model = session.get(CarModel, cr.model_id) if cr.model_id else None
            brand = session.get(CarBrand, model.brand_id) if model else None
            d["model_name"] = model.name if model else None
            d["brand_name"] = brand.name if brand else None
            car_dicts.append(d)
        backup["car_reviews"] = car_dicts
        print(f"Scraped car reviews: {len(car_revs)}")

        # Scraped insurance reviews
        ins_revs = session.query(InsuranceReview).filter(
            InsuranceReview.data_origin == 'scraped'
        ).all()
        ins_dicts = []
        for ir in ins_revs:
            d = serialize(ir)
            company = session.get(InsuranceCompany, ir.company_id) if ir.company_id else None
            d["company_name"] = company.name if company else None
            ins_dicts.append(d)
        backup["insurance_reviews"] = ins_dicts
        print(f"Scraped insurance reviews: {len(ins_revs)}")

    # Save to local JSON
    out_path = os.path.join(_PROJECT_ROOT, "reddit_data_backup.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(backup, f, ensure_ascii=False, indent=2)

    size_mb = os.path.getsize(out_path) / 1024 / 1024
    print(f"\n✅ Backup saved to: {out_path}")
    print(f"   Size: {size_mb:.2f} MB")
    print(f"   Articles: {len(backup['articles'])} reddit / {len(backup.get('all_scraped_articles', []))} total scraped")
    print(f"   Car reviews: {len(backup['car_reviews'])}")
    print(f"   Insurance reviews: {len(backup['insurance_reviews'])}")


if __name__ == "__main__":
    main()
