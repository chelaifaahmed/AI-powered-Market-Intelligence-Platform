"""
scripts/final_apify_scrape.py
------------------------------
One-time final scrape to maximize Reddit data before the Apify key expires.
Covers a wider range of subreddits with 250 posts each.
"""
from __future__ import annotations
import os, sys, json, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import ingestion logic from the batch script
from scripts.launch_apify_batches import (
    TOKEN, ACTOR_ID, launch_run, wait_for_run, fetch_dataset, ingest_items
)

# Extended list of subreddits — maximum coverage
FINAL_BATCHES = [
    ("cars_deep", [
        "https://www.reddit.com/r/cars/",
        "https://www.reddit.com/r/CarComplaints/",
        "https://www.reddit.com/r/UsedCars/",
        "https://www.reddit.com/r/carbuying/",
        "https://www.reddit.com/r/carreviews/",
        "https://www.reddit.com/r/whatcarshouldIbuy/",
        "https://www.reddit.com/r/Cartalk/",
        "https://www.reddit.com/r/trucks/",
    ]),
    ("insurance_deep", [
        "https://www.reddit.com/r/Insurance/",
        "https://www.reddit.com/r/personalfinance/",
        "https://www.reddit.com/r/legaladvice/",
        "https://www.reddit.com/r/povertyfinance/",
        "https://www.reddit.com/r/HealthInsurance/",
        "https://www.reddit.com/r/AutoInsurance/",
    ]),
    ("ev_market", [
        "https://www.reddit.com/r/electricvehicles/",
        "https://www.reddit.com/r/teslamotors/",
        "https://www.reddit.com/r/Rivian/",
        "https://www.reddit.com/r/leaf/",
        "https://www.reddit.com/r/volt/",
        "https://www.reddit.com/r/RenaultZoe/",
        "https://www.reddit.com/r/SolarCity/",
    ]),
    ("erp_fleet_business", [
        "https://www.reddit.com/r/smallbusiness/",
        "https://www.reddit.com/r/sysadmin/",
        "https://www.reddit.com/r/msp/",
        "https://www.reddit.com/r/ERP/",
        "https://www.reddit.com/r/logistics/",
        "https://www.reddit.com/r/fleetmanagement/",
        "https://www.reddit.com/r/supplychain/",
    ]),
    ("market_economy", [
        "https://www.reddit.com/r/economy/",
        "https://www.reddit.com/r/investing/",
        "https://www.reddit.com/r/wallstreetbets/",
        "https://www.reddit.com/r/RealEstate/",
        "https://www.reddit.com/r/Economics/",
        "https://www.reddit.com/r/Frugal/",
    ]),
]

MAX_ITEMS = 250  # Max per batch


def launch_with_max(label: str, urls: list[str]) -> str:
    """Launch run with maximum item count."""
    payload = {
        "startUrls": [{"url": u} for u in urls],
        "maxItems": MAX_ITEMS,
        "maxPostCount": MAX_ITEMS,
        "maxComments": 3,
        "sort": "new",
        "searchPosts": True,
        "skipComments": False,
        "proxy": {"useApifyProxy": True, "apifyProxyGroups": ["RESIDENTIAL"]},
        "scrollTimeout": 40,
        "includeNSFW": False,
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"https://api.apify.com/v2/acts/{ACTOR_ID}/runs?token={TOKEN}",
        data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.load(r).get("data", {})
    run_id = d.get("id", "?")
    print(f"  [{label}] launched run {run_id} ({len(urls)} subreddits, max {MAX_ITEMS} posts)")
    return run_id


def main():
    print("=" * 70)
    print("FINAL APIFY SCRAPE — maximizing data before key expiry")
    print("=" * 70)

    runs = []
    for label, urls in FINAL_BATCHES:
        try:
            run_id = launch_with_max(label, urls)
            runs.append((label, run_id))
            time.sleep(2)  # small delay between launches
        except Exception as e:
            print(f"  [{label}] FAILED to launch: {e}")

    print(f"\nAll {len(runs)} batches launched. Waiting for completion...")

    total = {"articles": 0, "car_reviews": 0, "ins_reviews": 0, "skipped": 0}

    for label, run_id in runs:
        print(f"\n--- [{label}] Waiting for run {run_id}...")
        run_data = wait_for_run(run_id, max_wait=500)
        status = run_data.get("status", "UNKNOWN")
        dataset_id = run_data.get("defaultDatasetId", "")
        print(f"  Status: {status} | Dataset: {dataset_id}")

        if status != "SUCCEEDED" or not dataset_id:
            print(f"  Skipping ingestion.")
            continue

        try:
            items = fetch_dataset(dataset_id)
            print(f"  Fetched {len(items)} items")
            stats = ingest_items(items, label)
            print(f"  → articles: {stats['articles']}, car reviews: {stats['car_reviews']}, "
                  f"ins reviews: {stats['ins_reviews']}, skipped: {stats['skipped']}")
            for k in total:
                total[k] += stats[k]
        except Exception as e:
            import traceback; traceback.print_exc()

    print("\n" + "=" * 70)
    print("FINAL TOTALS:")
    print(f"  Articles:          {total['articles']}")
    print(f"  Car reviews:       {total['car_reviews']}")
    print(f"  Insurance reviews: {total['ins_reviews']}")
    print(f"  Skipped:           {total['skipped']}")
    print("=" * 70)

    # Now export the backup
    print("\nCreating backup...")
    os.system(f'"{sys.executable}" scripts/export_reddit_backup.py')


if __name__ == "__main__":
    main()
