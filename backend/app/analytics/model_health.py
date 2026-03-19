"""Model drift and health monitoring utilities."""

from __future__ import annotations

from typing import Any

import numpy as np
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.transaction_model import Transaction
from app.models.fraud_prediction_model import FraudPrediction


def _hist(values: np.ndarray, bins: int = 10) -> list[float]:
    if values.size == 0:
        return [0.0] * bins
    hist, _ = np.histogram(values, bins=bins)
    total = float(hist.sum()) or 1.0
    return [float(v / total) for v in hist]


def _psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    if expected.size == 0 or actual.size == 0:
        return 0.0
    e_hist, edges = np.histogram(expected, bins=bins)
    a_hist, _ = np.histogram(actual, bins=edges)
    e = np.clip(e_hist.astype(float) / max(e_hist.sum(), 1), 1e-6, None)
    a = np.clip(a_hist.astype(float) / max(a_hist.sum(), 1), 1e-6, None)
    return float(np.sum((a - e) * np.log(a / e)))


def model_health_payload(db: Session, window: int = 1000) -> dict[str, Any]:
    tx_rows = (
        db.query(Transaction.amount, Transaction.timestamp)
        .order_by(Transaction.timestamp.desc())
        .limit(window)
        .all()
    )
    pred_rows = (
        db.query(FraudPrediction.risk_score, FraudPrediction.risk_category)
        .order_by(FraudPrediction.created_at.desc())
        .limit(window)
        .all()
    )

    if not tx_rows:
        return {
            "status": "insufficient_data",
            "feature_distribution": {},
            "prediction_distribution": {},
            "accuracy_changes": {"proxy_delta": 0.0},
            "drift_detected": False,
            "alerts": [],
        }

    amounts = np.array([float(r[0] or 0.0) for r in tx_rows], dtype=float)
    hours = np.array([int(getattr(r[1], "hour", 12)) for r in tx_rows], dtype=float)

    split = max(1, len(amounts) // 2)
    baseline_amount = amounts[split:]
    current_amount = amounts[:split]
    baseline_hours = hours[split:]
    current_hours = hours[:split]

    amount_psi = _psi(baseline_amount, current_amount, bins=12)
    hour_psi = _psi(baseline_hours, current_hours, bins=6)

    categories = [r[1] or "SAFE" for r in pred_rows]
    total_preds = max(len(categories), 1)
    prediction_distribution = {
        "SAFE": round(categories.count("SAFE") / total_preds, 4),
        "SUSPICIOUS": round(categories.count("SUSPICIOUS") / total_preds, 4),
        "FRAUD": round(categories.count("FRAUD") / total_preds, 4),
    }

    # Proxy for accuracy drift where labels are unavailable in online stream.
    recent_high_risk = prediction_distribution["FRAUD"] + prediction_distribution["SUSPICIOUS"]
    baseline_high_risk = 0.08
    proxy_delta = round(float(recent_high_risk - baseline_high_risk), 4)

    recent_fraud_rate = prediction_distribution["FRAUD"]
    baseline_fraud_rate = 0.02
    fraud_rate_change = round(float(recent_fraud_rate - baseline_fraud_rate), 4)

    drift_detected = amount_psi > 0.2 or hour_psi > 0.15 or abs(proxy_delta) > 0.12 or abs(fraud_rate_change) > 0.08
    alerts = []
    if amount_psi > 0.2:
        alerts.append("Amount feature distribution drift detected")
    if hour_psi > 0.15:
        alerts.append("Transaction-hour distribution drift detected")
    if abs(proxy_delta) > 0.12:
        alerts.append("Prediction distribution shift detected")
    if abs(fraud_rate_change) > 0.08:
        alerts.append("Fraud rate change exceeds adaptive threshold")

    return {
        "status": "healthy" if not drift_detected else "drift_warning",
        "feature_distribution": {
            "amount_histogram_current": _hist(current_amount, bins=12),
            "amount_histogram_baseline": _hist(baseline_amount, bins=12),
            "hour_histogram_current": _hist(current_hours, bins=6),
            "hour_histogram_baseline": _hist(baseline_hours, bins=6),
            "amount_psi": round(amount_psi, 4),
            "hour_psi": round(hour_psi, 4),
        },
        "prediction_distribution": prediction_distribution,
        "accuracy_changes": {"proxy_delta": proxy_delta},
        "fraud_rate_changes": {
            "current_fraud_rate": round(recent_fraud_rate, 4),
            "baseline_fraud_rate": round(baseline_fraud_rate, 4),
            "delta": fraud_rate_change,
        },
        "drift_detected": drift_detected,
        "alerts": alerts,
    }
