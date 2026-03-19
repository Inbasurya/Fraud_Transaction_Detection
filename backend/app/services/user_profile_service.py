"""User profile tracking — updates behavioral profile after each transaction."""

from __future__ import annotations
import logging
from sqlalchemy.orm import Session
from app.models.user_profile_model import UserProfile
from app.models.transaction_model import Transaction

logger = logging.getLogger(__name__)


def update_profile(db: Session, tx: Transaction) -> UserProfile:
    """Update (or create) the user profile after a transaction."""
    profile = db.query(UserProfile).filter(UserProfile.user_id == tx.user_id).first()

    if profile is None:
        profile = UserProfile(
            user_id=tx.user_id,
            avg_transaction_amount=tx.amount,
            avg_daily_transactions=1.0,
            total_transactions=1,
            last_location=tx.location,
            last_device=tx.device_type,
            last_merchant=tx.merchant,
        )
        db.add(profile)
    else:
        n = profile.total_transactions
        # Running average
        profile.avg_transaction_amount = (
            (profile.avg_transaction_amount * n + tx.amount) / (n + 1)
        )
        profile.total_transactions = n + 1
        profile.last_location = tx.location
        profile.last_device = tx.device_type
        profile.last_merchant = tx.merchant

    db.commit()
    db.refresh(profile)
    return profile


def get_profile(db: Session, user_id: int) -> UserProfile | None:
    return db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
