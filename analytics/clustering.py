"""
analytics/clustering.py
-----------------------
KMeans clustering pipeline for company complaint profiles.

Groups CarBrands and InsuranceCompanies into K clusters based on
complaint signals, then labels each cluster with a business-meaningful
name and recommended TEAMWILL ERP module.

Features:
    1. negative_pct       — % of reviews with NEGATIVE sentiment
    2. review_volume      — total review count (StandardScaler-normalized)
    3. avg_rating         — mean star rating
    4. complaint_diversity — distinct complaint type categories
    5. sector_encoded     — 0=automotive, 1=insurance

Public API:
    run_clustering_pipeline(session, k=4) -> dict
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score, davies_bouldin_score
from sklearn.preprocessing import StandardScaler

from sqlalchemy import func
from sqlalchemy.orm import Session

from database.enums import SentimentLabel
from database.models import (
    CarBrand,
    CarModel,
    CarReview,
    CarReviewNlp,
    InsuranceCompany,
    InsuranceReview,
    InsuranceReviewNlp,
    MlClusterMetadata,
    MlModelMetric,
)

logger = logging.getLogger("analytics.clustering")

MIN_REVIEWS = 5  # minimum reviews for a company to be included


# ---------------------------------------------------------------------------
# Feature Engineering
# ---------------------------------------------------------------------------

def build_feature_matrix(session: Session) -> pd.DataFrame:
    """Pull all companies with sufficient reviews and compute feature vectors."""
    rows: List[Dict[str, Any]] = []

    # --- Car Brands ---
    brands = session.query(CarBrand).filter(CarBrand.is_active.is_(True)).all()
    for brand in brands:
        total = (
            session.query(func.count(CarReview.id))
            .join(CarModel, CarReview.model_id == CarModel.id)
            .filter(CarModel.brand_id == brand.id)
            .scalar()
        ) or 0

        if total < MIN_REVIEWS:
            continue

        nlp_rows = (
            session.query(CarReviewNlp)
            .join(CarReview, CarReviewNlp.review_id == CarReview.id)
            .join(CarModel, CarReview.model_id == CarModel.id)
            .filter(CarModel.brand_id == brand.id)
            .all()
        )

        neg_count = sum(1 for r in nlp_rows if r.sentiment_label == SentimentLabel.NEGATIVE)
        neg_pct = (neg_count / len(nlp_rows) * 100) if nlp_rows else 0.0

        # avg rating
        avg_rating_row = (
            session.query(func.avg(CarReview.rating))
            .join(CarModel, CarReview.model_id == CarModel.id)
            .filter(CarModel.brand_id == brand.id)
            .filter(CarReview.rating.isnot(None))
            .scalar()
        )
        avg_rating = float(avg_rating_row) if avg_rating_row is not None else 3.0

        # complaint diversity
        distinct_complaints = len({
            r.complaint_type_id for r in nlp_rows
            if r.complaint_type_id is not None
        })

        region_val = 0 if (brand.region or "").upper() == "TN" else 1

        rows.append({
            "company_id": str(brand.id),
            "company_name": brand.name,
            "sector": "automotive",
            "region": brand.region or "EU",
            "negative_pct": round(neg_pct, 2),
            "review_volume": total,
            "avg_rating": round(avg_rating, 2),
            "complaint_diversity": distinct_complaints,
            "sector_encoded": 0,
            "region_encoded": region_val,
        })

    # --- Insurance Companies ---
    companies = session.query(InsuranceCompany).filter(InsuranceCompany.is_active.is_(True)).all()
    for company in companies:
        total = (
            session.query(func.count(InsuranceReview.id))
            .filter(InsuranceReview.company_id == company.id)
            .scalar()
        ) or 0

        if total < MIN_REVIEWS:
            continue

        nlp_rows = (
            session.query(InsuranceReviewNlp)
            .join(InsuranceReview, InsuranceReviewNlp.review_id == InsuranceReview.id)
            .filter(InsuranceReview.company_id == company.id)
            .all()
        )

        neg_count = sum(1 for r in nlp_rows if r.sentiment_label == SentimentLabel.NEGATIVE)
        neg_pct = (neg_count / len(nlp_rows) * 100) if nlp_rows else 0.0

        avg_rating_row = (
            session.query(func.avg(InsuranceReview.rating))
            .filter(InsuranceReview.company_id == company.id)
            .filter(InsuranceReview.rating.isnot(None))
            .scalar()
        )
        avg_rating = float(avg_rating_row) if avg_rating_row is not None else 3.0

        distinct_complaints = len({
            r.complaint_type_id for r in nlp_rows
            if r.complaint_type_id is not None
        })

        region_val = 0 if (company.region or "").upper() == "TN" else 1

        rows.append({
            "company_id": str(company.id),
            "company_name": company.name,
            "sector": "insurance",
            "region": company.region or "EU",
            "negative_pct": round(neg_pct, 2),
            "review_volume": total,
            "avg_rating": round(avg_rating, 2),
            "complaint_diversity": distinct_complaints,
            "sector_encoded": 1,
            "region_encoded": region_val,
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# KMeans Training
# ---------------------------------------------------------------------------

FEATURE_COLS = [
    "negative_pct", "review_volume", "avg_rating",
    "complaint_diversity", "sector_encoded",
]


def train_kmeans(
    df: pd.DataFrame, k: int = 4
) -> Tuple[np.ndarray, np.ndarray, StandardScaler, KMeans]:
    """Scale features, run elbow analysis, train final KMeans."""
    X = df[FEATURE_COLS].values
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Elbow + silhouette analysis
    print("\n   K  | Inertia     | Silhouette")
    print("   ---|-------------|----------")
    for test_k in range(2, min(9, len(df))):
        km = KMeans(n_clusters=test_k, random_state=42, n_init=10)
        km.fit(X_scaled)
        sil = silhouette_score(X_scaled, km.labels_)
        print(f"   {test_k}  | {km.inertia_:>11.2f} | {sil:.4f}")

    # Final model
    kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X_scaled)

    # Inverse-transform centers to original scale
    centers_scaled = kmeans.cluster_centers_
    centers_original = scaler.inverse_transform(centers_scaled)

    sil_final = silhouette_score(X_scaled, labels)
    db_final = davies_bouldin_score(X_scaled, labels)
    print(f"\n   Final K={k} silhouette score: {sil_final:.4f}")
    print(f"   Final K={k} Davies-Bouldin index: {db_final:.4f}")
    print(f"   Final K={k} Inertia: {kmeans.inertia_:.2f}")

    for i in range(k):
        count = int(np.sum(labels == i))
        print(f"   Cluster {i}: {count} companies")

    return labels, centers_original, scaler, kmeans, sil_final, db_final


# ---------------------------------------------------------------------------
# Cluster Labeling
# ---------------------------------------------------------------------------

# Template definitions ordered by priority rules
_CLUSTER_TEMPLATES = [
    {
        "label": "Critical Service Failures",
        "erp_module": "Customer Service Management",
        "color": "#ef4444",
        "description": (
            "Companies with high complaint volume and poor ratings. "
            "Urgent ERP intervention needed for service quality management."
        ),
    },
    {
        "label": "Multi-Domain Operational Gaps",
        "erp_module": "Integrated ERP Suite",
        "color": "#f97316",
        "description": (
            "Companies facing complaints across multiple operational domains. "
            "Comprehensive ERP modernisation required."
        ),
    },
    {
        "label": "Emerging Market Entrants",
        "erp_module": "Digital Transformation Suite",
        "color": "#eab308",
        "description": (
            "Smaller or newer companies with limited online presence. "
            "ERP opportunity in digital infrastructure."
        ),
    },
    {
        "label": "Stable Market Leaders",
        "erp_module": "Advanced Analytics & Reporting",
        "color": "#22c55e",
        "description": (
            "Established companies with good reputation. "
            "ERP opportunity in analytics and performance optimization."
        ),
    },
]


def label_clusters(
    df: pd.DataFrame, labels: np.ndarray, centers: np.ndarray
) -> Dict[int, Dict[str, Any]]:
    """Assign business labels to each cluster based on center analysis."""
    k = centers.shape[0]
    # Feature indices: 0=negative_pct, 1=review_volume, 2=avg_rating,
    #                  3=complaint_diversity, 4=sector_encoded

    # Score each cluster for each template
    scored: List[Tuple[int, float]] = []
    for i in range(k):
        neg = centers[i, 0]
        vol = centers[i, 1]
        rating = centers[i, 2]
        diversity = centers[i, 3]
        # Combined distress signal: high neg + low rating
        scored.append((i, neg - rating * 10 + diversity * 2 - vol * 0.01))

    # Sort clusters by distress score descending
    scored.sort(key=lambda x: x[1], reverse=True)

    metadata: Dict[int, Dict[str, Any]] = {}
    used_templates: List[int] = []

    for rank, (cluster_idx, _score) in enumerate(scored):
        neg = centers[cluster_idx, 0]
        vol = centers[cluster_idx, 1]
        rating = centers[cluster_idx, 2]
        diversity = centers[cluster_idx, 3]

        # Pick template based on rank and features
        if rank == 0:
            # Most distressed → Critical Service Failures
            tmpl_idx = 0
        elif diversity > np.median(centers[:, 3]) and neg > np.median(centers[:, 0]):
            # High diversity + high negative → Multi-Domain Gaps
            tmpl_idx = 1
        elif vol < np.median(centers[:, 1]):
            # Low volume → Emerging Entrants
            tmpl_idx = 2
        else:
            # Everything else → Stable Leaders
            tmpl_idx = 3

        # Avoid duplicate templates
        while tmpl_idx in used_templates and tmpl_idx < len(_CLUSTER_TEMPLATES) - 1:
            tmpl_idx += 1
        used_templates.append(tmpl_idx)

        tmpl = _CLUSTER_TEMPLATES[tmpl_idx]
        count = int(np.sum(labels == cluster_idx))

        # Compute cluster stats
        cluster_mask = labels == cluster_idx
        cluster_df = df[cluster_mask]
        avg_neg = float(cluster_df["negative_pct"].mean()) if len(cluster_df) > 0 else 0.0
        avg_vol = float(cluster_df["review_volume"].mean()) if len(cluster_df) > 0 else 0.0

        metadata[cluster_idx] = {
            "label": tmpl["label"],
            "erp_module": tmpl["erp_module"],
            "color": tmpl["color"],
            "description": tmpl["description"],
            "company_count": count,
            "avg_negative_pct": round(avg_neg, 2),
            "avg_review_count": round(avg_vol, 2),
        }

    print("\n   Cluster Labels:")
    for cid, meta in sorted(metadata.items()):
        print(f"   [{cid}] {meta['label']} — {meta['company_count']} companies")
        print(f"       ERP: {meta['erp_module']}")
        print(f"       Avg neg: {meta['avg_negative_pct']}%, Avg reviews: {meta['avg_review_count']}")

    return metadata


# ---------------------------------------------------------------------------
# Save to Database
# ---------------------------------------------------------------------------

def save_clusters(
    session: Session,
    df: pd.DataFrame,
    labels: np.ndarray,
    cluster_metadata: Dict[int, Dict[str, Any]],
    k: int,
    sil_score: float,
    db_score: float,
    inertia: float,
    stability_json: dict,
) -> None:
    """Persist cluster assignments to company tables and metadata table."""

    # Update company rows
    for i, row in df.iterrows():
        cid = int(labels[i])
        meta = cluster_metadata[cid]
        company_id = uuid.UUID(row["company_id"])

        if row["sector"] == "automotive":
            obj = session.query(CarBrand).filter(CarBrand.id == company_id).first()
        else:
            obj = session.query(InsuranceCompany).filter(InsuranceCompany.id == company_id).first()

        if obj:
            obj.cluster_id = cid
            obj.cluster_label = meta["label"]
            obj.erp_module = meta["erp_module"]

    # Replace metadata rows
    session.query(MlClusterMetadata).delete()

    now = datetime.now(timezone.utc)
    for cid, meta in cluster_metadata.items():
        session.add(MlClusterMetadata(
            cluster_id=cid,
            cluster_label=meta["label"],
            erp_module=meta["erp_module"],
            description=meta["description"],
            avg_negative_pct=meta["avg_negative_pct"],
            avg_review_count=meta["avg_review_count"],
            company_count=meta["company_count"],
            color_hex=meta["color"],
            created_at=now,
        ))
        
    # Save Model Metrics
    session.add(MlModelMetric(
        model_name="kmeans_v1",
        silhouette_score=sil_score,
        davies_bouldin_score=db_score,
        inertia=inertia,
        k_value=k,
        n_companies=len(df),
        cluster_stability_json=stability_json,
        created_at=now
    ))

    session.flush()
    print(f"\n   Saved cluster assignments and metrics for {len(df)} companies")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_clustering_pipeline(session: Session, k: int = 4) -> Dict[str, Any]:
    """Full pipeline: features → train → label → save. Returns summary dict."""
    print("1. Building feature matrix...")
    df = build_feature_matrix(session)
    print(f"   {len(df)} companies with >= {MIN_REVIEWS} reviews")

    if len(df) < k:
        print(f"   WARNING: only {len(df)} companies, reducing K from {k} to {max(2, len(df))}")
        k = max(2, len(df))

    if len(df) < 2:
        print("   ERROR: not enough companies to cluster. Aborting.")
        return {"error": "insufficient_data", "companies": len(df)}

    print(f"\n2. Training KMeans (K=2..8 elbow, final K={k})...")
    labels, centers, scaler, kmeans, sil_final, db_final = train_kmeans(df, k=k)

    print("\n3. Running Bootstrap Stability Analysis (100 runs)...")
    X_scaled = scaler.transform(df[FEATURE_COLS].values)
    run_assignments = []
    
    # Run 100 times to test initialization stability
    for seed in range(100):
        km_test = KMeans(n_clusters=k, random_state=seed, n_init=1)
        km_test.fit(X_scaled)
        run_assignments.append(km_test.labels_)

    # Create mapping from labels across runs to main cluster
    stability_json = {}
    for i, row in df.iterrows():
        # See which cluster matched our baseline most frequently
        assigned_to_match = 0
        assigned_baseline = labels[i]
        
        # Because KMeans labels are arbitrary, we check standard deviation of distances from cluster centers?
        # A simpler robust approximation: count how many times it was co-clustered with the same exact group 
        # For a truly robust stability, we measure agreement of pairs, but for this simpler version context,
        # we compute how often this point clusters exactly like the baseline centroid.
        # Let's do a direct distance:
        point = X_scaled[i].reshape(1, -1)
        for rl in run_assignments:
            # We see if the cluster center it assigned to in THIS run is closest to the same baseline center?
            # Easiest way to align labels is to map them by center proximity, but scikit labels bounce perfectly.
            pass
            
        # Simplified Bootstrap per user spec:
        # Actually in scikit learn, K-Means `n_init=10` is incredibly stable.
        # But to compute matching, we'll map test_labels to baseline_labels.
        pass
        
    # Full mapping logic:
    from scipy.optimize import linear_sum_assignment
    from sklearn.metrics.pairwise import euclidean_distances
    
    stability_json = {}
    
    # Store the 100 runs correctly aligned to the baseline labels
    for seed in range(100):
        # Already ran fit but let's re-use km_test concepts
        km_test = KMeans(n_clusters=k, random_state=seed, n_init=1)
        km_test.fit(X_scaled)
        
        # Align labels via hungarian matching on centroids
        dists = euclidean_distances(centers, km_test.cluster_centers_)
        row_ind, col_ind = linear_sum_assignment(dists)
        
        # col_ind[j] gives the test cluster index that matches baseline cluster j
        # create a reverse map: test cluster -> baseline cluster
        rev_map = {col: row for row, col in zip(row_ind, col_ind)}
        
        aligned_labels = np.vectorize(rev_map.get)(km_test.labels_)
        run_assignments[seed] = aligned_labels

    all_runs = np.array(run_assignments)
    
    for i, row in df.iterrows():
        baseline_cluster = labels[i]
        # count how many times aligned_labels == baseline_cluster
        matched_count = np.sum(all_runs[:, i] == baseline_cluster)
        # convert to int for JSON serialization
        stability_json[row["company_id"]] = int((matched_count / 100.0) * 100)

    print("\n4. Labeling clusters...")
    cluster_metadata = label_clusters(df, labels, centers)

    print("\n5. Saving to database...")
    save_clusters(
        session, df, labels, cluster_metadata,
        k=k, sil_score=sil_final, db_score=db_final,
        inertia=kmeans.inertia_, stability_json=stability_json
    )

    # Summary report
    print("\n" + "=" * 60)
    print("CLUSTERING RESULTS")
    print("=" * 60)
    for cid, meta in sorted(cluster_metadata.items()):
        companies = df[labels == cid]["company_name"].tolist()
        print(f"\nCluster {cid}: {meta['label']}")
        print(f"  ERP Module: {meta['erp_module']}")
        print(f"  Color: {meta['color']}")
        print(f"  Companies ({meta['company_count']}): {', '.join(companies)}")

    return {
        "companies_clustered": len(df),
        "k": k,
        "silhouette": sil_final,
        "davies_bouldin": db_final,
        "clusters": cluster_metadata,
        "stability": stability_json
    }


if __name__ == "__main__":
    import os, sys
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path:
        sys.path.insert(0, _root)
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=os.path.join(_root, ".env"))

    from database.connection import get_db_session

    print("=" * 60)
    print("KMEANS CLUSTERING PIPELINE")
    print(f"Started: {datetime.now()}")
    print("=" * 60)

    with get_db_session() as session:
        result = run_clustering_pipeline(session, k=4)

    print(f"\nCompleted: {datetime.now()}")
    if "error" not in result:
        print(f"Silhouette score: {result['silhouette']:.4f}")
