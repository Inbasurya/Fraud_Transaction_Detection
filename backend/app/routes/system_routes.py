from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.limiter import limiter
from app.services.monitoring_service import get_dashboard_metrics, get_fraud_velocity

from app.database import get_db
from app.streaming.engine import streaming_engine
from app.ml.retraining_scheduler import retraining_scheduler

router = APIRouter()


@router.get("/metrics/dashboard")
@limiter.limit("30/minute")
async def dashboard_metrics(request: Request):
    """
    Unified dashboard metrics:
    - Total/Fraud/Flagged counts (last 24h)
    - Fraud rate
    - Velocity
    - System health summary
    """
    return await get_dashboard_metrics()


@router.get("/metrics/velocity")
async def velocity_metrics():
    """
    Returns fraud events per minute for last 60 minutes.
    Used to detect fraud waves.
    """
    return await get_fraud_velocity()


@router.get("/system/health")
def system_health(db: Session = Depends(get_db)):
    db_status = "green"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "red"

    engine_stats = streaming_engine.stats()
    stream_status = "green" if engine_stats.get("consumer_running") else "yellow"
    fraud_engine_status = "green" if db_status == "green" else "yellow"
    model_status = "green"

    return {
        "model_status": model_status,
        "streaming_status": stream_status,
        "fraud_engine_status": fraud_engine_status,
        "database_status": db_status,
        "streaming": engine_stats,
        "retraining": retraining_scheduler.stats(),
    }
