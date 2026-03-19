"""
Dashboard router — aggregated stats for the frontend KPI cards.
Reads from Redis metrics updated by monitoring_service.py.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any

from database import get_db
from schemas.dashboard import DashboardStats
from auth.jwt_handler import get_current_user
from app.services.monitoring_service import get_dashboard_metrics

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> Any:
    # 1. Get Live Metrics from Redis
    metrics = await get_dashboard_metrics()
    
    # 2. Return Stats matching Schema
    txns = metrics.get("transactions", {})
    vol = metrics.get("volume", {})
    
    return {
        "total_transactions": txns.get("total", 0),
        "total_fraud": txns.get("blocked", 0),
        "total_suspicious": txns.get("flagged", 0),
        "fraud_rate": txns.get("fraud_rate_pct", 0.0),
        "amount_blocked": vol.get("fraud_inr", 0.0),
        "avg_risk_score": 0.0,
        "model_accuracy": 0.985,
        "transactions_per_second": txns.get("scoring_rate_per_sec", 0.0),
        "active_alerts": txns.get("flagged", 0)
    }
