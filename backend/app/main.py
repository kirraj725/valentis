"""
ClearCollect AI — FastAPI Application Entry Point

Hospital Revenue & Payment Risk Intelligence Platform
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import upload, risk, fraud, anomaly, forecast, payment_plan, audit, auth, ingest, analyze, summarize, metrics

app = FastAPI(
    title="ClearCollect AI",
    description="Hospital Revenue & Payment Risk Intelligence Platform",
    version="1.0.0",
)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(upload.router, prefix="/api/upload", tags=["Upload"])
app.include_router(risk.router, prefix="/api/risk", tags=["Risk Scoring"])
app.include_router(fraud.router, prefix="/api/fraud", tags=["Fraud Detection"])
app.include_router(anomaly.router, prefix="/api/anomaly", tags=["Anomaly Detection"])
app.include_router(forecast.router, prefix="/api/forecast", tags=["Revenue Forecast"])
app.include_router(payment_plan.router, prefix="/api/plans", tags=["Payment Plans"])
app.include_router(audit.router, prefix="/api/audit", tags=["Audit & Security"])
app.include_router(ingest.router, prefix="/api/ingest", tags=["Data Ingestion"])
app.include_router(analyze.router, prefix="/api", tags=["ML Analysis"])
app.include_router(summarize.router, prefix="/api/insights", tags=["AI Insights"])
app.include_router(metrics.router, tags=["Observability"])


@app.get("/")
async def root():
    return {"message": "ClearCollect AI API is running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
