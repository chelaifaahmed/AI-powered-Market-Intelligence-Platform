"""
scripts/launch_apify_batches.py
--------------------------------
Launches multiple parallel Apify Reddit scraper runs, waits for
completion, then ingests ALL results into the database.

Covers: cars, insurance, EV/tech, mechanics/reviews
"""
from __future__ import annotations
import os, sys, json, time, urllib.request
from datetime import datetime, timezone, date

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

from database.connection import get_db_session
from database.models import MarketTrendArticle, CarReview, InsuranceReview, CarBrand, InsuranceCompany, CarModel

TOKEN    = os.environ.get("APIFY_TOKEN", "")
ACTOR_ID = "FgJtjDwJCLhRH9saM"

BATCHES = [
    ("cars_general", [
        "https://www.reddit.com/r/cars/",
        "https://www.reddit.com/r/CarComplaints/",
        "https://www.reddit.com/r/UsedCars/",
        "https://www.reddit.com/r/carbuying/",
        "https://www.reddit.com/r/whatcarshouldIbuy/",
        "https://www.reddit.com/r/trucks/",
    ]),
    ("insurance_finance", [
        "https://www.reddit.com/r/Insurance/",
        "https://www.reddit.com/r/personalfinance/",
        "https://www.reddit.com/r/legaladvice/",
        "https://www.reddit.com/r/Frugal/",
    ]),
    ("ev_tech", [
        "https://www.reddit.com/r/electricvehicles/",
        "https://www.reddit.com/r/teslamotors/",
        "https://www.reddit.com/r/RenaultZoe/",
        "https://www.reddit.com/r/Rivian/",
        "https://www.reddit.com/r/leaf/",
    ]),
    ("mechanics_reviews", [
        "https://www.reddit.com/r/MechanicAdvice/",
        "https://www.reddit.com/r/askcarsales/",
        "https://www.reddit.com/r/AutoDetailing/",
        "https://www.reddit.com/r/Cartalk/",
        "https://www.reddit.com/r/cars/search/?q=review+2024+2025&sort=new",
    ]),
]

# ── Known brand & company names for review mapping ──────────────────────────
CAR_BRAND_KEYWORDS = [
    "toyota","volkswagen","bmw","mercedes","audi","ford","honda","hyundai",
    "kia","peugeot","renault","citroen","fiat","seat","volvo","tesla",
    "nissan","mazda","chevrolet","gmc","jeep","ram","dodge","subaru",
    "mitsubishi","lexus","infiniti","porsche","lamborghini","ferrari",
    "land rover","jaguar","skoda","opel","dacia","alfa romeo",
]

INSURANCE_KEYWORDS = [
    "geico","progressive","allstate","state farm","usaa","nationwide",
    "farmers","liberty mutual","travelers","hartford","amica","esurance",
    "allianz","axa","zurich","generali","maaf","mma","groupama",
    "matmut","gmf","covea","april","abeille","gan","pacifica",
]


def _apify_post(endpoint: str, payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        endpoint, data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def launch_run(label: str, urls: list[str]) -> str:
    payload = {
        "startUrls": [{"url": u} for u in urls],
        "maxItems": 200,
        "maxPostCount": 200,
        "maxComments": 5,
        "sort": "new",
        "searchPosts": True,
        "skipComments": False,
        "proxy": {"useApifyProxy": True, "apifyProxyGroups": ["RESIDENTIAL"]},
        "scrollTimeout": 40,
        "includeNSFW": False,
    }
    url = f"https://api.apify.com/v2/acts/{ACTOR_ID}/runs?token={TOKEN}"
    resp = _apify_post(url, payload)
    run_id = resp.get("data", {}).get("id", "?")
    print(f"  [{label}] launched => run {run_id}")
    return run_id


def wait_for_run(run_id: str, max_wait: int = 300) -> dict:
    deadline = time.time() + max_wait
    while time.time() < deadline:
        with urllib.request.urlopen(
            f"https://api.apify.com/v2/actor-runs/{run_id}?token={TOKEN}", timeout=30
        ) as r:
            d = json.load(r).get("data", {})
        status = d.get("status", "")
        if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            return d
        time.sleep(20)
    return {}


def fetch_dataset(dataset_id: str) -> list[dict]:
    url = f"https://api.apify.com/v2/datasets/{dataset_id}/items?token={TOKEN}&limit=500"
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


# ── Category detection ────────────────────────────────────────────────────────
def detect_category(title: str, body: str) -> str:
    text = (title + " " + (body or "")).lower()
    if any(k in text for k in ["ev ", "electric vehicle", "battery", "tesla", "bev", "charging station", "e-car"]):
        return "EV"
    if any(k in text for k in ["insurance", "premium", "claim", "coverage", "policy", "deductible"]):
        return "Insurance"
    if any(k in text for k in ["erp", "leasing software", "fleet management", "crm system", "sap", "dealer software"]):
        return "Technology"
    if any(k in text for k in ["recall", "defect", "safety", "regulation", "nhtsa", "fmcsa", "law", "illegal"]):
        return "Regulation"
    if any(k in text for k in ["market", "price", "economy", "gdp", "inflation", "fuel", "oil price", "supply chain"]):
        return "Market"
    if any(k in text for k in ["manufacture", "factory", "production", "assembly", "supply"]):
        return "Manufacturing"
    return "Market"


def detect_brand(text: str) -> str | None:
    tl = text.lower()
    for b in CAR_BRAND_KEYWORDS:
        if b in tl:
            return b.title()
    return None


def detect_insurer(text: str) -> str | None:
    tl = text.lower()
    for ins in INSURANCE_KEYWORDS:
        if ins in tl:
            return ins.title()
    return None


# ── DB ingestion ──────────────────────────────────────────────────────────────
def ingest_items(items: list[dict], label: str) -> dict:
    stats = {"articles": 0, "car_reviews": 0, "ins_reviews": 0, "skipped": 0}

    with get_db_session() as session:
        # Pre-load existing URLs to dedup
        existing_art = {r[0] for r in session.query(MarketTrendArticle.source_url).all()}
        existing_car = {r[0] for r in session.query(CarReview.source_url).all()}
        existing_ins = {r[0] for r in session.query(InsuranceReview.source_url).all()}

        # Brand & company lookup
        brands = {b.name.lower(): b for b in session.query(CarBrand).all()}
        companies = {c.name.lower(): c for c in session.query(InsuranceCompany).all()}
        # Get a default car model per brand (first one found)
        brand_models: dict[str, object] = {}
        for model in session.query(CarModel).all():
            bname = None
            for b in brands.values():
                if b.id == model.brand_id:
                    bname = b.name.lower()
                    break
            if bname and bname not in brand_models:
                brand_models[bname] = model

        for item in items:
            if item.get("dataType") != "post":
                stats["skipped"] += 1
                continue

            url   = item.get("url", "")
            title = (item.get("title") or "Reddit Post")[:500]
            body  = item.get("body") or ""
            author = (item.get("username") or "reddit_user")[:200]
            rating_raw = item.get("upVoteRatio")  # 0-1 float, map to 1-5
            rating = round(rating_raw * 5, 1) if rating_raw else None

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

            full_text = title + " " + body
            category  = detect_category(title, body)
            region    = "Global"

            # ── Try to map to CarReview ──────────────────────────────────────
            brand_name = detect_brand(full_text)
            brand_obj  = brands.get(brand_name.lower()) if brand_name else None
            model_obj  = brand_models.get(brand_name.lower()) if brand_name else None

            is_car_review = (
                brand_obj is not None
                and model_obj is not None
                and url not in existing_car
                and len(body) > 30
                and any(k in full_text.lower() for k in [
                    "drove","drive","own","bought","purchase","bought","love","hate",
                    "recommend","problem","issue","broke","miles","km","engine",
                    "review","experience","my car","my truck","my vehicle"
                ])
            )

            # ── Try to map to InsuranceReview ────────────────────────────────
            insurer_name = detect_insurer(full_text)
            insurer_obj  = companies.get(insurer_name.lower()) if insurer_name else None
            is_ins_review = (
                insurer_obj is not None
                and url not in existing_ins
                and len(body) > 30
                and any(k in full_text.lower() for k in [
                    "claim","policy","premium","coverage","deductible","adjuster",
                    "cancelled","denied","renewal","rate","quote","insurance"
                ])
            )

            # ── Insert ───────────────────────────────────────────────────────
            if is_car_review:
                cr = CarReview(
                    model_id     = model_obj.id,
                    source_url   = url,
                    rating       = rating,
                    review_title = title[:300],
                    review_text  = (body or title)[:5000],
                    author       = author,
                    review_date  = pub_date,
                    scraped_at   = scraped_dt,
                    data_origin  = "scraped",
                )
                session.add(cr)
                existing_car.add(url)
                stats["car_reviews"] += 1

            elif is_ins_review:
                ir = InsuranceReview(
                    company_id   = insurer_obj.id,
                    source_url   = url,
                    rating       = rating,
                    review_title = title[:300],
                    review_text  = (body or title)[:5000],
                    author       = author,
                    review_date  = pub_date,
                    scraped_at   = scraped_dt,
                    data_origin  = "scraped",
                )
                session.add(ir)
                existing_ins.add(url)
                stats["ins_reviews"] += 1

            # ── Always store as article too (if not dupe) ────────────────────
            if url not in existing_art:
                article = MarketTrendArticle(
                    title            = title,
                    author           = author,
                    publication_date = pub_date,
                    body_text        = (body or None)[:10000] if body else None,
                    source_url       = url,
                    category         = category,
                    region           = region,
                    scraped_at       = scraped_dt,
                    data_origin      = "scraped",
                )
                session.add(article)
                existing_art.add(url)
                stats["articles"] += 1
            else:
                if not is_car_review and not is_ins_review:
                    stats["skipped"] += 1

        session.commit()
    return stats


def main():
    print("=" * 60)
    print("Launching Apify Reddit batches...")
    print("=" * 60)

    runs = []
    for label, urls in BATCHES:
        try:
            run_id = launch_run(label, urls)
            runs.append((label, run_id))
        except Exception as e:
            print(f"  [{label}] FAILED to launch: {e}")

    print(f"\nWaiting for {len(runs)} runs to complete (up to 5 min each)...")

    total_stats = {"articles": 0, "car_reviews": 0, "ins_reviews": 0, "skipped": 0}

    for label, run_id in runs:
        print(f"\n--- [{label}] Waiting for run {run_id}...")
        run_data = wait_for_run(run_id, max_wait=400)
        status = run_data.get("status", "UNKNOWN")
        dataset_id = run_data.get("defaultDatasetId", "")
        print(f"  Status: {status} | Dataset: {dataset_id}")

        if status != "SUCCEEDED" or not dataset_id:
            print(f"  Skipping ingestion (run did not succeed)")
            continue

        try:
            items = fetch_dataset(dataset_id)
            print(f"  Fetched {len(items)} items from dataset")
            stats = ingest_items(items, label)
            print(f"  Ingested => articles: {stats['articles']}, "
                  f"car reviews: {stats['car_reviews']}, "
                  f"insurance reviews: {stats['ins_reviews']}, "
                  f"skipped: {stats['skipped']}")
            for k in total_stats:
                total_stats[k] += stats[k]
        except Exception as e:
            print(f"  ERROR during ingestion: {e}")
            import traceback; traceback.print_exc()

    print("\n" + "=" * 60)
    print("TOTAL:")
    print(f"  Articles inserted:         {total_stats['articles']}")
    print(f"  Car reviews inserted:      {total_stats['car_reviews']}")
    print(f"  Insurance reviews inserted:{total_stats['ins_reviews']}")
    print(f"  Skipped:                   {total_stats['skipped']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
