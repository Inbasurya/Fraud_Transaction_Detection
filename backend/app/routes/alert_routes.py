from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.schemas import alert_schema
from app.database import get_db
from app.services import alert_service
from app.models.alert_model import Alert
from app.utils.auth_handler import get_current_user
from app.models.user_model import User

router = APIRouter()


@router.get("/", response_model=List[alert_schema.AlertResponse])
def get_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized",
        )
    return alert_service.get_alerts(db)


@router.get("/live")
def live_alerts(limit: int = 50, db: Session = Depends(get_db)):
    """Recent alerts — public endpoint for dashboard hydration."""
    alerts = (
        db.query(Alert)
        .order_by(Alert.created_at.desc())
        .limit(limit)
        .all()
    )
    results = []
    for a in alerts:
        tx = a.transaction
        results.append({
            "id": a.id,
            "transaction_id": tx.transaction_id if tx else str(a.transaction_id),
            "user_id": tx.user_id if tx else None,
            "amount": tx.amount if tx else None,
            "risk_score": a.risk_score,
            "alert_type": a.alert_type,
            "status": a.status,
            "message": a.message,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        })
    return results
