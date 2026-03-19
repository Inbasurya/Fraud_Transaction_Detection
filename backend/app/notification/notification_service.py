"""SMS / Email notification service for fraud alerts.

In production, integrate with Twilio (SMS) and SendGrid/SES (email).
For now, logs the notification and stores it in the notifications table.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.notification_model import Notification
from app.models.customer_model import Customer

logger = logging.getLogger(__name__)


def send_sms(
    db: Session,
    customer_id: str,
    phone: str,
    message: str,
    transaction_id: Optional[int] = None,
) -> Notification:
    """Send SMS alert to customer (simulated).

    In production: integrate with Twilio API.
    """
    logger.info("SMS → %s: %s", phone, message[:80])

    notification = Notification(
        customer_id=customer_id,
        transaction_id=transaction_id,
        notification_type="SMS",
        recipient=phone,
        subject=None,
        message=message,
        status="SENT",
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def send_email(
    db: Session,
    customer_id: str,
    email: str,
    subject: str,
    message: str,
    transaction_id: Optional[int] = None,
) -> Notification:
    """Send email alert to customer (simulated).

    In production: integrate with SendGrid/AWS SES.
    """
    logger.info("EMAIL → %s: [%s] %s", email, subject, message[:80])

    notification = Notification(
        customer_id=customer_id,
        transaction_id=transaction_id,
        notification_type="EMAIL",
        recipient=email,
        subject=subject,
        message=message,
        status="SENT",
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def send_fraud_notification(
    db: Session,
    customer: Customer,
    transaction_id: int,
    risk_score: float,
    risk_category: str,
    amount: float,
    merchant: Optional[str] = None,
) -> list[Notification]:
    """Send both SMS and email fraud alert to a customer."""
    notifications = []

    msg = (
        f"⚠️ Fraud Alert: A {risk_category} transaction of ${amount:,.2f}"
        f"{f' at {merchant}' if merchant else ''} was flagged on your account "
        f"(risk score: {risk_score:.2f}). If this wasn't you, please contact "
        f"your bank immediately at 1-800-BANK-SAFE."
    )

    subject = f"🚨 Fraud Alert — {risk_category} Transaction Detected"

    if customer.phone:
        notifications.append(
            send_sms(db, customer.customer_id, customer.phone, msg, transaction_id)
        )

    if customer.email:
        notifications.append(
            send_email(db, customer.customer_id, customer.email, subject, msg, transaction_id)
        )

    logger.info(
        "Fraud notifications sent for customer %s, tx %d, risk %.2f",
        customer.customer_id, transaction_id, risk_score,
    )
    return notifications
