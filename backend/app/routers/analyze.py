"""
Analyze endpoints — run ML anomaly detection and manage flagged records.

POST /api/analyze    — run Isolation Forest on unscored claims
GET  /api/anomalies  — paginated flagged records
PATCH /api/anomalies/{id} — mark flag as reviewed
GET  /api/anomalies/stats — overview statistics
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.database import get_db, engine, Base
from app.db.models import Claim, AnomalyFlag

import pandas as pd

router = APIRouter()


@router.post("/analyze")
def run_analysis(db: Session = Depends(get_db)):
    """Run three-layer anomaly detection on all unscored claims."""
    from ml.anomaly_detector import AnomalyDetector

    # Ensure tables exist
    Base.metadata.create_all(bind=engine)

    # Get all claims
    claims = db.query(Claim).all()
    if not claims:
        raise HTTPException(status_code=404, detail="No claims in database. Ingest data first.")

    # Already-flagged claim_ids
    flagged_ids = {row[0] for row in db.query(AnomalyFlag.claim_id).all()}

    # Build DataFrame — include all fields needed by three layers
    records = [{
        "claim_id": c.claim_id,
        "patient_id": c.patient_id,
        "provider_id": c.provider_id,
        "cpt_code": c.cpt_code,
        "icd10_code": c.icd10_code,
        "billed_amount": c.billed_amount,
        "allowed_amount": c.allowed_amount,
        "paid_amount": c.paid_amount,
    } for c in claims if c.claim_id not in flagged_ids]

    if not records:
        return {"status": "complete", "message": "All claims already scored", "new_flags": 0}

    df = pd.DataFrame(records)

    # Load or train model
    detector = AnomalyDetector()
    try:
        detector.load()
    except RuntimeError:
        detector.train(df)
        detector.save()

    # Score with all three layers
    scored = detector.score(df)
    anomalies = scored[scored["is_anomaly"]]

    # Build flags with per-layer reason explanations
    new_flags = []
    for _, row in anomalies.iterrows():
        reason = detector.get_flag_reasons(row)
        new_flags.append(AnomalyFlag(
            claim_id=row["claim_id"],
            anomaly_score=round(float(row["anomaly_score"]), 4),
            flag_reason=reason,
            reviewed=False,
        ))

    if new_flags:
        db.bulk_save_objects(new_flags)
        db.commit()

    return {
        "status": "complete",
        "total_scored": len(df),
        "new_flags": len(new_flags),
        "flagged_percentage": round(len(new_flags) / len(df) * 100, 1),
        "layer_breakdown": {
            "duplicates": int(scored["_layer1_dup"].sum()),
            "cpt_icd_mismatches": int(scored["_layer1_mismatch"].sum()),
            "statistical_outliers": int(scored["_layer2_if"].sum()),
            "provider_anomalies": int(scored["_layer3_provider"].sum()),
        },
    }


@router.get("/anomalies")
def get_anomalies(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    reviewed: bool | None = None,
    sort_by: str = Query("anomaly_score", pattern="^(anomaly_score|flagged_at|claim_id)$"),
    db: Session = Depends(get_db),
):
    """Return paginated anomaly flags with optional filtering."""
    query = db.query(AnomalyFlag)

    if reviewed is not None:
        query = query.filter(AnomalyFlag.reviewed == reviewed)

    # Sort ascending for anomaly_score (lower = more anomalous)
    if sort_by == "anomaly_score":
        query = query.order_by(AnomalyFlag.anomaly_score.asc())
    elif sort_by == "flagged_at":
        query = query.order_by(AnomalyFlag.flagged_at.desc())
    else:
        query = query.order_by(AnomalyFlag.claim_id)

    total = query.count()
    flags = query.offset((page - 1) * per_page).limit(per_page).all()

    return {
        "flags": [
            {
                "id": f.id,
                "claim_id": f.claim_id,
                "anomaly_score": f.anomaly_score,
                "flag_reason": f.flag_reason,
                "reviewed": f.reviewed,
                "flagged_at": f.flagged_at.isoformat() if f.flagged_at else None,
            }
            for f in flags
        ],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page,
        },
    }


@router.patch("/anomalies/{flag_id}")
def mark_reviewed(flag_id: int, db: Session = Depends(get_db)):
    """Toggle the reviewed status of an anomaly flag."""
    flag = db.query(AnomalyFlag).filter(AnomalyFlag.id == flag_id).first()
    if not flag:
        raise HTTPException(status_code=404, detail="Anomaly flag not found")

    flag.reviewed = not flag.reviewed
    db.commit()
    db.refresh(flag)

    return {
        "id": flag.id,
        "claim_id": flag.claim_id,
        "reviewed": flag.reviewed,
        "message": f"Flag {'marked as reviewed' if flag.reviewed else 'unmarked'}",
    }


@router.get("/anomalies/stats")
def get_anomaly_stats(db: Session = Depends(get_db)):
    """Return overview statistics for the claims + anomaly pipeline."""
    total_claims = db.query(func.count(Claim.id)).scalar() or 0
    total_flagged = db.query(func.count(AnomalyFlag.id)).scalar() or 0
    reviewed_count = db.query(func.count(AnomalyFlag.id)).filter(AnomalyFlag.reviewed == True).scalar() or 0
    avg_score = db.query(func.avg(AnomalyFlag.anomaly_score)).scalar()

    date_range = db.query(
        func.min(Claim.service_date),
        func.max(Claim.service_date),
    ).first()

    return {
        "total_claims": total_claims,
        "total_flagged": total_flagged,
        "flagged_percentage": round(total_flagged / total_claims * 100, 1) if total_claims else 0,
        "reviewed_count": reviewed_count,
        "pending_review": total_flagged - reviewed_count,
        "avg_anomaly_score": round(float(avg_score), 4) if avg_score else None,
        "date_range": {
            "start": str(date_range[0]) if date_range and date_range[0] else None,
            "end": str(date_range[1]) if date_range and date_range[1] else None,
        },
    }
