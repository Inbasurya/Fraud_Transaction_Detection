"""Analytics routes — graph detection, pattern detection, account risk views."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, case

from app.database import get_db
from app.analytics.graph_detection import (
    detect_fraud_clusters,
    detect_device_rings,
    get_graph_data,
)
from app.services.pattern_detector import detect_all_patterns
from app.models.transaction_model import Transaction
from app.models.fraud_prediction_model import FraudPrediction
from app.models.user_profile_model import UserProfile

router = APIRouter()


# ── Graph-based fraud detection ───────────────────────────────

@router.get("/graph")
def fraud_graph(limit: int = 500, db: Session = Depends(get_db)):
    """Return graph data (nodes + edges) for force-graph visualization."""
    return get_graph_data(db, limit=limit)


@router.get("/clusters")
def fraud_clusters(min_risk: float = 0.4, db: Session = Depends(get_db)):
    """Detect fraud clusters — connected components with high avg risk."""
    return detect_fraud_clusters(db, min_risk=min_risk)


@router.get("/device-rings")
def device_rings(db: Session = Depends(get_db)):
    """Detect devices shared by multiple users."""
    return detect_device_rings(db)


# ── Pattern detection ─────────────────────────────────────────

@router.get("/patterns")
def fraud_patterns(db: Session = Depends(get_db)):
    """Run all pattern detectors and return results."""
    return detect_all_patterns(db)


# ── Account risk views ────────────────────────────────────────

@router.get("/accounts")
def account_risk(limit: int = 50, db: Session = Depends(get_db)):
    """Return accounts ranked by risk level with activity summary."""
    rows = (
        db.query(
            Transaction.user_id,
            func.count(Transaction.id).label("tx_count"),
            func.sum(Transaction.amount).label("total_amount"),
            func.avg(FraudPrediction.risk_score).label("avg_risk"),
            func.max(FraudPrediction.risk_score).label("max_risk"),
            func.max(Transaction.timestamp).label("last_activity"),
            func.count(func.distinct(Transaction.device_type)).label("distinct_devices"),
            func.count(func.distinct(Transaction.location)).label("distinct_locations"),
            func.sum(
                case(
                    (FraudPrediction.risk_category == "FRAUD", 1),
                    else_=0,
                )
            ).label("fraud_count"),
            func.sum(
                case(
                    (FraudPrediction.risk_category == "SUSPICIOUS", 1),
                    else_=0,
                )
            ).label("suspicious_count"),
        )
        .outerjoin(FraudPrediction, FraudPrediction.transaction_id == Transaction.id)
        .group_by(Transaction.user_id)
        .order_by(desc("avg_risk"))
        .limit(limit)
        .all()
    )

    accounts = []
    for r in rows:
        avg_risk = float(r[3] or 0)
        tx_count = int(r[1] or 0)
        fraud_count = int(r[8] or 0)
        suspicious_count = int(r[9] or 0)
        distinct_devices = int(r[6] or 0)
        distinct_locations = int(r[7] or 0)
        device_change_score = (max(distinct_devices - 1, 0) / tx_count) if tx_count else 0.0
        location_change_score = (max(distinct_locations - 1, 0) / tx_count) if tx_count else 0.0
        avg_amount = (float(r[2] or 0) / tx_count) if tx_count else 0.0
        fraud_ratio = ((fraud_count + suspicious_count) / tx_count) if tx_count else 0.0
        risk_level = "CRITICAL" if avg_risk >= 0.7 else "HIGH" if avg_risk >= 0.4 else "LOW"
        accounts.append({
            "user_id": r[0],
            "tx_count": tx_count,
            "total_amount": round(float(r[2] or 0), 2),
            "avg_amount": round(avg_amount, 2),
            "fraud_ratio": round(fraud_ratio, 4),
            "avg_risk": round(avg_risk, 4),
            "max_risk": round(float(r[4] or 0), 4),
            "last_activity": r[5].isoformat() if r[5] else None,
            "distinct_devices": distinct_devices,
            "distinct_locations": distinct_locations,
            "device_change_score": round(device_change_score, 4),
            "location_change_score": round(location_change_score, 4),
            "fraud_count": fraud_count,
            "suspicious_count": suspicious_count,
            "risk_level": risk_level,
        })

    return accounts


@router.get("/accounts/{user_id}")
def account_detail(user_id: int, db: Session = Depends(get_db)):
    """Detailed account view with recent transactions and profile."""
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()

    txs = (
        db.query(Transaction)
        .filter(Transaction.user_id == user_id)
        .order_by(Transaction.timestamp.desc())
        .limit(50)
        .all()
    )

    tx_list = []
    for t in txs:
        record = {
            "transaction_id": t.transaction_id,
            "amount": t.amount,
            "merchant": t.merchant,
            "location": t.location,
            "device_type": t.device_type,
            "timestamp": t.timestamp.isoformat() if t.timestamp else None,
        }
        if t.prediction:
            record["risk_score"] = t.prediction.risk_score
            record["risk_category"] = t.prediction.risk_category
        tx_list.append(record)

    return {
        "user_id": user_id,
        "profile": {
            "avg_transaction_amount": profile.avg_transaction_amount if profile else 0,
            "total_transactions": profile.total_transactions if profile else 0,
            "last_location": profile.last_location if profile else None,
            "last_device": profile.last_device if profile else None,
            "last_merchant": profile.last_merchant if profile else None,
        } if profile else None,
        "recent_transactions": tx_list,
    }


@router.get("/accounts/{user_id}/risk-trend")
def account_risk_trend(user_id: int, points: int = 24, db: Session = Depends(get_db)):
    rows = (
        db.query(
            Transaction.timestamp,
            FraudPrediction.risk_score,
            FraudPrediction.risk_category,
        )
        .outerjoin(FraudPrediction, FraudPrediction.transaction_id == Transaction.id)
        .filter(Transaction.user_id == user_id)
        .order_by(Transaction.timestamp.desc())
        .limit(points)
        .all()
    )
    trend = [
        {
            "timestamp": ts.isoformat() if ts else None,
            "risk_score": round(float(risk or 0), 4),
            "risk_category": category or "SAFE",
        }
        for ts, risk, category in reversed(rows)
    ]
    return {"user_id": user_id, "points": trend}


@router.get("/heatmap")
def fraud_heatmap(db: Session = Depends(get_db)):
    rows = (
        db.query(
            Transaction.location,
            func.count(Transaction.id).label("transactions"),
            func.avg(FraudPrediction.risk_score).label("avg_risk"),
            func.sum(case((FraudPrediction.risk_category == "FRAUD", 1), else_=0)).label("fraud_count"),
            func.sum(case((FraudPrediction.risk_category == "SUSPICIOUS", 1), else_=0)).label("suspicious_count"),
        )
        .outerjoin(FraudPrediction, FraudPrediction.transaction_id == Transaction.id)
        .group_by(Transaction.location)
        .order_by(desc("fraud_count"))
        .all()
    )
    return [
        {
            "location": (location or "Unknown"),
            "transactions": int(transactions or 0),
            "avg_risk": round(float(avg_risk or 0), 4),
            "fraud_count": int(fraud_count or 0),
            "suspicious_count": int(suspicious_count or 0),
            "hotspot_score": round(float((fraud_count or 0) * 1.2 + (suspicious_count or 0) * 0.6), 3),
        }
        for location, transactions, avg_risk, fraud_count, suspicious_count in rows
    ]
