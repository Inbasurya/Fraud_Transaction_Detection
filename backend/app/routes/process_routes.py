"""Real-time transaction processing pipeline.

POST /transaction/process

Pipeline: transaction → feature engineering → rule engine → ML model
          → anomaly detection → graph analysis → risk scoring → alert system
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.transaction_model import Transaction
from app.models.customer_model import Customer
from app.models.device_model import Device
from app.models.alert_model import Alert
from app.models import fraud_prediction_model
from app.services.feature_engineering import compute_behavioral_features
from app.rule_engine.fraud_rules import evaluate_fraud_rules
from app.ml_models.supervised_fraud_model import supervised_fraud_model
from app.ml_models.anomaly_model import anomaly_model
from app.graph_detection.fraud_graph import fraud_graph
from app.services.risk_engine import compute_hybrid_risk
from app.notification.notification_service import send_fraud_notification
from app.websocket.manager import ws_manager

router = APIRouter()


class ProcessTransactionRequest(BaseModel):
    transaction_id: str
    customer_id: str
    amount: float
    merchant: Optional[str] = None
    location: Optional[str] = None
    device_id: Optional[str] = None
    device_type: Optional[str] = None
    browser: Optional[str] = None
    operating_system: Optional[str] = None
    ip_address: Optional[str] = None
    timestamp: Optional[datetime] = None


@router.post("/process")
async def process_transaction(req: ProcessTransactionRequest, db: Session = Depends(get_db)):
    """Full fraud detection pipeline for a single transaction.

    Pipeline: feature engineering → rule engine → ML model → anomaly detection
              → graph analysis → hybrid risk scoring → alert + notification
    """
    ts = req.timestamp or datetime.utcnow()

    # ── 1. Resolve or create user mapping ─────────────────────
    # Map customer_id to user_id (int) for Transaction model compatibility
    customer = db.query(Customer).filter(Customer.customer_id == req.customer_id).first()
    user_id = customer.id if customer else 1  # fallback

    # ── 2. Create transaction record ─────────────────────────
    db_tx = Transaction(
        transaction_id=req.transaction_id,
        user_id=user_id,
        amount=req.amount,
        merchant=req.merchant,
        location=req.location,
        device_type=req.device_type,
        timestamp=ts,
    )
    db.add(db_tx)
    db.commit()
    db.refresh(db_tx)

    # ── 3. Device fingerprinting ─────────────────────────────
    device_change_flag = 0.0
    if req.device_id and customer:
        existing_device = (
            db.query(Device)
            .filter(Device.device_id == req.device_id, Device.customer_id == req.customer_id)
            .first()
        )
        if existing_device:
            existing_device.last_used = ts
            db.commit()
        else:
            new_device = Device(
                device_id=req.device_id,
                customer_id=req.customer_id,
                device_type=req.device_type,
                browser=req.browser,
                operating_system=req.operating_system,
                ip_address=req.ip_address,
            )
            db.add(new_device)
            db.commit()
            device_change_flag = 1.0

    # ── 4. Feature engineering ────────────────────────────────
    behavioral_features = compute_behavioral_features(db, db_tx, customer)

    # Merge core features for ML
    from app.core.features import build_features
    core_features = build_features(db, db_tx)
    all_features = {**core_features, **behavioral_features}

    # Override device_change if new device detected
    if device_change_flag:
        all_features["device_change_flag"] = 1.0
        all_features["new_device_flag"] = 1.0

    # ── 5. Rule engine ────────────────────────────────────────
    rule_result = evaluate_fraud_rules(all_features, db_tx)

    # ── 6. ML model prediction ────────────────────────────────
    ml_probability = supervised_fraud_model.predict_fraud_probability(all_features)

    # ── 7. Anomaly detection ──────────────────────────────────
    anomaly_score = anomaly_model.predict_anomaly_score(all_features)

    # ── 8. Graph analysis ─────────────────────────────────────
    graph_risk_score = fraud_graph.compute_graph_risk_score(user_id)

    # ── 9. Hybrid risk scoring ────────────────────────────────
    assessment = compute_hybrid_risk(
        ml_probability=ml_probability,
        anomaly_score=anomaly_score,
        graph_risk_score=graph_risk_score,
        rule_score=rule_result.rule_score,
        rule_reasons=rule_result.triggered_rules,
    )

    # ── 10. Record prediction ─────────────────────────────────
    pred = fraud_prediction_model.FraudPrediction(
        transaction_id=db_tx.id,
        fraud_probability=ml_probability,
        risk_score=assessment.risk_score,
        risk_category=assessment.risk_category,
        model_used="supervised+anomaly+graph+rules",
    )
    db.add(pred)
    db.commit()

    # ── 11. Alert generation ──────────────────────────────────
    alert_id = None
    if assessment.risk_category in ("SUSPICIOUS", "FRAUD"):
        alert_type = "FRAUD" if assessment.risk_category == "FRAUD" else "SUSPICIOUS"
        alert = Alert(
            transaction_id=db_tx.id,
            risk_score=assessment.risk_score,
            alert_type=alert_type,
            status="OPEN",
            message="; ".join(assessment.reasons[:5]) or f"{alert_type} transaction detected",
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        alert_id = alert.id

    # ── 12. Notification (for FRAUD) ──────────────────────────
    notifications_sent = 0
    if assessment.risk_category == "FRAUD" and customer:
        sent = send_fraud_notification(
            db, customer, db_tx.id,
            assessment.risk_score, assessment.risk_category,
            req.amount, req.merchant,
        )
        notifications_sent = len(sent)

    # ── 13. Update customer profile ───────────────────────────
    if customer:
        total = customer.total_transactions + 1
        customer.avg_transaction_amount = (
            (customer.avg_transaction_amount * customer.total_transactions + req.amount) / total
        )
        customer.total_transactions = total
        if assessment.risk_score >= 0.85:
            customer.risk_level = "CRITICAL"
        elif assessment.risk_score >= 0.70:
            customer.risk_level = "HIGH"
        elif assessment.risk_score >= 0.30:
            customer.risk_level = "MEDIUM"
        db.commit()

    # ── 14. WebSocket broadcast ───────────────────────────────
    payload = {
        "id": db_tx.id,
        "transaction_id": req.transaction_id,
        "customer_id": req.customer_id,
        "user_id": user_id,
        "amount": req.amount,
        "merchant": req.merchant,
        "location": req.location,
        "device_type": req.device_type,
        "timestamp": ts.isoformat(),
        "risk_score": assessment.risk_score,
        "risk_category": assessment.risk_category,
        "ml_probability": assessment.ml_probability,
        "anomaly_score": assessment.anomaly_score,
        "graph_risk_score": assessment.graph_risk_score,
        "rule_score": assessment.rule_score,
        "fraud_probability": assessment.ml_probability,
        "reasons": assessment.reasons,
        "weights": assessment.weights,
        "alert_id": alert_id,
        "notifications_sent": notifications_sent,
        "status": assessment.risk_category,
    }

    await ws_manager.broadcast("stream", {"type": "transaction_update", "transaction": payload, "data": payload})
    if alert_id:
        await ws_manager.broadcast("alerts", {"type": "fraud_alert", "alert": payload, "data": payload})

    return payload
