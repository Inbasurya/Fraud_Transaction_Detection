"""Fraud pattern detector — identifies suspicious behavioral patterns.

Patterns detected:
  - Rapid transactions (velocity spike within time window)
  - Location hopping (multiple locations in short time)
  - Device switching (multiple devices in short time)
  - Abnormal amount spike (sudden large transaction)
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.models.transaction_model import Transaction
from app.models.fraud_prediction_model import FraudPrediction

logger = logging.getLogger(__name__)


def detect_rapid_transactions(
    db: Session, window_minutes: int = 60, threshold: int = 5
) -> list[dict[str, Any]]:
    """Find users with more than `threshold` transactions in the last `window_minutes`."""
    cutoff = datetime.utcnow() - timedelta(minutes=window_minutes)
    rows = (
        db.query(
            Transaction.user_id,
            func.count(Transaction.id).label("tx_count"),
            func.max(Transaction.amount).label("max_amount"),
        )
        .filter(Transaction.timestamp >= cutoff)
        .group_by(Transaction.user_id)
        .having(func.count(Transaction.id) > threshold)
        .order_by(desc("tx_count"))
        .all()
    )
    return [
        {
            "user_id": r[0],
            "tx_count": r[1],
            "max_amount": round(float(r[2] or 0), 2),
            "pattern": "rapid_transactions",
            "severity": "HIGH" if r[1] > threshold * 2 else "MEDIUM",
        }
        for r in rows
    ]


def detect_location_hopping(
    db: Session, window_minutes: int = 120, threshold: int = 3
) -> list[dict[str, Any]]:
    """Find users transacting from many distinct locations in a short window."""
    cutoff = datetime.utcnow() - timedelta(minutes=window_minutes)
    rows = (
        db.query(
            Transaction.user_id,
            func.count(func.distinct(Transaction.location)).label("loc_count"),
        )
        .filter(Transaction.timestamp >= cutoff)
        .group_by(Transaction.user_id)
        .having(func.count(func.distinct(Transaction.location)) >= threshold)
        .order_by(desc("loc_count"))
        .all()
    )
    results = []
    for r in rows:
        locs = (
            db.query(Transaction.location)
            .filter(Transaction.user_id == r[0], Transaction.timestamp >= cutoff)
            .distinct()
            .all()
        )
        results.append({
            "user_id": r[0],
            "location_count": r[1],
            "locations": [l[0] for l in locs if l[0]],
            "pattern": "location_hopping",
            "severity": "HIGH" if r[1] >= threshold * 2 else "MEDIUM",
        })
    return results


def detect_device_switching(
    db: Session, window_minutes: int = 120, threshold: int = 3
) -> list[dict[str, Any]]:
    """Find users switching between multiple devices rapidly."""
    cutoff = datetime.utcnow() - timedelta(minutes=window_minutes)
    rows = (
        db.query(
            Transaction.user_id,
            func.count(func.distinct(Transaction.device_type)).label("dev_count"),
        )
        .filter(Transaction.timestamp >= cutoff)
        .group_by(Transaction.user_id)
        .having(func.count(func.distinct(Transaction.device_type)) >= threshold)
        .order_by(desc("dev_count"))
        .all()
    )
    results = []
    for r in rows:
        devs = (
            db.query(Transaction.device_type)
            .filter(Transaction.user_id == r[0], Transaction.timestamp >= cutoff)
            .distinct()
            .all()
        )
        results.append({
            "user_id": r[0],
            "device_count": r[1],
            "devices": [d[0] for d in devs if d[0]],
            "pattern": "device_switching",
            "severity": "HIGH" if r[1] >= 4 else "MEDIUM",
        })
    return results


def detect_amount_spikes(
    db: Session, multiplier: float = 5.0
) -> list[dict[str, Any]]:
    """Find recent transactions where amount exceeds `multiplier` × user average."""
    subq = (
        db.query(
            Transaction.user_id,
            func.avg(Transaction.amount).label("avg_amount"),
        )
        .group_by(Transaction.user_id)
        .subquery()
    )

    rows = (
        db.query(
            Transaction.user_id,
            Transaction.transaction_id,
            Transaction.amount,
            subq.c.avg_amount,
        )
        .join(subq, Transaction.user_id == subq.c.user_id)
        .filter(Transaction.amount > subq.c.avg_amount * multiplier)
        .order_by(desc(Transaction.timestamp))
        .limit(50)
        .all()
    )
    return [
        {
            "user_id": r[0],
            "transaction_id": r[1],
            "amount": round(float(r[2]), 2),
            "avg_amount": round(float(r[3] or 0), 2),
            "spike_ratio": round(float(r[2]) / max(float(r[3] or 1), 1), 1),
            "pattern": "amount_spike",
            "severity": "CRITICAL" if float(r[2]) / max(float(r[3] or 1), 1) > 10 else "HIGH",
        }
        for r in rows
    ]


def detect_all_patterns(db: Session) -> dict[str, Any]:
    """Run all pattern detectors and return combined results."""
    rapid = detect_rapid_transactions(db)
    location = detect_location_hopping(db)
    device = detect_device_switching(db)
    spikes = detect_amount_spikes(db)

    all_patterns = rapid + location + device + spikes
    all_patterns.sort(
        key=lambda p: {"CRITICAL": 3, "HIGH": 2, "MEDIUM": 1}.get(p.get("severity", ""), 0),
        reverse=True,
    )

    return {
        "total_patterns": len(all_patterns),
        "rapid_transactions": len(rapid),
        "location_hopping": len(location),
        "device_switching": len(device),
        "amount_spikes": len(spikes),
        "patterns": all_patterns,
    }
