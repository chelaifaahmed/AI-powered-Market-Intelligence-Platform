"""
scripts/import_reddit_backup.py
--------------------------------
Re-imports Reddit data from the local JSON backup file back into the database.
Use this if the database is reset and you need to restore the Reddit data.

Usage:
    python scripts/import_reddit_backup.py
    python scripts/import_reddit_backup.py --file my_backup.json
"""
import os, sys, json, argparse
from datetime import datetime, timezone, date

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

from database.connection import get_db_session
from database.models import MarketTrendArticle, CarReview, InsuranceReview, CarModel, CarBrand, InsuranceCompany


def parse_dt(s):
    if not s: return datetime.now(timezone.utc)
    try: return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except: return datetime.now(timezone.utc)

def parse_date(s):
    if not s: return date.today()
    try: return date.fromisoformat(s[:10])
    except: return date.today()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default="reddit_data_backup.json")
    args = parser.parse_args()

    backup_path = os.path.join(_PROJECT_ROOT, args.file)
    if not os.path.exists(backup_path):
        print(f"❌ Backup file not found: {backup_path}")
        sys.exit(1)

    with open(backup_path, "r", encoding="utf-8") as f:
        backup = json.load(f)

    # Use all_scraped_articles if available, otherwise articles
    articles = backup.get("all_scraped_articles") or backup.get("articles", [])
    car_reviews = backup.get("car_reviews", [])
    insurance_reviews = backup.get("insurance_reviews", [])

    print(f"Backup from: {backup.get('exported_at', 'unknown')}")
    print(f"  Articles to restore:          {len(articles)}")
    print(f"  Car reviews to restore:       {len(car_reviews)}")
    print(f"  Insurance reviews to restore: {len(insurance_reviews)}")
    print()

    stats = {"articles": 0, "car_reviews": 0, "ins_reviews": 0, "skipped": 0}

    with get_db_session() as session:
        # Pre-load existing URLs
        existing_art = {r[0] for r in session.query(MarketTrendArticle.source_url).all()}
        existing_car = {r[0] for r in session.query(CarReview.source_url).all()}
        existing_ins = {r[0] for r in session.query(InsuranceReview.source_url).all()}

        # Brand lookup by name
        brands = {b.name.lower(): b for b in session.query(CarBrand).all()}
        brand_models: dict[str, object] = {}
        for model in session.query(CarModel).all():
            for b in brands.values():
                if b.id == model.brand_id and b.name.lower() not in brand_models:
                    brand_models[b.name.lower()] = model

        companies = {c.name.lower(): c for c in session.query(InsuranceCompany).all()}

        # Restore articles
        for a in articles:
            url = a.get("source_url", "")
            if not url or url in existing_art:
                stats["skipped"] += 1
                continue
            article = MarketTrendArticle(
                title=a.get("title") or "Untitled",
                author=a.get("author"),
                publication_date=parse_date(a.get("publication_date")),
                body_text=a.get("body_text"),
                source_url=url,
                category=a.get("category"),
                region=a.get("region") or "Global",
                scraped_at=parse_dt(a.get("scraped_at")),
                data_origin="scraped",
            )
            session.add(article)
            existing_art.add(url)
            stats["articles"] += 1

        # Restore car reviews
        for cr in car_reviews:
            url = cr.get("source_url", "")
            if not url or url in existing_car:
                stats["skipped"] += 1
                continue
            brand_name = (cr.get("brand_name") or "").lower()
            model_obj = brand_models.get(brand_name)
            if not model_obj:
                stats["skipped"] += 1
                continue
            review = CarReview(
                model_id=model_obj.id,
                source_url=url,
                rating=float(cr["rating"]) if cr.get("rating") else None,
                review_title=cr.get("review_title"),
                review_text=cr.get("review_text") or "",
                author=cr.get("author"),
                review_date=parse_date(cr.get("review_date")),
                scraped_at=parse_dt(cr.get("scraped_at")),
                data_origin="scraped",
            )
            session.add(review)
            existing_car.add(url)
            stats["car_reviews"] += 1

        # Restore insurance reviews
        for ir in insurance_reviews:
            url = ir.get("source_url", "")
            if not url or url in existing_ins:
                stats["skipped"] += 1
                continue
            company_name = (ir.get("company_name") or "").lower()
            company_obj = companies.get(company_name)
            if not company_obj:
                stats["skipped"] += 1
                continue
            review = InsuranceReview(
                company_id=company_obj.id,
                source_url=url,
                rating=float(ir["rating"]) if ir.get("rating") else None,
                review_title=ir.get("review_title"),
                review_text=ir.get("review_text") or "",
                author=ir.get("author"),
                review_date=parse_date(ir.get("review_date")),
                scraped_at=parse_dt(ir.get("scraped_at")),
                data_origin="scraped",
            )
            session.add(review)
            existing_ins.add(url)
            stats["ins_reviews"] += 1

        session.commit()

    print("✅ Restore complete:")
    print(f"  Articles inserted:         {stats['articles']}")
    print(f"  Car reviews inserted:      {stats['car_reviews']}")
    print(f"  Insurance reviews inserted:{stats['ins_reviews']}")
    print(f"  Skipped (duplicates/etc):  {stats['skipped']}")


if __name__ == "__main__":
    main()
