"""Feature engineering engine for real-time transaction analysis."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.transaction_model import Transaction


def _recent_user_transactions(db: Session, user_id: int, limit: int = 200) -> list[Transaction]:
    return (
        db.query(Transaction)
        .filter(Transaction.user_id == user_id)
        .order_by(Transaction.timestamp.desc())
        .limit(limit)
        .all()
    )


def _safe_timestamp(value) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def build_features(db: Session, tx: Transaction) -> dict:
    """Compute engineered features for a single transaction."""

    history = _recent_user_transactions(db, tx.user_id, limit=200)
    history = [row for row in history if row.id != tx.id]
    history.sort(key=lambda row: row.timestamp)

    ts = _safe_timestamp(tx.timestamp)
    last_tx = history[-1] if history else None
    amounts = [float(row.amount or 0.0) for row in history]

    user_avg_amount = (sum(amounts) / len(amounts)) if amounts else float(tx.amount or 0.0)
    user_avg_amount = max(user_avg_amount, 1.0)

    if len(amounts) >= 2:
        mean_amount = sum(amounts) / len(amounts)
        std_amount = (sum((amount - mean_amount) ** 2 for amount in amounts) / len(amounts)) ** 0.5
        amount_deviation = (float(tx.amount or 0.0) - mean_amount) / max(std_amount, 1.0)
    else:
        amount_deviation = 0.0

    trailing_24h = ts - timedelta(hours=24)
    transaction_frequency_last_24h = sum(
        1 for row in history if row.timestamp and row.timestamp >= trailing_24h
    )
    account_transaction_velocity = sum(
        1
        for row in history
        if row.timestamp and (ts - row.timestamp).total_seconds() <= 3600
    )

    location_change_flag = 1.0 if last_tx and last_tx.location != tx.location else 0.0
    device_change_flag = 1.0 if last_tx and last_tx.device_type != tx.device_type else 0.0

    if last_tx and last_tx.timestamp:
        time_since_last_transaction = max((ts - last_tx.timestamp).total_seconds() / 60.0, 0.0)
    else:
        time_since_last_transaction = 24 * 60.0

    unusual_time_flag = 1.0 if 0 <= ts.hour <= 5 else 0.0
    unusual_time_activity = unusual_time_flag
    transaction_amount_ratio = float(tx.amount or 0.0) / user_avg_amount

    if history and tx.merchant:
        merchant_hits = sum(1 for row in history if row.merchant == tx.merchant)
        merchant_frequency = merchant_hits / max(len(history), 1)
    else:
        merchant_frequency = 0.0

    from app.ml_models.kaggle_fraud_model import kaggle_model

    merchant_risk_score = kaggle_model.merchant_risk_score(tx.merchant)

    last_24h_locations = [str(row.location or "UNKNOWN") for row in history if row.timestamp and row.timestamp >= trailing_24h]
    last_24h_devices = [str(row.device_type or "UNKNOWN") for row in history if row.timestamp and row.timestamp >= trailing_24h]
    dominant_location = Counter(last_24h_locations).most_common(1)[0][0] if last_24h_locations else str(tx.location or "UNKNOWN")
    dominant_device = Counter(last_24h_devices).most_common(1)[0][0] if last_24h_devices else str(tx.device_type or "UNKNOWN")
    location_stability_score = 1.0 if str(tx.location or "UNKNOWN") == dominant_location else 0.0
    device_stability_score = 1.0 if str(tx.device_type or "UNKNOWN") == dominant_device else 0.0

    unusual_amount_flag = 1.0 if transaction_amount_ratio >= 3.0 else 0.0

    return {
        "amount": round(float(tx.amount or 0.0), 4),
        "transaction_hour": float(ts.hour),
        "time_of_transaction": float(ts.hour),
        "avg_user_spend": round(user_avg_amount, 4),
        "user_avg_amount": round(user_avg_amount, 4),
        "transaction_amount_ratio": round(transaction_amount_ratio, 4),
        "transaction_amount_over_user_avg": round(transaction_amount_ratio, 4),
        "transaction_frequency_last_24h": float(transaction_frequency_last_24h),
        "location_change_flag": location_change_flag,
        "device_change_flag": device_change_flag,
        "merchant_risk_score": round(float(merchant_risk_score), 4),
        "time_since_last_transaction": round(time_since_last_transaction, 3),
        "unusual_time_activity": unusual_time_activity,
        "unusual_time_flag": unusual_time_flag,
        "account_transaction_velocity": float(account_transaction_velocity),
        "merchant_frequency": round(float(merchant_frequency), 4),
        "amount_deviation": round(float(amount_deviation), 4),
        "velocity": float(account_transaction_velocity),
        "location_stability_score": float(location_stability_score),
        "device_stability_score": float(device_stability_score),
        "location_change": location_change_flag,
        "device_change": device_change_flag,
        "time_delta_minutes": round(time_since_last_transaction, 3),
        "unusual_amount_flag": unusual_amount_flag,
    }
