"""
scripts/llm_label_reviews.py
-----------------------------
Phase 1 of the LLM-assisted fine-tuning pipeline.

Uses Groq (Llama 3.3-70b-versatile) to auto-label every scraped CarReview
and InsuranceReview in the database with domain-aware sentiment labels.

Technique: "LLM-as-annotator" (weak supervision).  The large model acts as
an expert labeler that understands automotive and insurance domain language,
negation, and French/English code-switching — capabilities the downstream
distilbert-base-multilingual-cased model will learn from.

Output: data/llm_labels.jsonl
  One JSON object per line:
  {
    "id":                 str  (UUID of the source review),
    "corpus":             "car_review" | "insurance_review",
    "text":               str  (review_text, truncated to 1200 chars),
    "rating":             float | null,
    "language":           "en" | "fr" | "ar" | "other",
    "sentiment":          "positive" | "negative" | "neutral",
    "confidence":         float  [0.0 – 1.0],
    "complaint_category": str,
    "reasoning":          str,
    "labeled_at":         ISO-8601 datetime string
  }

Resume behaviour:
  Already-labeled IDs are loaded from the JSONL at startup and skipped.
  Safe to re-run after interruption.

Rate limiting:
  Groq free tier allows 30 RPM for llama-3.3-70b-versatile.
  This script enforces a 2.2 s inter-request delay (~27 RPM) for safety.

Usage:
    python -m scripts.llm_label_reviews
    python -m scripts.llm_label_reviews --limit 200     # label first N reviews
    python -m scripts.llm_label_reviews --corpus car    # car reviews only
    python -m scripts.llm_label_reviews --corpus insurance
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv(_ROOT / ".env")

from database.connection import get_db_session
from database.models import CarReview, InsuranceReview

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

OUTPUT_PATH = _ROOT / "data" / "llm_labels.jsonl"
GROQ_MODEL  = "llama-3.3-70b-versatile"
REQUEST_DELAY_S = 5.0          # 12k TPM limit / ~600 tokens per call ≈ 20 RPM max → 5s safe
MAX_TEXT_CHARS  = 500          # keep input tokens low (~130 tokens of text per call)
CONFIDENCE_WARN = 0.70         # log a warning if confidence drops below this
MAX_RETRIES     = 3            # retry on TPM 429 with backoff (same key)

# ---------------------------------------------------------------------------
# Multi-key support — rotates on TPD exhaustion
# ---------------------------------------------------------------------------

def _load_groq_keys() -> list[str]:
    """Return all GROQ_API_KEY / GROQ_API_KEY_2 … keys found in environment."""
    keys: list[str] = []
    primary = os.environ.get("GROQ_API_KEY", "").strip()
    if primary:
        keys.append(primary)
    for i in range(2, 10):
        k = os.environ.get(f"GROQ_API_KEY_{i}", "").strip()
        if k:
            keys.append(k)
    return keys

# ---------------------------------------------------------------------------
# Groq system prompt — domain-specific, bilingual (EN/FR)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an expert NLP annotator specialising in the automotive \
and insurance industries. You label customer reviews for a B2B market intelligence \
platform that monitors car brands (Toyota, Hyundai, Renault, Peugeot, Kia …) and \
insurance companies (AXA, Allianz, Admiral, Star Assurances, STAR …) operating in \
Tunisia and Europe.

Your task: read the review and return a single JSON object with EXACTLY these fields:

{
  "sentiment":          "positive" | "negative" | "neutral",
  "confidence":         <float, 0.0–1.0>,
  "complaint_category": "engine_issues" | "battery_issues" | "claims_delays" | \
"policy_pricing" | "customer_service" | "general_dissatisfaction" | "none",
  "language":           "en" | "fr" | "ar" | "other",
  "reasoning":          "<one concise sentence explaining the label>"
}

Labeling rules:
1. sentiment="positive"  → overall satisfaction, praise, recommendation, loyalty.
2. sentiment="negative"  → dissatisfaction, complaint, warning, disappointment, \
   regret. Domain cues: "claim denied/pending", "knocking/stall/misfire", \
   "rate hike", "no response", "slow settlement" are NEGATIVE even without \
   explicit negative adjectives.
3. sentiment="neutral"   → purely factual, deeply mixed, or insufficient content.
4. confidence ≥ 0.85     → text is clearly positive or negative.
   confidence 0.65–0.84  → mostly clear with minor ambiguity.
   confidence < 0.65     → mixed, too short, or language you cannot parse.
5. complaint_category    → choose the PRIMARY complaint category if negative, \
   else "none".
6. language              → main language of the review text.

Return ONLY the JSON object. No markdown, no explanation outside the JSON."""

# ---------------------------------------------------------------------------
# Load already-labeled IDs (resume support)
# ---------------------------------------------------------------------------

def _load_labeled_ids() -> set[str]:
    if not OUTPUT_PATH.exists():
        return set()
    ids: set[str] = set()
    with OUTPUT_PATH.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                ids.add(json.loads(line)["id"])
            except (json.JSONDecodeError, KeyError):
                pass
    return ids


# ---------------------------------------------------------------------------
# Single-review labeling call
# ---------------------------------------------------------------------------

_TPD_EXHAUSTED = object()   # sentinel returned when daily quota is fully used

def _label_one(client, corpus: str, review_id: str, text: str,
               rating: float | None) -> dict | None:
    """
    Call Groq and parse the JSON response.
    Returns a dict on success, None on parse failure, or _TPD_EXHAUSTED sentinel
    when the daily token quota for this key is exhausted (triggers key rotation).
    Retries up to MAX_RETRIES times on TPM 429s with exponential backoff.
    """
    rating_line = f"Star rating: {rating}/5\n" if rating is not None else ""
    user_msg = (
        f"Review type: {corpus}\n"
        f"{rating_line}"
        f"Review text:\n{text[:MAX_TEXT_CHARS]}"
    )

    for attempt in range(MAX_RETRIES):
        try:
            completion = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": user_msg},
                ],
                temperature=0.0,
                max_tokens=220,
                response_format={"type": "json_object"},
            )
            break  # success — exit retry loop
        except Exception as exc:
            err = str(exc)
            if "429" in err:
                # TPD (tokens per day) exhausted → signal key rotation
                if "tokens per day" in err or "per day (TPD)" in err:
                    return _TPD_EXHAUSTED
                # TPM (tokens per minute) → backoff and retry same key
                if attempt < MAX_RETRIES - 1:
                    wait = 10 * (attempt + 1)
                    print(f"  [429] TPM limit — waiting {wait}s before retry {attempt+2}/{MAX_RETRIES}…")
                    time.sleep(wait)
                    continue
            print(f"  [ERROR] Groq call failed for {review_id}: {exc}")
            return None

    try:
        raw = completion.choices[0].message.content.strip()
        data = json.loads(raw)

        # Validate required fields
        for field in ("sentiment", "confidence", "complaint_category",
                      "language", "reasoning"):
            if field not in data:
                print(f"  [WARN] Missing field '{field}' for {review_id}: {raw[:80]}")
                return None

        if data["sentiment"] not in ("positive", "negative", "neutral"):
            print(f"  [WARN] Invalid sentiment '{data['sentiment']}' for {review_id}")
            return None

        confidence = float(data["confidence"])
        if confidence < CONFIDENCE_WARN:
            print(f"  [INFO] Low confidence ({confidence:.2f}) for {review_id[:8]}…")

        return {
            "id":                 review_id,
            "corpus":             corpus,
            "text":               text[:MAX_TEXT_CHARS],
            "rating":             float(rating) if rating is not None else None,
            "language":           data.get("language", "other"),
            "sentiment":          data["sentiment"],
            "confidence":         confidence,
            "complaint_category": data.get("complaint_category", "none"),
            "reasoning":          data.get("reasoning", ""),
            "labeled_at":         datetime.now(timezone.utc).isoformat(),
        }

    except json.JSONDecodeError as exc:
        print(f"  [ERROR] JSON parse failed for {review_id}: {exc}")
        return None
    except Exception as exc:
        print(f"  [ERROR] Groq call failed for {review_id}: {exc}")
        return None


# ---------------------------------------------------------------------------
# Main labeling loop
# ---------------------------------------------------------------------------

def run(limit: int | None = None, corpus_filter: str = "all") -> None:
    from groq import Groq

    api_keys = _load_groq_keys()
    if not api_keys:
        print("ERROR: No GROQ_API_KEY found in .env")
        sys.exit(1)

    key_idx = 0
    client  = Groq(api_key=api_keys[key_idx])
    print(f"Loaded {len(api_keys)} Groq API key(s). Starting with key #1.")

    def _next_key() -> bool:
        """Rotate to next key. Returns False if all keys exhausted."""
        nonlocal key_idx, client
        key_idx += 1
        if key_idx >= len(api_keys):
            return False
        print(f"\n  [KEY ROTATION] Key #{key_idx} TPD exhausted — switching to key #{key_idx + 1}…")
        client = Groq(api_key=api_keys[key_idx])
        return True

    already_labeled = _load_labeled_ids()
    print(f"Resuming: {len(already_labeled)} reviews already labeled.")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    outfile = OUTPUT_PATH.open("a", encoding="utf-8")

    total_labeled = 0
    total_skipped = 0
    total_failed  = 0

    with get_db_session() as session:

        # --- Car reviews ---
        if corpus_filter in ("all", "car"):
            car_rows = (
                session.query(CarReview)
                .filter(CarReview.data_origin == "scraped")
                .filter(CarReview.review_text.isnot(None))
                .order_by(CarReview.scraped_at.desc())
                .all()
            )
            print(f"\nCar reviews to process: {len(car_rows)}")
            all_keys_exhausted = False
            for row in car_rows:
                if all_keys_exhausted or (limit and total_labeled >= limit):
                    break
                rid = str(row.id)
                if rid in already_labeled:
                    total_skipped += 1
                    continue

                while True:
                    result = _label_one(
                        client, "car_review", rid,
                        row.review_text, float(row.rating) if row.rating else None
                    )
                    if result is _TPD_EXHAUSTED:
                        if not _next_key():
                            print("  [STOP] All API keys exhausted for today.")
                            all_keys_exhausted = True
                            break
                        continue  # retry same review with new key
                    break

                if all_keys_exhausted:
                    break
                if result:
                    outfile.write(json.dumps(result, ensure_ascii=False) + "\n")
                    outfile.flush()
                    total_labeled += 1
                    print(f"  [{total_labeled}] car  {rid[:8]}… "
                          f"{result['sentiment']:8s} "
                          f"conf={result['confidence']:.2f}  "
                          f"lang={result['language']}")
                else:
                    total_failed += 1

                time.sleep(REQUEST_DELAY_S)

        # --- Insurance reviews ---
        if corpus_filter in ("all", "insurance"):
            ins_rows = (
                session.query(InsuranceReview)
                .filter(InsuranceReview.data_origin == "scraped")
                .filter(InsuranceReview.review_text.isnot(None))
                .order_by(InsuranceReview.scraped_at.desc())
                .all()
            )
            print(f"\nInsurance reviews to process: {len(ins_rows)}")
            all_keys_exhausted = False
            for row in ins_rows:
                if all_keys_exhausted or (limit and total_labeled >= limit):
                    break
                rid = str(row.id)
                if rid in already_labeled:
                    total_skipped += 1
                    continue

                while True:
                    result = _label_one(
                        client, "insurance_review", rid,
                        row.review_text, float(row.rating) if row.rating else None
                    )
                    if result is _TPD_EXHAUSTED:
                        if not _next_key():
                            print("  [STOP] All API keys exhausted for today.")
                            all_keys_exhausted = True
                            break
                        continue
                    break

                if all_keys_exhausted:
                    break
                if result:
                    outfile.write(json.dumps(result, ensure_ascii=False) + "\n")
                    outfile.flush()
                    total_labeled += 1
                    print(f"  [{total_labeled}] ins  {rid[:8]}… "
                          f"{result['sentiment']:8s} "
                          f"conf={result['confidence']:.2f}  "
                          f"lang={result['language']}")
                else:
                    total_failed += 1

                time.sleep(REQUEST_DELAY_S)

    outfile.close()

    print(f"\n{'='*55}")
    print(f"Labeling complete.")
    print(f"  New labels written : {total_labeled}")
    print(f"  Skipped (existing) : {total_skipped}")
    print(f"  Failed / unparsable: {total_failed}")
    print(f"  Output file        : {OUTPUT_PATH}")
    print(f"{'='*55}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Auto-label reviews with Groq Llama 3.3-70b."
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Maximum number of NEW labels to generate (default: all)."
    )
    parser.add_argument(
        "--corpus", choices=["all", "car", "insurance"], default="all",
        help="Which corpus to label (default: all)."
    )
    args = parser.parse_args()
    run(limit=args.limit, corpus_filter=args.corpus)


if __name__ == "__main__":
    main()
