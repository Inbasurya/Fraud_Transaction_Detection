"""Fraud statistics and analytics routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, cast, String
from app.database import get_db
from app.models.transaction_model import Transaction
from app.models.fraud_prediction_model import FraudPrediction
from app.models.alert_model import Alert

router = APIRouter()


@router.get("/stats")
def fraud_stats(db: Session = Depends(get_db)):
    """Aggregate fraud statistics — public endpoint for dashboard."""
    total = db.query(func.count(Transaction.id)).scalar() or 0
    fraud = (
        db.query(func.count(FraudPrediction.id))
        .filter(FraudPrediction.risk_category == "FRAUD")
        .scalar()
    ) or 0
    suspicious = (
        db.query(func.count(FraudPrediction.id))
        .filter(FraudPrediction.risk_category == "SUSPICIOUS")
        .scalar()
    ) or 0
    safe = (
        db.query(func.count(FraudPrediction.id))
        .filter(FraudPrediction.risk_category == "SAFE")
        .scalar()
    ) or 0
    open_alerts = (
        db.query(func.count(Alert.id))
        .filter(Alert.status == "OPEN")
        .scalar()
    ) or 0

    fraud_rate = round((fraud / total * 100), 2) if total > 0 else 0.0

    return {
        "total_transactions": total,
        "fraud": fraud,
        "suspicious": suspicious,
        "safe": safe,
        "open_alerts": open_alerts,
        "fraud_rate": fraud_rate,
    }


@router.get("/top-merchants")
def top_risky_merchants(limit: int = 10, db: Session = Depends(get_db)):
    """Top merchants by fraud count."""
    rows = (
        db.query(
            Transaction.merchant,
            func.count(FraudPrediction.id).label("fraud_count"),
            func.avg(FraudPrediction.risk_score).label("avg_risk"),
        )
        .join(FraudPrediction, FraudPrediction.transaction_id == Transaction.id)
        .filter(FraudPrediction.risk_category.in_(["FRAUD", "SUSPICIOUS"]))
        .group_by(Transaction.merchant)
        .order_by(desc("fraud_count"))
        .limit(limit)
        .all()
    )
    return [
        {"merchant": r[0] or "Unknown", "fraud_count": r[1], "avg_risk": round(float(r[2] or 0), 4)}
        for r in rows
    ]


@router.get("/velocity")
def transaction_velocity(db: Session = Depends(get_db)):
    """Transaction count grouped by hour for velocity chart."""
    hour_expr = cast(func.extract("hour", Transaction.timestamp), String)
    rows = (
        db.query(
            hour_expr.label("hour"),
            func.count(Transaction.id).label("count"),
        )
        .group_by(hour_expr)
        .order_by(hour_expr)
        .all()
    )
    return [{"hour": r[0], "count": r[1]} for r in rows]


@router.get("/high-risk-users")
def high_risk_users(limit: int = 10, db: Session = Depends(get_db)):
    """Users with highest average risk scores."""
    rows = (
        db.query(
            Transaction.user_id,
            func.count(Transaction.id).label("tx_count"),
            func.avg(FraudPrediction.risk_score).label("avg_risk"),
            func.sum(Transaction.amount).label("total_amount"),
        )
        .join(FraudPrediction, FraudPrediction.transaction_id == Transaction.id)
        .group_by(Transaction.user_id)
        .order_by(desc("avg_risk"))
        .limit(limit)
        .all()
    )
    return [
        {
            "user_id": r[0],
            "tx_count": r[1],
            "avg_risk": round(float(r[2] or 0), 4),
            "total_amount": round(float(r[3] or 0), 2),
        }
        for r in rows
    ]
