"""
scripts/finetune_sentiment.py
------------------------------
Phase 2 of the LLM-assisted fine-tuning pipeline.

Loads the auto-labeled dataset produced by llm_label_reviews.py and
fine-tunes distilbert-base-multilingual-cased for 3-class sentiment
classification (negative / neutral / positive).

Model choice rationale:
  distilbert-base-multilingual-cased supports 104 languages including
  French and English, making it appropriate for the bilingual
  automotive/insurance corpus scraped from Tunisian and European sources.
  It is 40% smaller than bert-base-multilingual-cased while retaining
  ~97% of its performance (Sanh et al., 2019).

Fine-tuning strategy:
  - All encoder layers are unfrozen (full fine-tuning).
  - 4 training epochs with early stopping on macro-F1.
  - AdamW optimiser, lr=2e-5, weight_decay=0.01, warmup_ratio=0.1.
  - Confidence threshold: only samples with LLM confidence >= 0.85 are
    included in training, to suppress noisy pseudo-labels.
  - Stratified 80/20 train/validation split.

Output:
  models/sentiment-automotive-v1/   (HuggingFace model directory)
    config.json, pytorch_model.bin, tokenizer files, label_map.json

Usage:
    python -m scripts.finetune_sentiment
    python -m scripts.finetune_sentiment --confidence 0.90 --epochs 5
    python -m scripts.finetune_sentiment --labels data/llm_labels.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_MODEL     = "distilbert-base-multilingual-cased"
DEFAULT_LABELS = _ROOT / "data" / "llm_labels.jsonl"
OUTPUT_DIR     = _ROOT / "models" / "sentiment-automotive-v1"
MAX_SEQ_LEN    = 256      # tokens — balances coverage vs. speed on CPU
TRAIN_EPOCHS   = 4
BATCH_TRAIN    = 16
BATCH_EVAL     = 32
LEARNING_RATE  = 2e-5
WEIGHT_DECAY   = 0.01
WARMUP_RATIO   = 0.1
SEED           = 42

LABEL2ID = {"negative": 0, "neutral": 1, "positive": 2}
ID2LABEL = {0: "negative", 1: "neutral", 2: "positive"}

# ---------------------------------------------------------------------------
# Data loading and filtering
# ---------------------------------------------------------------------------

def load_labels(jsonl_path: Path, confidence_threshold: float) -> list[dict]:
    """
    Load JSONL labels and return only rows above confidence_threshold.
    Each returned dict has keys: text, label (int), sentiment (str),
    language, corpus, confidence.
    """
    if not jsonl_path.exists():
        print(f"ERROR: Label file not found: {jsonl_path}")
        print("Run   python -m scripts.llm_label_reviews   first.")
        sys.exit(1)

    all_rows, kept_rows = 0, 0
    samples: list[dict] = []
    skip_reasons: Counter = Counter()

    with jsonl_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            all_rows += 1
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                skip_reasons["json_error"] += 1
                continue

            sentiment = obj.get("sentiment", "")
            confidence = float(obj.get("confidence", 0.0))
            text = obj.get("text", "").strip()

            if sentiment not in LABEL2ID:
                skip_reasons["invalid_sentiment"] += 1
                continue
            if confidence < confidence_threshold:
                skip_reasons["low_confidence"] += 1
                continue
            if len(text) < 10:
                skip_reasons["too_short"] += 1
                continue

            samples.append({
                "text":       text,
                "label":      LABEL2ID[sentiment],
                "sentiment":  sentiment,
                "language":   obj.get("language", "other"),
                "corpus":     obj.get("corpus", "unknown"),
                "confidence": confidence,
            })
            kept_rows += 1

    print(f"\nDataset statistics (confidence >= {confidence_threshold}):")
    print(f"  Total rows in file  : {all_rows}")
    print(f"  Kept for training   : {kept_rows}")
    print(f"  Skipped             : {all_rows - kept_rows}")
    for reason, count in skip_reasons.items():
        print(f"    {reason:<22}: {count}")

    label_dist = Counter(s["sentiment"] for s in samples)
    print(f"\n  Label distribution:")
    for lbl, cnt in sorted(label_dist.items()):
        pct = 100 * cnt / kept_rows if kept_rows else 0
        print(f"    {lbl:<10}: {cnt:4d}  ({pct:.1f}%)")

    lang_dist = Counter(s["language"] for s in samples)
    print(f"\n  Language distribution:")
    for lang, cnt in sorted(lang_dist.items()):
        print(f"    {lang:<8}: {cnt:4d}")

    if kept_rows < 50:
        print(f"\nWARNING: Only {kept_rows} samples after filtering. "
              "Consider lowering --confidence or running more labeling.")

    return samples


# ---------------------------------------------------------------------------
# Stratified 80/20 split
# ---------------------------------------------------------------------------

def stratified_split(
    samples: list[dict], val_ratio: float = 0.20, seed: int = SEED
) -> tuple[list[dict], list[dict]]:
    """
    Stratified split preserving class proportions in both splits.
    """
    rng = np.random.default_rng(seed)
    by_label: dict[int, list[dict]] = {}
    for s in samples:
        by_label.setdefault(s["label"], []).append(s)

    train, val = [], []
    for label_id, group in by_label.items():
        idx = rng.permutation(len(group))
        n_val = max(1, int(len(group) * val_ratio))
        val   += [group[i] for i in idx[:n_val]]
        train += [group[i] for i in idx[n_val:]]

    rng.shuffle(train)
    rng.shuffle(val)
    return train, val


# ---------------------------------------------------------------------------
# HuggingFace Dataset wrapper
# ---------------------------------------------------------------------------

def _to_hf_dataset(samples: list[dict], tokenizer):
    from datasets import Dataset

    texts  = [s["text"]  for s in samples]
    labels = [s["label"] for s in samples]

    encodings = tokenizer(
        texts,
        truncation=True,
        padding="max_length",
        max_length=MAX_SEQ_LEN,
        return_tensors=None,
    )
    data_dict = {k: v for k, v in encodings.items()}
    data_dict["labels"] = labels
    return Dataset.from_dict(data_dict)


# ---------------------------------------------------------------------------
# Class-weight computation (handles severe label imbalance)
# ---------------------------------------------------------------------------

def compute_class_weights(samples: list[dict]) -> list[float]:
    """
    Inverse-frequency class weights: w_c = N / (n_classes * count_c).
    Upweights underrepresented classes (positive, neutral) to prevent the
    model collapsing to always predicting the majority class (negative).
    """
    from collections import Counter
    counts = Counter(s["label"] for s in samples)
    n_total = len(samples)
    n_classes = 3
    weights = []
    for i in range(n_classes):
        c = counts.get(i, 1)   # avoid division by zero
        weights.append(n_total / (n_classes * c))
    print(f"\n  Class weights (inverse-frequency):")
    for i, w in enumerate(weights):
        print(f"    {ID2LABEL[i]:<10}: {w:.3f}  (n={counts.get(i, 0)})")
    return weights


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def _compute_metrics(eval_pred):
    from sklearn.metrics import f1_score, accuracy_score

    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    acc   = accuracy_score(labels, preds)
    f1_macro  = f1_score(labels, preds, average="macro",  zero_division=0)
    f1_weighted = f1_score(labels, preds, average="weighted", zero_division=0)
    return {
        "accuracy":     round(acc, 4),
        "f1_macro":     round(f1_macro, 4),
        "f1_weighted":  round(f1_weighted, 4),
    }


# ---------------------------------------------------------------------------
# Weighted Trainer — applies inverse-frequency class weights to cross-entropy
# ---------------------------------------------------------------------------

class WeightedTrainer:
    """
    Factory that returns a Trainer subclass with weighted cross-entropy loss.
    Defined as a factory to keep the import of torch inside the function
    so the module stays importable even without torch installed.
    """
    @staticmethod
    def build(class_weights: list[float], **trainer_kwargs):
        import torch
        from torch import nn
        from transformers import Trainer

        weight_tensor = torch.tensor(class_weights, dtype=torch.float)

        class _WeightedTrainer(Trainer):
            def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
                labels = inputs.pop("labels")
                outputs = model(**inputs)
                logits  = outputs.logits
                w = weight_tensor.to(logits.device)
                loss = nn.CrossEntropyLoss(weight=w)(logits, labels)
                return (loss, outputs) if return_outputs else loss

        return _WeightedTrainer(**trainer_kwargs)


# ---------------------------------------------------------------------------
# Fine-tuning entry point
# ---------------------------------------------------------------------------

def finetune(
    labels_path: Path,
    confidence_threshold: float,
    epochs: int,
    val_path: Path | None = None,
) -> None:
    from transformers import (
        AutoTokenizer,
        AutoModelForSequenceClassification,
        TrainingArguments,
    )

    print(f"\n{'='*60}")
    print(f"  LLM-Assisted Fine-Tuning — TEAMWILL Sentiment Model")
    print(f"  Base model : {BASE_MODEL}")
    print(f"  Output     : {OUTPUT_DIR}")
    print(f"{'='*60}\n")

    # 1. Load and filter data
    samples = load_labels(labels_path, confidence_threshold)
    if len(samples) < 20:
        print("Too few samples to fine-tune. Aborting.")
        sys.exit(1)

    if val_path is not None and val_path.exists():
        train_data = samples
        val_data   = load_labels(val_path, confidence_threshold=0.0)
        print(f"\nUsing pre-built val set: {len(train_data)} train / {len(val_data)} validation")
    else:
        train_data, val_data = stratified_split(samples)
        print(f"\nAuto-split: {len(train_data)} train / {len(val_data)} validation")

    # 2. Tokenizer
    print(f"\nLoading tokenizer: {BASE_MODEL} …")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)

    # 3. Encode datasets
    print("Tokenizing datasets …")
    train_ds = _to_hf_dataset(train_data, tokenizer)
    val_ds   = _to_hf_dataset(val_data,   tokenizer)

    # 4. Model
    print(f"Loading model: {BASE_MODEL} …")
    model = AutoModelForSequenceClassification.from_pretrained(
        BASE_MODEL,
        num_labels=3,
        id2label=ID2LABEL,
        label2id=LABEL2ID,
    )
    total_params = sum(p.numel() for p in model.parameters())
    trainable    = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"  Parameters  : {total_params:,}  ({trainable:,} trainable)")

    # 5. Training arguments
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    training_args = TrainingArguments(
        output_dir=str(OUTPUT_DIR),
        num_train_epochs=epochs,
        per_device_train_batch_size=BATCH_TRAIN,
        per_device_eval_batch_size=BATCH_EVAL,
        learning_rate=LEARNING_RATE,
        weight_decay=WEIGHT_DECAY,
        warmup_ratio=WARMUP_RATIO,
        eval_strategy="epoch",
        save_strategy="no",            # no intermediate checkpoints → saves ~3GB disk
        logging_steps=20,
        seed=SEED,
        dataloader_num_workers=0,      # Windows: avoid multiprocessing issues
        report_to="none",              # no wandb / tensorboard
        fp16=False,                    # CPU training: no FP16
    )

    # 6. Class weights + weighted trainer
    class_weights = compute_class_weights(train_data)
    trainer = WeightedTrainer.build(
        class_weights=class_weights,
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        compute_metrics=_compute_metrics,
    )

    # 7. Train
    print(f"\nStarting training ({epochs} epochs max, early stopping patience=2)…")
    print("Note: CPU training takes ~1–3 hours. Leave this running overnight.\n")
    train_result = trainer.train()

    # 8. Evaluate final model on val set
    print("\nFinal evaluation on validation set …")
    metrics = trainer.evaluate()
    print(f"\n  Validation accuracy   : {metrics.get('eval_accuracy', 'N/A')}")
    print(f"  Validation macro-F1   : {metrics.get('eval_f1_macro', 'N/A')}")
    print(f"  Validation weighted-F1: {metrics.get('eval_f1_weighted', 'N/A')}")

    # 9. Save model + tokenizer
    print(f"\nSaving model to {OUTPUT_DIR} …")
    trainer.save_model(str(OUTPUT_DIR))
    tokenizer.save_pretrained(str(OUTPUT_DIR))

    # 10. Save label map (consumed by sentiment_analyzer.py)
    label_map = {
        "id2label": ID2LABEL,
        "label2id": LABEL2ID,
        "base_model": BASE_MODEL,
        "confidence_threshold_used": confidence_threshold,
        "train_samples": len(train_data),
        "val_samples":   len(val_data),
        "epochs_trained": int(train_result.global_step /
                              max(1, len(train_data) // BATCH_TRAIN)),
        "val_accuracy":  metrics.get("eval_accuracy"),
        "val_f1_macro":  metrics.get("eval_f1_macro"),
    }
    with (OUTPUT_DIR / "label_map.json").open("w") as fh:
        json.dump(label_map, fh, indent=2)

    # 11. Save val set for use by evaluate_sentiment.py
    val_out = _ROOT / "data" / "val_set.jsonl"
    with val_out.open("w", encoding="utf-8") as fh:
        for s in val_data:
            fh.write(json.dumps(s, ensure_ascii=False) + "\n")
    print(f"Validation set written to: {val_out}  ({len(val_data)} rows)")

    print(f"\n{'='*60}")
    print("Fine-tuning complete.")
    print(f"  Model saved to : {OUTPUT_DIR}")
    print(f"  Val accuracy   : {metrics.get('eval_accuracy', 'N/A')}")
    print(f"  Val macro-F1   : {metrics.get('eval_f1_macro', 'N/A')}")
    print(f"{'='*60}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fine-tune distilbert-base-multilingual-cased on LLM labels."
    )
    parser.add_argument(
        "--labels", type=Path, default=DEFAULT_LABELS,
        help=f"Path to llm_labels.jsonl (default: {DEFAULT_LABELS})."
    )
    parser.add_argument(
        "--confidence", type=float, default=0.85,
        help="Minimum LLM confidence to include a sample (default: 0.85)."
    )
    parser.add_argument(
        "--epochs", type=int, default=TRAIN_EPOCHS,
        help=f"Maximum training epochs (default: {TRAIN_EPOCHS})."
    )
    parser.add_argument(
        "--val", type=Path, default=None,
        help="Path to pre-built val_set.jsonl. If omitted, an 80/20 split is made from --labels."
    )
    args = parser.parse_args()
    finetune(args.labels, args.confidence, args.epochs, args.val)


if __name__ == "__main__":
    main()
