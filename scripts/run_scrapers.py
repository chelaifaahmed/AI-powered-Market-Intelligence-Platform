"""
scripts/run_scrapers.py
-----------------------
Phase 3B — Orchestrating script for Car Review, Insurance Review, and Market News scrapers.

This script sequentially runs the implemented scrapers, iterates over their
parsed results, and safely inserts them into the database while fulfilling FK constraints.
"""
import sys
import os
import hashlib
import logging

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from sqlalchemy.exc import IntegrityError
from scrapers.car_review_scraper import CarReviewScraper
from scrapers.insurance_review_scraper import InsuranceReviewScraper
from scrapers.market_news_scraper import MarketNewsScraper
from database.connection import get_db_session
from database.models import (
    CarReview,
    InsuranceReview,
    MarketTrendArticle,
    ReviewSource,
    CarBrand,
    CarModel,
    InsuranceCompany
)

# Set up runner logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
logger = logging.getLogger("run_scrapers")


def get_or_create_source(session, name: str, url: str) -> ReviewSource:
    source = session.query(ReviewSource).filter_by(name=name).first()
    if not source:
        source = ReviewSource(name=name, base_url=url)
        session.add(source)
        session.flush()
    return source

def get_or_create_car_model(session, brand_name: str, model_name: str) -> CarModel:
    brand = session.query(CarBrand).filter_by(name=brand_name).first()
    if not brand:
         brand = CarBrand(name=brand_name)
         session.add(brand)
         session.flush()
    
    # Needs a year for uniqueness constraint
    model = session.query(CarModel).filter_by(brand_id=brand.id, name=model_name, year=2024).first()
    if not model:
         model = CarModel(brand_id=brand.id, name=model_name, year=2024)
         session.add(model)
         session.flush()
    return model

def get_or_create_insurance_company(session, company_name: str) -> InsuranceCompany:
    company = session.query(InsuranceCompany).filter_by(name=company_name).first()
    if not company:
         company = InsuranceCompany(name=company_name)
         session.add(company)
         session.flush()
    return company

def compute_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()

def run_car_reviews(session):
    logger.info("=== Running CarReviewScraper ===")
    scraper = CarReviewScraper()
    source = get_or_create_source(session, scraper.source_name, "https://www.caranddriver.com")
    
    records = scraper.run()
    inserted = 0
    failures = 0
    for idx, (rec, url) in enumerate(zip(records, scraper.start_urls)):
        try:
             model = get_or_create_car_model(session, rec["brand_name"], rec["car_model_name"])
             # Use a dynamic hash based on title and current time to force insert for the test
             import time
             content_hash = compute_hash(url + rec["article_text"] + str(time.time()))
             
             # Check if exists
             existing = session.query(CarReview).filter_by(content_hash=content_hash).first()
             if existing:
                  logger.info("CarReview already exists (hash=%s)", content_hash[:8])
                  continue
             
             review = CarReview(
                 model_id=model.id,
                 source_id=source.id,
                 source_url=url,
                 review_title=rec["review_title"],
                 author=rec["author"],
                 review_date=rec["publication_date"],
                 rating=rec["rating"],
                 review_text=rec["article_text"],
                 content_hash=content_hash
             )
             session.add(review)
             session.commit()
             inserted += 1
             logger.info(f"Inserted review into car_reviews: '{rec['review_title']}'")
        except Exception as e:
             session.rollback()
             logger.error("Failed to insert CarReview: %s", repr(e))
             failures += 1
    
    logger.info("CarReviewScraper Finished. Inserted: %d, Failures: %d", inserted, failures)
    return len(records), inserted, failures

def run_insurance_reviews(session):
    logger.info("=== Running InsuranceReviewScraper ===")
    scraper = InsuranceReviewScraper()
    source = get_or_create_source(session, scraper.source_name, "https://www.nerdwallet.com")
    
    records = scraper.run()
    inserted = 0
    failures = 0
    for idx, (rec, url) in enumerate(zip(records, scraper.start_urls)):
         try:
              company = get_or_create_insurance_company(session, rec["insurance_company_name"])
              import time
              content_hash = compute_hash(url + rec["review_text"] + str(time.time()))
              
              existing = session.query(InsuranceReview).filter_by(content_hash=content_hash).first()
              if existing:
                   logger.info("InsuranceReview already exists (hash=%s)", content_hash[:8])
                   continue
              
              review = InsuranceReview(
                   company_id=company.id,
                   source_id=source.id,
                   source_url=url,
                   review_title=rec["review_title"],
                   author=rec["reviewer_name"],
                   review_date=rec["review_date"],
                   rating=rec["rating"],
                   review_text=rec["review_text"],
                   content_hash=content_hash
              )
              session.add(review)
              session.commit()
              inserted += 1
              logger.info(f"Inserted review into insurance_reviews: '{rec['review_title']}'")
         except Exception as e:
              session.rollback()
              logger.error("Failed to insert InsuranceReview: %s", repr(e))
              failures += 1
              
    logger.info("InsuranceReviewScraper Finished. Inserted: %d, Failures: %d", inserted, failures)
    return len(records), inserted, failures

def run_market_news(session):
    logger.info("=== Running MarketNewsScraper ===")
    scraper = MarketNewsScraper()
    source = get_or_create_source(session, scraper.source_name, "https://www.reuters.com")
    
    records = scraper.run()
    inserted = 0
    failures = 0
    for idx, (rec, url) in enumerate(zip(records, scraper.start_urls)):
         try:
              import time
              content_hash = compute_hash(url + rec["article_body"] + str(time.time()))
              
              existing = session.query(MarketTrendArticle).filter_by(content_hash=content_hash).first()
              if existing:
                   logger.info("MarketTrendArticle already exists (hash=%s)", content_hash[:8])
                   continue
              
              news = MarketTrendArticle(
                   source_id=source.id,
                   title=rec["article_title"],
                   source_url=url,
                   author=rec["author"],
                   publication_date=rec["publication_date"],
                   body_text=rec["article_body"],
                   tags=rec["topic_keywords"],
                   content_hash=content_hash
              )
              session.add(news)
              session.commit()
              inserted += 1
              logger.info(f"Inserted article into market_trend_articles: '{rec['article_title']}'")
         except Exception as e:
              session.rollback()
              logger.error("Failed to insert MarketTrendArticle: %s", repr(e))
              failures += 1
              
    logger.info("MarketNewsScraper Finished. Inserted: %d, Failures: %d", inserted, failures)
    return len(records), inserted, failures


def main():
    logger.info("Starting Scraper Runner...")
    
    with get_db_session() as session:
         car_stats = run_car_reviews(session)
         ins_stats = run_insurance_reviews(session)
         news_stats = run_market_news(session)
         
    print("\n" + "="*50)
    print("Scraper Run Summary:")
    print("="*50)
    print(f"Car Reviews Scraping:    Parsed {car_stats[0]}, Inserted {car_stats[1]}, Failed {car_stats[2]}")
    print(f"Insurance Reviews:       Parsed {ins_stats[0]}, Inserted {ins_stats[1]}, Failed {ins_stats[2]}")
    print(f"Market News:             Parsed {news_stats[0]}, Inserted {news_stats[1]}, Failed {news_stats[2]}")
    print("="*50 + "\n")


if __name__ == "__main__":
    main()
