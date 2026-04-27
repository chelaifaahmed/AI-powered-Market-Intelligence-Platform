"""
scripts/evaluate_sentiment.py
-------------------------------
Phase 3 of the LLM-assisted fine-tuning pipeline.

Performs a rigorous comparison between:
  A. Baseline  — distilbert-base-uncased-finetuned-sst-2-english  (SST-2)
  B. Fine-tuned — models/sentiment-automotive-v1/  (domain-adapted)

Two evaluation protocols are used:

  1. LLM-labeled validation set (data/val_set.jsonl)
     The 20% held-out split from the fine-tuning dataset.
     Ground truth = Groq Llama 3.3-70b pseudo-labels.

  2. Rating-anchored gold set (queried live from the database)
     Reviews with extreme star ratings are used as proxy ground truth:
       rating >= 4.5  →  positive
       rating <= 2.0  →  negative
     This set is INDEPENDENT of the LLM labels and validates both models
     against a human-observable signal.

Metrics reported for each protocol × model:
  - Overall accuracy
  - Macro F1
  - Weighted F1
  - Per-class precision / recall / F1
  - Confusion matrix
  - Language-stratified accuracy (EN vs FR)

Disagreement analysis:
  Reviews where the two models disagree are printed to help interpret the
  qualitative difference in domain understanding.

Output:
  data/evaluation_report.json   (machine-readable, for the academic report)

Usage:
    python -m scripts.evaluate_sentiment
"""

from __future__ import annotations

import io
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Force UTF-8 output on Windows (avoids cp1252 UnicodeEncodeError)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import numpy as np

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv(_ROOT / ".env")

# ---------------------------------------------------------------------------
# Paths and constants
# ---------------------------------------------------------------------------

VAL_SET_PATH   = _ROOT / "data" / "val_set.jsonl"
FINETUNED_DIR  = _ROOT / "models" / "sentiment-automotive-v1"
REPORT_PATH    = _ROOT / "data" / "evaluation_report.json"

SST2_MODEL_ID  = "distilbert-base-uncased-finetuned-sst-2-english"
NEUTRAL_THRESHOLD = 0.65   # mirrors nlp/sentiment_analyzer.py

LABEL2ID = {"negative": 0, "neutral": 1, "positive": 2}
ID2LABEL = {0: "negative", 1: "neutral", 2: "positive"}

# ---------------------------------------------------------------------------
# SST-2 baseline inference (3-class with neutral threshold)
# ---------------------------------------------------------------------------

def _load_sst2():
    from transformers import pipeline as hf_pipeline
    print(f"Loading SST-2 baseline: {SST2_MODEL_ID} …")
    return hf_pipeline(
        "sentiment-analysis",
        model=SST2_MODEL_ID,
        truncation=True,
        max_length=512,
    )


def _sst2_predict(pipe, texts: list[str]) -> list[int]:
    """Run SST-2 and map to 3-class labels with neutral threshold."""
    preds = []
    for text in texts:
        result = pipe(text[:2000])[0]
        confidence = float(result["score"])
        if confidence < NEUTRAL_THRESHOLD:
            preds.append(LABEL2ID["neutral"])
        elif result["label"].upper() == "POSITIVE":
            preds.append(LABEL2ID["positive"])
        else:
            preds.append(LABEL2ID["negative"])
    return preds


# ---------------------------------------------------------------------------
# Fine-tuned model inference
# ---------------------------------------------------------------------------

def _load_finetuned():
    from transformers import pipeline as hf_pipeline
    if not FINETUNED_DIR.exists():
        print(f"ERROR: Fine-tuned model not found at {FINETUNED_DIR}")
        print("Run   python -m scripts.finetune_sentiment   first.")
        sys.exit(1)
    print(f"Loading fine-tuned model: {FINETUNED_DIR} …")
    return hf_pipeline(
        "text-classification",
        model=str(FINETUNED_DIR),
        tokenizer=str(FINETUNED_DIR),
        truncation=True,
        max_length=256,
    )


def _finetuned_predict(pipe, texts: list[str]) -> list[int]:
    """Run fine-tuned model and map label strings to ints."""
    preds = []
    for text in texts:
        result = pipe(text[:2000])[0]
        label_str = result["label"].lower()
        preds.append(LABEL2ID.get(label_str, LABEL2ID["neutral"]))
    return preds


# ---------------------------------------------------------------------------
# Metrics helpers
# ---------------------------------------------------------------------------

def _classification_metrics(y_true: list[int], y_pred: list[int]) -> dict:
    from sklearn.metrics import (
        accuracy_score, f1_score, precision_score,
        recall_score, confusion_matrix, classification_report
    )
    acc = accuracy_score(y_true, y_pred)
    f1_macro     = f1_score(y_true, y_pred, average="macro",    zero_division=0)
    f1_weighted  = f1_score(y_true, y_pred, average="weighted", zero_division=0)
    prec_per_cls = precision_score(y_true, y_pred, average=None,
                                   labels=[0, 1, 2], zero_division=0)
    rec_per_cls  = recall_score(y_true, y_pred, average=None,
                                labels=[0, 1, 2], zero_division=0)
    f1_per_cls   = f1_score(y_true, y_pred, average=None,
                            labels=[0, 1, 2], zero_division=0)
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1, 2]).tolist()

    return {
        "accuracy":    round(float(acc), 4),
        "f1_macro":    round(float(f1_macro), 4),
        "f1_weighted": round(float(f1_weighted), 4),
        "per_class": {
            ID2LABEL[i]: {
                "precision": round(float(prec_per_cls[i]), 4),
                "recall":    round(float(rec_per_cls[i]),  4),
                "f1":        round(float(f1_per_cls[i]),   4),
            }
            for i in range(3)
        },
        "confusion_matrix": {
            "labels": ["negative", "neutral", "positive"],
            "matrix": cm,
        },
    }


def _language_accuracy(samples: list[dict],
                        y_pred: list[int]) -> dict[str, dict]:
    """Compute per-language accuracy."""
    by_lang: dict[str, list[tuple[int, int]]] = {}
    for s, pred in zip(samples, y_pred):
        lang = s.get("language", "other")
        by_lang.setdefault(lang, []).append((s["label"], pred))

    result = {}
    for lang, pairs in by_lang.items():
        true_vals  = [p[0] for p in pairs]
        pred_vals  = [p[1] for p in pairs]
        correct = sum(t == p for t, p in zip(true_vals, pred_vals))
        result[lang] = {
            "n":        len(pairs),
            "accuracy": round(correct / len(pairs), 4),
        }
    return result


# ---------------------------------------------------------------------------
# Rating-anchored gold set — loaded from held-out test_set.jsonl
# ---------------------------------------------------------------------------

_TEST_SET_PATH = _ROOT / "data" / "test_set.jsonl"

def _build_rating_gold_set() -> list[dict]:
    """
    Load the held-out test set produced by build_training_set.py.
    This set was never used in training or val — no data leakage.
    Falls back to querying all rated reviews if test_set.jsonl doesn't exist
    (legacy behaviour, noted as potentially leaky in the report).
    """
    if _TEST_SET_PATH.exists():
        samples = []
        with _TEST_SET_PATH.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                samples.append({
                    "text":   obj["text"],
                    "label":  obj["label"],
                    "rating": obj.get("rating"),
                    "corpus": obj.get("corpus", "unknown"),
                })
        print(f"Held-out test set (no leakage): {len(samples)} reviews")
        dist = {0: 0, 1: 0, 2: 0}
        for s in samples:
            dist[s["label"]] += 1
        print(f"  negative={dist[0]}  neutral={dist[1]}  positive={dist[2]}")
        return samples

    # Legacy fallback — warns about leakage
    print("WARNING: test_set.jsonl not found. Run build_training_set.py first.")
    print("         Falling back to full rating pool (CONTAINS TRAINING DATA — results inflated).")
    from database.connection import get_db_session
    from database.models import CarReview, InsuranceReview

    samples = []
    with get_db_session() as session:
        for Model, corpus_name in [
            (CarReview, "car_review"),
            (InsuranceReview, "insurance_review"),
        ]:
            for row in session.query(Model).filter(
                Model.data_origin == "scraped",
                Model.rating.isnot(None),
            ).all():
                r = float(row.rating)
                if r >= 4.5:
                    label = LABEL2ID["positive"]
                elif r <= 2.0:
                    label = LABEL2ID["negative"]
                else:
                    continue
                samples.append({
                    "text":   row.review_text[:1200],
                    "label":  label,
                    "rating": r,
                    "corpus": corpus_name,
                })

    print(f"[LEGACY] Full rating pool: {len(samples)} reviews (leaky — use build_training_set.py)")
    return samples


# ---------------------------------------------------------------------------
# Disagreement examples
# ---------------------------------------------------------------------------

def _disagreement_examples(
    samples: list[dict],
    sst2_preds: list[int],
    ft_preds:   list[int],
    n: int = 8,
) -> list[dict]:
    """Return N examples where the two models predict differently."""
    examples = []
    for s, sp, fp in zip(samples, sst2_preds, ft_preds):
        if sp != fp:
            examples.append({
                "text":          s["text"][:200] + "…",
                "true_label":    ID2LABEL.get(s.get("label", -1), "N/A"),
                "sst2_pred":     ID2LABEL[sp],
                "finetuned_pred": ID2LABEL[fp],
                "corpus":        s.get("corpus", ""),
            })
    return examples[:n]


# ---------------------------------------------------------------------------
# Pretty-print helpers
# ---------------------------------------------------------------------------

def _print_metrics_table(name: str, metrics: dict) -> None:
    print(f"\n  {name}")
    print(f"  {'-'*45}")
    print(f"  {'Accuracy':<20}: {metrics['accuracy']:.4f}")
    print(f"  {'Macro F1':<20}: {metrics['f1_macro']:.4f}")
    print(f"  {'Weighted F1':<20}: {metrics['f1_weighted']:.4f}")
    print(f"  Per-class breakdown:")
    for cls, vals in metrics["per_class"].items():
        print(f"    {cls:<12}  P={vals['precision']:.3f}  "
              f"R={vals['recall']:.3f}  F1={vals['f1']:.3f}")


# ---------------------------------------------------------------------------
# Main evaluation routine
# ---------------------------------------------------------------------------

def evaluate() -> None:
    # 1. Load models
    sst2_pipe = _load_sst2()
    ft_pipe   = _load_finetuned()

    report: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "baseline_model":  SST2_MODEL_ID,
        "finetuned_model": str(FINETUNED_DIR),
    }

    # =========================================================
    # PROTOCOL 1 — LLM-labeled validation set
    # =========================================================
    print(f"\n{'='*55}")
    print("PROTOCOL 1 — LLM-labeled validation set")
    print(f"{'='*55}")

    if not VAL_SET_PATH.exists():
        print(f"WARNING: {VAL_SET_PATH} not found. Skipping protocol 1.")
        print("Run finetune_sentiment.py first to generate this file.")
        report["protocol_1"] = {"error": "val_set.jsonl not found"}
    else:
        val_samples: list[dict] = []
        with VAL_SET_PATH.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    val_samples.append(json.loads(line))

        print(f"Loaded {len(val_samples)} validation samples.")
        texts  = [s["text"]  for s in val_samples]
        labels = [s["label"] for s in val_samples]

        print("Running SST-2 baseline inference …")
        sst2_preds = _sst2_predict(sst2_pipe, texts)

        print("Running fine-tuned model inference …")
        ft_preds = _finetuned_predict(ft_pipe, texts)

        sst2_metrics = _classification_metrics(labels, sst2_preds)
        ft_metrics   = _classification_metrics(labels, ft_preds)

        print("\n--- Results ---")
        _print_metrics_table("SST-2 Baseline",   sst2_metrics)
        _print_metrics_table("Fine-tuned Model", ft_metrics)

        delta_acc = ft_metrics["accuracy"] - sst2_metrics["accuracy"]
        delta_f1  = ft_metrics["f1_macro"] - sst2_metrics["f1_macro"]
        print(f"\n  Δ Accuracy  (fine-tuned − baseline): {delta_acc:+.4f}")
        print(f"  Δ Macro F1  (fine-tuned − baseline): {delta_f1:+.4f}")

        sst2_lang = _language_accuracy(val_samples, sst2_preds)
        ft_lang   = _language_accuracy(val_samples, ft_preds)

        print("\n  Language-stratified accuracy:")
        all_langs = sorted(set(list(sst2_lang.keys()) + list(ft_lang.keys())))
        for lang in all_langs:
            s = sst2_lang.get(lang, {})
            f = ft_lang.get(lang,   {})
            print(f"    {lang:<6}  n={s.get('n',0):3d}  "
                  f"SST-2={s.get('accuracy','N/A'):.3f}  "
                  f"FT={f.get('accuracy','N/A'):.3f}")

        disagree = _disagreement_examples(val_samples, sst2_preds, ft_preds)
        if disagree:
            print(f"\n  Sample disagreements (first {len(disagree)}):")
            for ex in disagree[:4]:
                print(f"    [{ex['corpus'][:3]}]  true={ex['true_label']:<9} "
                      f"sst2={ex['sst2_pred']:<9} ft={ex['finetuned_pred']}")
                print(f"         \"{ex['text'][:100]}\"")

        report["protocol_1"] = {
            "n_samples":         len(val_samples),
            "sst2_metrics":      sst2_metrics,
            "finetuned_metrics": ft_metrics,
            "delta_accuracy":    round(delta_acc, 4),
            "delta_f1_macro":    round(delta_f1,  4),
            "language_accuracy": {
                "sst2":      sst2_lang,
                "finetuned": ft_lang,
            },
            "disagreement_examples": disagree,
        }

    # =========================================================
    # PROTOCOL 2 — Rating-anchored gold set
    # =========================================================
    print(f"\n{'='*55}")
    print("PROTOCOL 2 — Rating-anchored gold set")
    print(f"{'='*55}")

    gold_samples = _build_rating_gold_set()

    if len(gold_samples) < 10:
        print("WARNING: Too few rating-anchored samples. Skipping protocol 2.")
        report["protocol_2"] = {"error": "insufficient rating-anchored samples"}
    else:
        gold_texts  = [s["text"]  for s in gold_samples]
        gold_labels = [s["label"] for s in gold_samples]

        print("Running SST-2 on gold set …")
        gold_sst2 = _sst2_predict(sst2_pipe, gold_texts)

        print("Running fine-tuned model on gold set …")
        gold_ft = _finetuned_predict(ft_pipe, gold_texts)

        gold_sst2_metrics = _classification_metrics(gold_labels, gold_sst2)
        gold_ft_metrics   = _classification_metrics(gold_labels, gold_ft)

        print("\n--- Results (rating-anchored ground truth) ---")
        _print_metrics_table("SST-2 Baseline",   gold_sst2_metrics)
        _print_metrics_table("Fine-tuned Model", gold_ft_metrics)

        delta_acc = gold_ft_metrics["accuracy"] - gold_sst2_metrics["accuracy"]
        delta_f1  = gold_ft_metrics["f1_macro"] - gold_sst2_metrics["f1_macro"]
        print(f"\n  Δ Accuracy  (fine-tuned − baseline): {delta_acc:+.4f}")
        print(f"  Δ Macro F1  (fine-tuned − baseline): {delta_f1:+.4f}")

        report["protocol_2"] = {
            "n_samples":         len(gold_samples),
            "sst2_metrics":      gold_sst2_metrics,
            "finetuned_metrics": gold_ft_metrics,
            "delta_accuracy":    round(delta_acc, 4),
            "delta_f1_macro":    round(delta_f1,  4),
        }

    # =========================================================
    # Save report
    # =========================================================
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with REPORT_PATH.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)

    print(f"\n{'='*55}")
    print(f"Evaluation report saved to: {REPORT_PATH}")
    print(f"{'='*55}\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    evaluate()
