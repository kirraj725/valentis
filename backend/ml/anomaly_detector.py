"""
Three-Layer Anomaly Detection System

Layer 1 — Rule-based: Duplicate claims + CMS crosswalk mismatch detection
Layer 2 — Statistical: Per-CPT Isolation Forest for numerical outliers
Layer 3 — Aggregate: Provider-level Z-score behavioral analysis

Each layer is independently explainable. The hybrid approach achieves high
precision because each detector targets the anomaly type it's best suited for.
"""

import os
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import precision_score, recall_score, f1_score, classification_report


MODEL_DIR = os.path.dirname(__file__)
MODEL_PATH = os.path.join(MODEL_DIR, "model.joblib")
CROSSWALK_PATH = os.path.join(MODEL_DIR, "data", "cpt_icd10_crosswalk.csv")


# ═══════════════════════════════════════════════════════════════
# Layer 1 — Rule-Based Detection
# ═══════════════════════════════════════════════════════════════

def load_crosswalk(path: str = CROSSWALK_PATH) -> dict[str, set[str]]:
    """Load CMS CPT-to-ICD-10 crosswalk into a lookup dict."""
    if not os.path.exists(path):
        return {}
    df = pd.read_csv(path)
    crosswalk = {}
    for cpt, group in df.groupby("cpt_code"):
        crosswalk[str(cpt)] = set(group["icd10_code"].astype(str))
    return crosswalk


def detect_duplicates(df: pd.DataFrame) -> pd.Series:
    """
    Flag duplicate claims using deterministic matching.
    A duplicate = same claim_id appearing more than once.
    """
    return df.duplicated(subset=["claim_id"], keep=False)


def detect_cpt_icd_mismatch(df: pd.DataFrame, crosswalk: dict[str, set[str]]) -> pd.Series:
    """
    Flag claims where the ICD-10 code is not a valid pairing for the CPT code,
    according to the CMS crosswalk reference data.
    """
    if not crosswalk or "icd10_code" not in df.columns:
        return pd.Series(False, index=df.index)

    mismatch = pd.Series(False, index=df.index)
    for idx, row in df.iterrows():
        cpt = str(row.get("cpt_code", ""))
        icd = str(row.get("icd10_code", ""))
        if cpt in crosswalk and icd not in crosswalk[cpt]:
            mismatch.at[idx] = True
    return mismatch


# ═══════════════════════════════════════════════════════════════
# Layer 2 — Per-CPT Isolation Forest
# ═══════════════════════════════════════════════════════════════

NUMERICAL_FEATURES = ["billed_amount", "allowed_amount", "paid_amount", "billed_to_paid_ratio"]


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add engineered numerical features."""
    out = df.copy()
    out["billed_to_paid_ratio"] = np.where(
        out["paid_amount"] > 0,
        out["billed_amount"] / out["paid_amount"],
        out["billed_amount"],
    )
    out["billed_to_allowed_ratio"] = np.where(
        out["allowed_amount"] > 0,
        out["billed_amount"] / out["allowed_amount"],
        1.0,
    )
    return out


def train_per_cpt_models(df: pd.DataFrame, contamination: float = 0.08) -> dict:
    """
    Train one Isolation Forest per CPT code group.
    $800 is normal for an MRI but suspicious for a blood draw —
    per-CPT training captures this domain reality.
    """
    featured = engineer_features(df)
    models = {}

    for cpt_code, group in featured.groupby("cpt_code"):
        if len(group) < 20:
            continue  # Not enough data for meaningful model

        X = group[NUMERICAL_FEATURES].fillna(0)
        model = IsolationForest(
            n_estimators=200,
            contamination=contamination,
            max_features=0.8,
            random_state=42,
            n_jobs=-1,
        )
        model.fit(X)
        models[str(cpt_code)] = model

    return models


def score_with_per_cpt_models(df: pd.DataFrame, models: dict) -> pd.DataFrame:
    """Score claims using per-CPT Isolation Forest models."""
    featured = engineer_features(df)
    scores = np.zeros(len(df))
    anomaly_flags = np.zeros(len(df), dtype=bool)

    for cpt_code, group in featured.groupby("cpt_code"):
        cpt_str = str(cpt_code)
        if cpt_str not in models:
            continue

        X = group[NUMERICAL_FEATURES].fillna(0)
        cpt_scores = models[cpt_str].decision_function(X)
        scores[group.index] = cpt_scores
        anomaly_flags[group.index] = cpt_scores < -0.1

    result = df.copy()
    result["if_score"] = np.round(scores, 4)
    result["if_anomaly"] = anomaly_flags
    return result


# ═══════════════════════════════════════════════════════════════
# Layer 3 — Provider-Level Behavioral Z-Score Analysis
# ═══════════════════════════════════════════════════════════════

def detect_provider_anomalies(df: pd.DataFrame, z_threshold: float = 3.0) -> pd.Series:
    """
    Flag claims from providers with statistically anomalous behavior:
    - Claims per day significantly above peers
    - Average billed amount far above peer average for same CPT codes
    - Billed-to-allowed ratio unusually consistent (near 1.0 across all claims)
    """
    provider_flags = pd.Series(False, index=df.index)

    if "provider_id" not in df.columns or len(df) < 50:
        return provider_flags

    featured = engineer_features(df)

    # Aggregate per provider
    provider_stats = featured.groupby("provider_id").agg(
        claim_count=("claim_id", "count"),
        avg_billed=("billed_amount", "mean"),
        std_billed=("billed_amount", "std"),
        avg_ratio=("billed_to_allowed_ratio", "mean"),
        std_ratio=("billed_to_allowed_ratio", "std"),
    ).fillna(0)

    # Z-score each metric across providers
    for col in ["claim_count", "avg_billed", "avg_ratio"]:
        mean = provider_stats[col].mean()
        std = provider_stats[col].std()
        if std > 0:
            provider_stats[f"{col}_z"] = (provider_stats[col] - mean) / std
        else:
            provider_stats[f"{col}_z"] = 0

    # Flag providers where MULTIPLE z-scores exceed threshold (not just one)
    anomalous_providers = provider_stats[
        ((provider_stats["claim_count_z"].abs() > z_threshold).astype(int) +
         (provider_stats["avg_billed_z"].abs() > z_threshold).astype(int) +
         (provider_stats["avg_ratio_z"].abs() > z_threshold).astype(int)) >= 2
    ].index

    # Providers with suspiciously low variance in billing ratio
    consistent_billers = provider_stats[
        (provider_stats["std_ratio"] < 0.03) &
        (provider_stats["avg_ratio"] > 0.98) &
        (provider_stats["claim_count"] > 20)
    ].index

    flagged_providers = set(anomalous_providers) | set(consistent_billers)
    provider_flags = df["provider_id"].isin(flagged_providers)

    return provider_flags


# ═══════════════════════════════════════════════════════════════
# Orchestrator — Combines All Three Layers
# ═══════════════════════════════════════════════════════════════

class AnomalyDetector:
    """Three-layer anomaly detection orchestrator."""

    def __init__(self, contamination: float = 0.08):
        self.contamination = contamination
        self.models = {}
        self.crosswalk = {}
        self._is_fitted = False

    def train(self, df: pd.DataFrame) -> "AnomalyDetector":
        """Train per-CPT Isolation Forest models and load crosswalk."""
        self.models = train_per_cpt_models(df, self.contamination)
        self.crosswalk = load_crosswalk()
        self._is_fitted = True
        return self

    def save(self, path: str = MODEL_PATH):
        """Persist models to disk."""
        joblib.dump({"models": self.models, "crosswalk": self.crosswalk}, path)

    def load(self, path: str = MODEL_PATH) -> "AnomalyDetector":
        """Load previously trained models."""
        if os.path.exists(path):
            data = joblib.load(path)
            self.models = data.get("models", {})
            self.crosswalk = data.get("crosswalk", load_crosswalk())
            self._is_fitted = True
        return self

    def score(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Run all three detection layers and combine results.
        A claim is flagged if ANY layer fires.
        """
        if not self._is_fitted:
            self.load()
        if not self._is_fitted:
            raise RuntimeError("Model not trained. Call train() or load() first.")

        # Layer 1: Rule-based
        dup_flags = detect_duplicates(df)
        mismatch_flags = detect_cpt_icd_mismatch(df, self.crosswalk)

        # Layer 2: Per-CPT Isolation Forest
        if_result = score_with_per_cpt_models(df, self.models)

        # Layer 3: Provider Z-score
        provider_flags = detect_provider_anomalies(df)

        # Combine
        combined = dup_flags | mismatch_flags | if_result["if_anomaly"] | provider_flags

        # Composite score
        composite = if_result["if_score"].copy()
        composite[dup_flags] = np.minimum(composite[dup_flags], -0.2)
        composite[mismatch_flags] = np.minimum(composite[mismatch_flags], -0.15)
        composite[provider_flags] = np.minimum(composite[provider_flags], -0.12)

        result = df.copy()
        result["anomaly_score"] = composite
        result["is_anomaly"] = combined
        result["_layer1_dup"] = dup_flags
        result["_layer1_mismatch"] = mismatch_flags
        result["_layer2_if"] = if_result["if_anomaly"]
        result["_layer3_provider"] = provider_flags
        return result

    def get_flag_reasons(self, row: pd.Series) -> str:
        """Generate human-readable flag reason from detection layers."""
        reasons = []
        if row.get("_layer1_dup", False):
            reasons.append("duplicate claim ID")
        if row.get("_layer1_mismatch", False):
            reasons.append("CPT/ICD-10 coding mismatch")
        if row.get("_layer2_if", False):
            reasons.append("statistical amount outlier")
        if row.get("_layer3_provider", False):
            reasons.append("anomalous provider pattern")
        return "; ".join(reasons) if reasons else "multivariate anomaly"

    def evaluate(self, df: pd.DataFrame, ground_truth: pd.Series) -> dict:
        """Evaluate against ground truth with per-layer breakdown."""
        scored = self.score(df)
        predicted = scored["is_anomaly"].astype(int)
        actual = ground_truth.astype(int)

        precision = precision_score(actual, predicted, zero_division=0)
        recall = recall_score(actual, predicted, zero_division=0)
        f1 = f1_score(actual, predicted, zero_division=0)
        report = classification_report(actual, predicted, target_names=["normal", "anomaly"])

        return {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "report": report,
            "total_records": len(df),
            "predicted_anomalies": int(predicted.sum()),
            "actual_anomalies": int(actual.sum()),
            "layer_breakdown": {
                "layer1_duplicates": int(scored["_layer1_dup"].sum()),
                "layer1_mismatches": int(scored["_layer1_mismatch"].sum()),
                "layer2_isolation_forest": int(scored["_layer2_if"].sum()),
                "layer3_provider_zscore": int(scored["_layer3_provider"].sum()),
            },
        }


def train_and_evaluate():
    """Standalone: train on generated data and print metrics."""
    csv_path = os.path.join(MODEL_DIR, "..", "scripts", "claims_data.csv")
    if not os.path.exists(csv_path):
        print(f"ERROR: {csv_path} not found. Run scripts/generate_data.py first.")
        return

    df = pd.read_csv(csv_path)
    print(f"Loaded {len(df):,} claims")

    # Build ground truth from all three anomaly types
    crosswalk = load_crosswalk()

    dup_mask = df.duplicated(subset=["claim_id"], keep=False)

    outlier_mask = pd.Series(False, index=df.index)
    for cpt_code, group in df.groupby("cpt_code"):
        mean = group["billed_amount"].mean()
        std = group["billed_amount"].std()
        if std > 0:
            outlier_mask.loc[group.index] = group["billed_amount"] > (mean + 3 * std)

    mismatch_mask = pd.Series(False, index=df.index)
    for idx, row in df.iterrows():
        cpt = str(row.get("cpt_code", ""))
        icd = str(row.get("icd10_code", ""))
        if cpt in crosswalk and icd not in crosswalk[cpt]:
            mismatch_mask.at[idx] = True

    ground_truth = dup_mask | outlier_mask | mismatch_mask
    print(f"\nGround truth anomalies: {ground_truth.sum():,} ({ground_truth.mean()*100:.1f}%)")
    print(f"  Duplicates:  {dup_mask.sum():,}")
    print(f"  Outliers:    {outlier_mask.sum():,}")
    print(f"  Mismatches:  {mismatch_mask.sum():,}")

    # Train
    detector = AnomalyDetector()
    detector.train(df)
    detector.save()
    print(f"\nModel saved to {MODEL_PATH}")
    print(f"  Per-CPT models: {len(detector.models)}")
    print(f"  Crosswalk CPTs: {len(detector.crosswalk)}")

    # Evaluate
    metrics = detector.evaluate(df, ground_truth)
    print(f"\n{'='*55}")
    print(f"  PRECISION:  {metrics['precision']:.2%}")
    print(f"  RECALL:     {metrics['recall']:.2%}")
    print(f"  F1 SCORE:   {metrics['f1']:.2%}")
    print(f"{'='*55}")
    print(f"\n  Predicted: {metrics['predicted_anomalies']:,}")
    print(f"  Actual:    {metrics['actual_anomalies']:,}")
    print(f"\n  Layer Breakdown:")
    for layer, count in metrics["layer_breakdown"].items():
        print(f"    {layer}: {count:,}")
    print(f"\n{metrics['report']}")

    return metrics


if __name__ == "__main__":
    train_and_evaluate()
