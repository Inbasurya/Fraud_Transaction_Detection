"""Alert service — create, store, and manage fraud alerts."""

from __future__ import annotations
import uuid
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.alert_model import Alert
from app.models.transaction_model import Transaction
from app.websocket.manager import ws_manager

logger = logging.getLogger(__name__)


def create_fraud_alert(
    db: Session,
    tx: Transaction,
    risk_score: float,
    reasons: list[str],
) -> Alert:
    """Create and persist a fraud alert, then broadcast over WebSocket."""
    alert_id = f"ALERT-{uuid.uuid4().hex[:8].upper()}"
    message = "; ".join(reasons) if reasons else "High risk fraud transaction detected"

    alert = Alert(
        transaction_id=tx.id,
        risk_score=risk_score,
        alert_type="ADMIN_ALERT",
        status="OPEN",
        message=message,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    logger.info("Alert %s created for TX %s (risk=%.2f)", alert.id, tx.transaction_id, risk_score)
    return alert


def build_alert_payload(alert: Alert, tx: Transaction) -> dict:
    """Build the WebSocket broadcast payload for an alert."""
    return {
        "id": alert.id,
        "alert_id": f"ALERT-{alert.id}",
        "transaction_id": tx.transaction_id,
        "user_id": tx.user_id,
        "amount": tx.amount,
        "merchant": tx.merchant,
        "location": tx.location,
        "risk_score": alert.risk_score,
        "alert_type": alert.alert_type,
        "status": alert.status,
        "message": alert.message,
        "created_at": alert.created_at.isoformat() if alert.created_at else None,
    }


async def broadcast_alert(payload: dict):
    """Broadcast a fraud_alert message to the alerts WebSocket room."""
    await ws_manager.broadcast("alerts", {"type": "fraud_alert", "data": payload})


def get_alerts(db: Session, status: str | None = None, limit: int = 100):
    """Retrieve alerts, optionally filtering by status."""
    query = db.query(Alert).order_by(Alert.created_at.desc())
    if status:
        query = query.filter(Alert.status == status)
    return query.limit(limit).all()


def close_alert(db: Session, alert_id: int) -> Alert | None:
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if alert:
        alert.status = "CLOSED"
        db.commit()
        db.refresh(alert)
    return alert
