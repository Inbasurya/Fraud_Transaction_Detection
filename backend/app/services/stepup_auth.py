"""Step-Up Authentication Service — OTP generation, verification, and escalation.

When risk score is between 60-80 (suspicious range):
1. Generate 6-digit OTP
2. Store in Redis with 5-minute TTL
3. Send via SMS (Twilio) or email (SendGrid)
4. Verify OTP or escalate after 3 failed attempts
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import time
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.models.otp_model import OTPAttempt

logger = logging.getLogger(__name__)


def _get_redis():
    try:
        import redis
        r = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True, socket_timeout=2)
        r.ping()
        return r
    except Exception:
        return None


def _hash_otp(otp: str) -> str:
    return hashlib.sha256(otp.encode()).hexdigest()


def generate_otp(
    db: Session,
    transaction_id: str,
    customer_id: str,
    channel: str = "sms",
    recipient: str = "",
) -> dict[str, Any]:
    """Generate a 6-digit OTP and store in Redis + DB.

    Args:
        db: Database session
        transaction_id: The transaction requiring step-up auth
        customer_id: Customer ID
        channel: "sms" or "email"
        recipient: Phone number or email address

    Returns:
        Dict with otp (only in dev/test), channel, recipient, expires_in
    """
    otp_code = f"{secrets.randbelow(900000) + 100000:06d}"
    otp_hash = _hash_otp(otp_code)

    # Store in Redis with TTL
    r = _get_redis()
    redis_key = f"otp:{transaction_id}:{customer_id}"
    if r is not None:
        r.setex(redis_key, settings.OTP_TTL_SECONDS, otp_hash)
        r.setex(f"{redis_key}:attempts", settings.OTP_TTL_SECONDS, "0")

    # Store in DB for audit trail
    otp_record = OTPAttempt(
        transaction_id=transaction_id,
        customer_id=customer_id,
        otp_hash=otp_hash,
        channel=channel,
        recipient=recipient,
        attempt_count=0,
    )
    db.add(otp_record)
    db.commit()

    # Send OTP via channel
    if channel == "sms":
        _send_sms_otp(recipient, otp_code)
    else:
        _send_email_otp(recipient, otp_code)

    result: dict[str, Any] = {
        "channel": channel,
        "recipient": _mask_recipient(recipient, channel),
        "expires_in": settings.OTP_TTL_SECONDS,
        "message": f"OTP sent via {channel}",
    }

    # Include OTP in development mode (no real SMS/email configured)
    if not settings.TWILIO_ACCOUNT_SID and not settings.SENDGRID_API_KEY:
        result["otp_dev"] = otp_code

    return result


def verify_otp(
    db: Session,
    transaction_id: str,
    customer_id: str,
    otp_code: str,
) -> dict[str, Any]:
    """Verify a submitted OTP.

    Returns:
        Dict with verified (bool), action (approve/block/retry), attempts_remaining
    """
    otp_hash = _hash_otp(otp_code)
    redis_key = f"otp:{transaction_id}:{customer_id}"

    r = _get_redis()

    # Check Redis first (faster)
    if r is not None:
        stored_hash = r.get(redis_key)
        attempts_str = r.get(f"{redis_key}:attempts") or "0"
        attempts = int(attempts_str)

        if stored_hash is None:
            return {
                "verified": False,
                "action": "expired",
                "message": "OTP expired or not found",
                "attempts_remaining": 0,
            }

        if attempts >= settings.OTP_MAX_ATTEMPTS:
            # Block and escalate
            r.delete(redis_key, f"{redis_key}:attempts")
            _update_otp_record(db, transaction_id, customer_id, attempts + 1, expired=True)
            return {
                "verified": False,
                "action": "block",
                "message": "Maximum OTP attempts exceeded. Transaction blocked and escalated.",
                "attempts_remaining": 0,
            }

        if otp_hash == stored_hash:
            # Success
            r.delete(redis_key, f"{redis_key}:attempts")
            _update_otp_record(db, transaction_id, customer_id, attempts + 1, verified=True)
            return {
                "verified": True,
                "action": "approve",
                "message": "OTP verified. Transaction approved.",
                "attempts_remaining": settings.OTP_MAX_ATTEMPTS - attempts - 1,
            }
        else:
            # Wrong OTP
            new_attempts = attempts + 1
            r.setex(f"{redis_key}:attempts", settings.OTP_TTL_SECONDS, str(new_attempts))
            _update_otp_record(db, transaction_id, customer_id, new_attempts)
            remaining = settings.OTP_MAX_ATTEMPTS - new_attempts

            if remaining <= 0:
                r.delete(redis_key, f"{redis_key}:attempts")
                return {
                    "verified": False,
                    "action": "block",
                    "message": "Maximum OTP attempts exceeded. Transaction blocked.",
                    "attempts_remaining": 0,
                }

            return {
                "verified": False,
                "action": "retry",
                "message": f"Invalid OTP. {remaining} attempts remaining.",
                "attempts_remaining": remaining,
            }

    # Fallback to DB-only verification
    record = (
        db.query(OTPAttempt)
        .filter(
            OTPAttempt.transaction_id == transaction_id,
            OTPAttempt.customer_id == customer_id,
            OTPAttempt.expired == False,
            OTPAttempt.verified == False,
        )
        .order_by(OTPAttempt.created_at.desc())
        .first()
    )

    if not record:
        return {"verified": False, "action": "expired", "message": "OTP not found"}

    record.attempt_count += 1

    if record.attempt_count > settings.OTP_MAX_ATTEMPTS:
        record.expired = True
        db.commit()
        return {"verified": False, "action": "block", "message": "Max attempts exceeded"}

    if record.otp_hash == otp_hash:
        record.verified = True
        record.verified_at = datetime.utcnow()
        db.commit()
        return {"verified": True, "action": "approve", "message": "OTP verified"}

    db.commit()
    return {
        "verified": False,
        "action": "retry",
        "attempts_remaining": settings.OTP_MAX_ATTEMPTS - record.attempt_count,
    }


def _update_otp_record(
    db: Session,
    transaction_id: str,
    customer_id: str,
    attempts: int,
    verified: bool = False,
    expired: bool = False,
) -> None:
    record = (
        db.query(OTPAttempt)
        .filter(
            OTPAttempt.transaction_id == transaction_id,
            OTPAttempt.customer_id == customer_id,
        )
        .order_by(OTPAttempt.created_at.desc())
        .first()
    )
    if record:
        record.attempt_count = attempts
        record.verified = verified
        record.expired = expired
        if verified:
            record.verified_at = datetime.utcnow()
        db.commit()


def _mask_recipient(recipient: str, channel: str) -> str:
    if channel == "sms" and len(recipient) > 4:
        return f"***{recipient[-4:]}"
    if channel == "email" and "@" in recipient:
        parts = recipient.split("@")
        return f"{parts[0][:2]}***@{parts[1]}"
    return "***"


def _send_sms_otp(phone: str, otp: str) -> bool:
    """Send OTP via Twilio SMS."""
    if not settings.TWILIO_ACCOUNT_SID:
        logger.info("[DEV] SMS OTP to %s: %s", phone, otp)
        return True
    try:
        from twilio.rest import Client
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        client.messages.create(
            body=f"Your fraud verification OTP is: {otp}. Valid for {settings.OTP_TTL_SECONDS // 60} minutes.",
            from_=settings.TWILIO_PHONE_NUMBER,
            to=phone,
        )
        return True
    except Exception as exc:
        logger.error("Twilio SMS failed: %s", exc)
        return False


def _send_email_otp(email: str, otp: str) -> bool:
    """Send OTP via SendGrid email."""
    if not settings.SENDGRID_API_KEY:
        logger.info("[DEV] Email OTP to %s: %s", email, otp)
        return True
    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail

        sg = sendgrid.SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
        message = Mail(
            from_email=settings.SENDGRID_FROM_EMAIL,
            to_emails=email,
            subject="Transaction Verification Code",
            plain_text_content=(
                f"Your verification code is: {otp}\n"
                f"This code expires in {settings.OTP_TTL_SECONDS // 60} minutes.\n"
                f"If you did not initiate this transaction, please contact support immediately."
            ),
        )
        sg.send(message)
        return True
    except Exception as exc:
        logger.error("SendGrid email failed: %s", exc)
        return False
