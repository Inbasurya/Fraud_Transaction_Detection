from datetime import datetime
from sqlalchemy.orm import Session
from app.models import alert_model


def create_alert(db: Session, transaction_id: int, risk_score: float) -> None:
    """Generate both admin and user alerts for a high-risk transaction."""
    message = "High risk transaction detected. Immediate review required."
    for alert_type in ("ADMIN_ALERT", "USER_ALERT"):
        alert = alert_model.Alert(
            transaction_id=transaction_id,
            risk_score=risk_score,
            alert_type=alert_type,
            status="OPEN",
            message=message,
        )
        db.add(alert)
    db.commit()


def get_alerts(db: Session, status: str = None):
    """Retrieve alerts, optionally filtering by status."""
    query = db.query(alert_model.Alert)
    if status:
        query = query.filter(alert_model.Alert.status == status)
    return query.all()
