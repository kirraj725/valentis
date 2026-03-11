"""
Prometheus-compatible metrics endpoint.

Exposes: claims_ingested_total, anomalies_flagged_total, flagged_percentage,
avg_anomaly_score, and summarization_latency_seconds.
"""

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.database import get_db
from app.db.models import Claim, AnomalyFlag

router = APIRouter()


@router.get("/metrics", response_class=PlainTextResponse)
def prometheus_metrics(db: Session = Depends(get_db)):
    """Return Prometheus-format metrics."""
    total_claims = db.query(func.count(Claim.id)).scalar() or 0
    total_flagged = db.query(func.count(AnomalyFlag.id)).scalar() or 0
    flagged_pct = round(total_flagged / total_claims * 100, 2) if total_claims else 0
    avg_score = db.query(func.avg(AnomalyFlag.anomaly_score)).scalar()
    avg_score_val = round(float(avg_score), 4) if avg_score else 0
    reviewed = db.query(func.count(AnomalyFlag.id)).filter(AnomalyFlag.reviewed == True).scalar() or 0

    # Import summarization latency
    try:
        from app.routers.summarize import get_summarization_latency
        latency = get_summarization_latency() or 0
    except ImportError:
        latency = 0

    lines = [
        "# HELP claims_ingested_total Total number of claims ingested",
        "# TYPE claims_ingested_total gauge",
        f"claims_ingested_total {total_claims}",
        "",
        "# HELP anomalies_flagged_total Total anomaly flags",
        "# TYPE anomalies_flagged_total gauge",
        f"anomalies_flagged_total {total_flagged}",
        "",
        "# HELP flagged_percentage Percentage of claims flagged as anomalous",
        "# TYPE flagged_percentage gauge",
        f"flagged_percentage {flagged_pct}",
        "",
        "# HELP avg_anomaly_score Average anomaly score across all flags",
        "# TYPE avg_anomaly_score gauge",
        f"avg_anomaly_score {avg_score_val}",
        "",
        "# HELP anomalies_reviewed_total Anomalies marked as reviewed",
        "# TYPE anomalies_reviewed_total gauge",
        f"anomalies_reviewed_total {reviewed}",
        "",
        "# HELP summarization_latency_seconds Last LLM summarization latency",
        "# TYPE summarization_latency_seconds gauge",
        f"summarization_latency_seconds {latency}",
        "",
    ]

    return "\n".join(lines)
