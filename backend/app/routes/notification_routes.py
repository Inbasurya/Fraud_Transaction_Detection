"""Notification API routes.

GET /notifications/  — List all notifications
GET /notifications/{customer_id}  — Get notifications for a customer
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.notification_model import Notification
from app.schemas.customer_schema import NotificationResponse

router = APIRouter()


@router.get("/", response_model=List[NotificationResponse])
def list_notifications(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    """List all notifications ordered by most recent."""
    return (
        db.query(Notification)
        .order_by(Notification.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/{customer_id}", response_model=List[NotificationResponse])
def get_customer_notifications(customer_id: str, skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    """Get notifications for a specific customer."""
    return (
        db.query(Notification)
        .filter(Notification.customer_id == customer_id)
        .order_by(Notification.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
