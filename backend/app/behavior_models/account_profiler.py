"""Per-account behavioral profiling utilities."""

from __future__ import annotations

from collections import Counter
from typing import Any

from sqlalchemy.orm import Session

from app.models.transaction_model import Transaction
from app.behavior_models import behavior_model


def _history(db: Session, user_id: int, limit: int = 120) -> list[Transaction]:
    return (
        db.query(Transaction)
        .filter(Transaction.user_id == user_id)
        .order_by(Transaction.timestamp.desc())
        .limit(limit)
        .all()
    )


def profile_account(db: Session, user_id: int) -> dict[str, Any]:
    rows = _history(db, user_id)
    if not rows:
        return {
            "average_transaction": 0.0,
            "transaction_frequency": 0.0,
            "device_usage_pattern": {},
            "location_changes": 0.0,
            "merchant_category_frequency": {},
        }

    amounts = [float(r.amount or 0) for r in rows]
    devices = [str(r.device_type or "Unknown") for r in rows]
    locations = [str(r.location or "Unknown") for r in rows]
    merchants = [str(r.merchant or "Unknown") for r in rows]

    location_switches = sum(1 for i in range(1, len(locations)) if locations[i] != locations[i - 1])
    device_dist = Counter(devices)
    merchant_dist = Counter(merchants)
    total = max(len(rows), 1)

    return {
        "average_transaction": round(sum(amounts) / total, 2),
        "transaction_frequency": round(total / 7.0, 4),  # tx/day approx over recent window
        "device_usage_pattern": {k: round(v / total, 4) for k, v in device_dist.items()},
        "location_changes": round(location_switches / total, 4),
        "merchant_category_frequency": {k: round(v / total, 4) for k, v in merchant_dist.items()},
    }


def score_behavior(db: Session, tx: Transaction, features: dict[str, Any]) -> dict[str, Any]:
    profile = profile_account(db, tx.user_id)
    score_bundle = behavior_model.score(
        amount=float(tx.amount or 0.0),
        transaction_amount_ratio=float(features.get("transaction_amount_ratio", features.get("transaction_amount_over_user_avg", 1.0))),
        transaction_frequency_last_24h=float(max(features.get("transaction_frequency_last_24h", features.get("velocity", 0)), 0.0)),
        location_change_flag=float(features.get("location_change_flag", features.get("location_change", 0.0))),
        device_change_flag=float(features.get("device_change_flag", features.get("device_change", 0.0))),
        merchant_risk_score=float(features.get("merchant_risk_score", 0.0)),
        time_since_last_transaction=float(features.get("time_since_last_transaction", features.get("time_delta_minutes", 24 * 60.0))),
        unusual_time_activity=float(features.get("unusual_time_activity", features.get("unusual_time_flag", 0.0))),
        account_transaction_velocity=float(features.get("account_transaction_velocity", features.get("velocity", 0.0))),
        merchant_frequency=float(features.get("merchant_frequency", 0.0)),
    )
    return {
        "behavior_score": float(score_bundle["ensemble_score"]),
        "anomaly_models": score_bundle,
        "profile": profile,
    }
