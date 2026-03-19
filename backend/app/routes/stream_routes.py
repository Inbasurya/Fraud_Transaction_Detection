"""Stream routes — latest transactions for initial dashboard hydration."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.transaction_model import Transaction
from app.streaming.engine import streaming_engine

router = APIRouter()


@router.get("/transactions")
def latest_transactions(limit: int = 50, db: Session = Depends(get_db)):
    """Return last N transactions with risk info (no auth — public feed)."""
    txs = (
        db.query(Transaction)
        .order_by(Transaction.timestamp.desc())
        .limit(limit)
        .all()
    )
    results = []
    for t in txs:
        record = {
            "id": t.id,
            "transaction_id": t.transaction_id,
            "user_id": t.user_id,
            "amount": t.amount,
            "merchant": t.merchant,
            "location": t.location,
            "device_type": t.device_type,
            "timestamp": t.timestamp.isoformat() if t.timestamp else None,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "risk_score": None,
            "risk_category": None,
            "fraud_probability": None,
            "behavior_score": None,
            "rule_score": None,
        }
        if t.prediction:
            record["risk_score"] = t.prediction.risk_score
            record["risk_category"] = t.prediction.risk_category
            record["fraud_probability"] = t.prediction.fraud_probability
        results.append(record)
    return results


@router.get("/engine-status")
def stream_engine_status():
    return streaming_engine.stats()
