"""Real-time fraud processing service used by transaction routes."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import fraud_prediction_model, transaction_model
from app.models.training_feedback_model import TrainingFeedback
from app.schemas import transaction_schema
from app.fraud_engine.pipeline import run_realtime_pipeline
from app.services.alert_service_v2 import create_fraud_alert
from app.services.explain_service import explain_prediction
from app.services.monitoring_service import update_all_metrics
from app.websocket.manager import ws_manager


def create_transaction(db: Session, tx: transaction_schema.TransactionCreate):
    tx_payload = tx.model_dump(exclude={"is_fraud_label", "label_source"})
    db_tx = transaction_model.Transaction(**tx_payload)
    db.add(db_tx)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = (
            db.query(transaction_model.Transaction)
            .filter_by(transaction_id=tx.transaction_id)
            .first()
        )
        if existing:
            return existing
        raise
    db.refresh(db_tx)
    if tx.is_fraud_label is not None:
        feedback = TrainingFeedback(
            transaction_id=db_tx.id,
            user_id=db_tx.user_id,
            amount=float(db_tx.amount or 0.0),
            merchant=db_tx.merchant,
            location=db_tx.location,
            device_type=db_tx.device_type,
            timestamp=db_tx.timestamp,
            is_fraud_label=bool(tx.is_fraud_label),
            label_source=tx.label_source or "stream_label",
        )
        db.add(feedback)
        db.commit()
    return db_tx


def get_transactions(db: Session, skip: int = 0, limit: int = 100):
    return (
        db.query(transaction_model.Transaction)
        .order_by(transaction_model.Transaction.timestamp.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


async def process_transaction(db: Session, db_tx: transaction_model.Transaction) -> dict:
    """Pipeline: features -> supervised model -> behavior model -> rules -> risk."""
    tx_dict = {
        "transaction_id": db_tx.transaction_id,
        "user_id": db_tx.user_id,
        "amount": db_tx.amount,
        "merchant": db_tx.merchant,
        "location": db_tx.location,
        "device_type": db_tx.device_type,
        "timestamp": db_tx.timestamp,
    }

    scored = await run_realtime_pipeline(db, db_tx)
    
    # Extract scores
    risk_score = float(scored["risk_score"])  # stored as float in DB typically, but here it's int
    # Actually, hybrid_engine returns int now for risk_score.
    
    action = scored["action"]
    priority = scored["priority"]
    reasons = scored["reasons"]
    
    kaggle_prob = float(scored.get("kaggle_probability", 0.0))
    behavior_score = float(scored.get("behavior_anomaly_score", 0.0))
    rule_score = float(scored.get("rule_score", 0.0))
    graph_risk_score = float(scored.get("graph_risk_score", 0.0))
    
    # --- Update metrics atomically ---
    await update_all_metrics(
        transaction_id=db_tx.transaction_id,
        risk_score=risk_score,
        amount=float(db_tx.amount or 0.0)
    )

    # Record prediction
    _record_prediction(
        db,
        transaction_id=db_tx.id,
        probability=kaggle_prob,
        risk_score=risk_score,
        risk_category=f"{action}/{priority}",
        model_used="hybrid_v2",
    )

    update_profile(db, db_tx)

    alert_record = None
    if action in ["REVIEW", "BLOCK"] or risk_score >= 85:
        alert_record = create_fraud_alert(db, db_tx, risk_score, reasons)

    # Explain prediction
    # Note: explain_service.explain_prediction signature might need check.
    # Assuming it takes: (transaction_dict, features, risk_score, risk_category, 
    #                     kaggle_prob, behavior_score, rule_score, reasons, shap)
    explanation = explain_prediction(
        tx_dict,
        scored["features"],
        risk_score,
        f"{action}/{priority}",  # risk_category
        kaggle_prob,
        behavior_score,
        rule_score,
        reasons,
        scored.get("shap"),
    )

    # Metrics update
    await update_all_metrics(
        transaction_id=db_tx.transaction_id,
        risk_score=risk_score,
        amount=float(db_tx.amount or 0.0),
        decision=action,
        customer_id=db_tx.user_id
    )


    payload = {
        "id": db_tx.id,
        "transaction_id": db_tx.transaction_id,
        "user_id": db_tx.user_id,
        "amount": db_tx.amount,
        "merchant": db_tx.merchant,
        "location": db_tx.location,
        "device_type": db_tx.device_type,
        "timestamp": db_tx.timestamp.isoformat() if db_tx.timestamp else None,
        "created_at": db_tx.created_at.isoformat() if db_tx.created_at else None,
        "fraud_probability": round(kaggle_prob, 4),
        "kaggle_probability": round(kaggle_prob, 4),
        "behavior_score": round(behavior_score, 4),
        "behavior_anomaly_score": round(behavior_score, 4),
        "rule_score": round(rule_score, 4),
        "graph_risk_score": round(graph_risk_score, 4),
        "risk_score": round(risk_score, 4),
        "risk_category": f"{action}/{priority}",
        "action": action,
        "priority": priority,
        "reasons": reasons,
        "features": scored["features"],
        "behavior_profile": scored.get("behavior_profile", {}),
        "explainability": scored.get("explainability", {}),
        "shap": scored.get("shap", {}),
        "explanation": explanation,
        "weights": scored.get("weights", {}),
    }

    if alert_record:
        payload["alert_id"] = alert_record.id

    # Broadcast to websocket
    await ws_manager.broadcast(payload)
    
    return payload



def _record_prediction(
    db: Session,
    transaction_id: int,
    probability: float,
    risk_score: float,
    risk_category: str,
    model_used: str,
):
    pred = fraud_prediction_model.FraudPrediction(
        transaction_id=transaction_id,
        fraud_probability=probability,
        risk_score=risk_score,
        risk_category=risk_category,
        model_used=model_used,
    )
    db.add(pred)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return None
    db.refresh(pred)
    return pred


async def broadcast_transaction(payload: dict):
    await ws_manager.broadcast(
        "stream",
        {
            "type": "transaction_update",
            "transaction": payload,
            "data": payload,
        },
    )


async def broadcast_alert(payload: dict):
    risk_score = float(payload.get("risk_score") or 0.0)
    severity = "HIGH" if risk_score >= 0.85 else "MEDIUM" if risk_score >= ALERT_THRESHOLD else "LOW"
    alert_payload = {
        "alert_id": f"ALERT-{payload.get('alert_id', '')}",
        "transaction_id": payload.get("transaction_id"),
        "risk_score": risk_score,
        "severity": severity,
        "account_id": payload.get("user_id"),
        "amount": payload.get("amount"),
        "timestamp": payload.get("timestamp"),
        "reasons": payload.get("reasons", []),
        "message": "; ".join(payload.get("reasons", []))
        or "High risk fraud transaction detected",
    }
    await ws_manager.broadcast(
        "alerts",
        {
            "type": "fraud_alert",
            "alert": alert_payload,
            "data": payload,
        },
    )
