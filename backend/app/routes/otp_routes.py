"""Step-up authentication OTP routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.case_schema import OTPVerify
from app.services.stepup_auth import generate_otp, verify_otp

router = APIRouter()


@router.post(
    "/{txn_id}/step-up",
    summary="Trigger step-up authentication for a suspicious transaction",
)
def trigger_step_up(
    txn_id: str,
    customer_id: str,
    channel: str = "sms",
    recipient: str = "",
    db: Session = Depends(get_db),
):
    """Generate and send OTP for step-up authentication.

    Called automatically when risk score is between 60-80.
    """
    if not recipient:
        raise HTTPException(status_code=400, detail="Recipient (phone/email) required")

    result = generate_otp(
        db=db,
        transaction_id=txn_id,
        customer_id=customer_id,
        channel=channel,
        recipient=recipient,
    )
    return result


@router.post(
    "/{txn_id}/verify-otp",
    summary="Verify OTP for step-up authentication",
)
def verify_transaction_otp(
    txn_id: str,
    customer_id: str,
    body: OTPVerify,
    db: Session = Depends(get_db),
):
    """Verify submitted OTP.

    - If verified: approve transaction, label as legitimate
    - If fails 3 times: block transaction, escalate to case management
    """
    result = verify_otp(
        db=db,
        transaction_id=txn_id,
        customer_id=customer_id,
        otp_code=body.otp_code,
    )

    if result.get("action") == "block":
        # Escalate: create alert + case
        _escalate_blocked_transaction(db, txn_id, customer_id)

    return result


def _escalate_blocked_transaction(db: Session, txn_id: str, customer_id: str) -> None:
    """Create an alert and case for OTP-blocked transactions."""
    from app.models.alert_model import Alert
    from app.models.case_model import Case
    from app.models.transaction_model import Transaction

    tx = db.query(Transaction).filter(Transaction.transaction_id == txn_id).first()
    if not tx:
        return

    alert = Alert(
        transaction_id=tx.id,
        risk_score=0.85,
        alert_type="OTP_FAILURE",
        status="OPEN",
        message=f"OTP verification failed {settings.OTP_MAX_ATTEMPTS} times for transaction {txn_id}",
    )
    db.add(alert)
    db.flush()

    case = Case(
        alert_id=alert.id,
        status="OPEN",
        priority="HIGH",
        notes=f"Auto-escalated: OTP failure for customer {customer_id}, txn {txn_id}",
    )
    db.add(case)
    db.commit()


# Import settings at module level for escalation
from app.config import settings
