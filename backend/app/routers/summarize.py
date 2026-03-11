"""
Insights endpoints — LLM-generated provider summaries.

POST /api/insights/generate — generate summaries from current anomaly flags
GET  /api/insights          — return cached summaries
"""

import time
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import AnomalyFlag, Claim
from app.config import settings

router = APIRouter()

# In-memory cache for generated summaries (persists across requests)
_cached_summaries: list[dict] = []
_last_generation_time: float | None = None
_last_latency: float | None = None


def get_summarization_latency() -> float | None:
    """Return the last summarization latency in seconds (for metrics)."""
    return _last_latency


@router.post("/generate")
def generate_insights(db: Session = Depends(get_db)):
    """Generate AI summaries grouped by provider from current anomaly flags."""
    global _cached_summaries, _last_generation_time, _last_latency
    from ml.summarizer import generate_summaries

    flags = db.query(AnomalyFlag).all()
    if not flags:
        raise HTTPException(status_code=404, detail="No anomaly flags found. Run /api/analyze first.")

    # Group by provider via claim lookup
    claim_map = {}
    claim_ids = [f.claim_id for f in flags]
    claims = db.query(Claim).filter(Claim.claim_id.in_(claim_ids)).all()
    for c in claims:
        claim_map[c.claim_id] = c.provider_id

    grouped: dict[str, list[dict]] = defaultdict(list)
    for f in flags:
        provider = claim_map.get(f.claim_id, "UNKNOWN")
        grouped[provider].append({
            "claim_id": f.claim_id,
            "anomaly_score": f.anomaly_score,
            "flag_reason": f.flag_reason,
            "reviewed": f.reviewed,
        })

    # Sort providers by total flags descending and cap at top 20
    sorted_providers = sorted(grouped.items(), key=lambda x: len(x[1]), reverse=True)[:20]
    top_grouped = dict(sorted_providers)

    start = time.time()
    summaries = generate_summaries(
        top_grouped,
        api_key=getattr(settings, "ANTHROPIC_API_KEY", None),
    )
    _last_latency = round(time.time() - start, 2)

    _cached_summaries = summaries
    _last_generation_time = time.time()

    return {
        "status": "complete",
        "summaries": summaries,
        "providers_analyzed": len(summaries),
        "generation_time_seconds": _last_latency,
    }


@router.get("/")
def get_insights():
    """Return the most recently generated summaries."""
    if not _cached_summaries:
        return {
            "summaries": [],
            "message": "No summaries generated yet. Call POST /api/insights/generate first.",
        }

    return {
        "summaries": _cached_summaries,
        "generated_at": _last_generation_time,
        "providers_count": len(_cached_summaries),
    }
