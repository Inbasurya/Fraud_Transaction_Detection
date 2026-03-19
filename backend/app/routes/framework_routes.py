"""Alias endpoints for research framework compatibility."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.transaction_schema import TransactionCreate
from app.services import fraud_service
from app.routes.alert_routes import live_alerts
from app.routes.account_risk_routes import account_risk_alias
from app.routes.model_routes import get_model_metrics

router = APIRouter()


@router.post("/process_transaction")
async def process_transaction(tx: TransactionCreate, db: Session = Depends(get_db)):
    db_tx = fraud_service.create_transaction(db, tx)
    payload = await fraud_service.process_transaction(db, db_tx)
    await fraud_service.broadcast_transaction(payload)
    if payload.get("risk_category") in ("FRAUD", "SUSPICIOUS") and payload.get("alert_id"):
        await fraud_service.broadcast_alert(payload)
    return payload


@router.get("/fraud_alerts")
def fraud_alerts(limit: int = 50, db: Session = Depends(get_db)):
    return live_alerts(limit=limit, db=db)


@router.get("/account_intelligence")
def account_intelligence(limit: int = 50, db: Session = Depends(get_db)):
    return account_risk_alias(limit=limit, db=db)


@router.get("/model_metrics")
def model_metrics_alias():
    return get_model_metrics()
