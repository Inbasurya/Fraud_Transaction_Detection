"""Fraud explanation service.

Returns human-readable explanations for why a transaction was flagged,
including feature contributions (SHAP-style when available, deterministic
fallback otherwise).
"""
from __future__ import annotations

import logging
from typing import Any

from app.core.explainer import generate_explanation

logger = logging.getLogger(__name__)


def explain_prediction(
    tx_dict: dict[str, Any],
    features: dict[str, Any],
    risk_score: float,
    risk_category: str,
    fraud_probability: float,
    behavior_score: float,
    rule_score: float,
    reasons: list[str],
    shap_details: dict[str, Any] | None = None,
) -> dict:
    """Build a full explanation payload for the dashboard."""

    # ── Feature contributions (deterministic SHAP-like) ──────
    contributions = _compute_contributions(tx_dict, features)

    # ── Part 2: Human-Readable Explanations ──────
    shap_values = (shap_details or {}).get("shap_values", {})
    if not shap_values:
        # Fallback if no SHAP available, use deterministic contributions as surrogate
        shap_values = {c["feature"]: c["impact"] for c in contributions}

    explanation_audit = generate_explanation(shap_values, features)

    return {
        "risk_score": round(risk_score, 4),
        "status": risk_category,
        "fraud_probability": round(fraud_probability, 4),
        "behavior_score": round(behavior_score, 4),
        "rule_score": round(rule_score, 4),
        "reasons": reasons if reasons else ["No anomalies detected"],
        "feature_contributions": contributions,
        "shap_values": shap_values,
        "shap_details": shap_details or {},
        
        # New RBI Compliance fields
        "explanation": explanation_audit.get("summary", ""),
        "top_features": explanation_audit.get("top_reasons", []),
    }


def explain_transaction_by_record(tx, prediction, features: dict) -> dict:
    """Explain a stored transaction from DB records."""
    reasons = []
    if prediction and prediction.risk_category in ("FRAUD", "SUSPICIOUS"):
        reasons = _infer_reasons(features)

    return explain_prediction(
        tx_dict={
            "amount": tx.amount,
            "merchant": tx.merchant,
            "location": tx.location,
            "device_type": tx.device_type,
            "timestamp": tx.timestamp,
        },
        features=features,
        risk_score=prediction.risk_score if prediction else 0,
        risk_category=prediction.risk_category if prediction else "SAFE",
        fraud_probability=prediction.fraud_probability if prediction else 0,
        behavior_score=0,
        rule_score=0,
        reasons=reasons,
        shap_details=None,
    )


# ── Internal helpers ─────────────────────────────────────────────

def _compute_contributions(tx: dict, features: dict) -> list[dict]:
    """Deterministic feature-contribution estimation."""
    contribs = []
    amount = float(tx.get("amount", 0))
    avg = float(features.get("user_avg_amount", features.get("avg_user_spend", 0)))

    ratio = float(features.get("transaction_amount_over_user_avg", 1.0))
    if avg > 0:
        impact = min(max((ratio - 1.0) * 0.12, 0.0), 0.35)
        contribs.append({"feature": "transaction_amount_over_user_avg", "impact": round(impact, 4),
                         "desc": f"${amount:,.2f} vs avg ${avg:,.2f}"})

    hour = features.get("transaction_hour", 12)
    hour_impact = 0.18 if 0 <= hour <= 5 else -0.03
    contribs.append({"feature": "unusual_time_flag", "impact": round(hour_impact, 4),
                     "desc": f"Transaction hour: {hour}"})

    loc_change = features.get("location_change_flag", features.get("location_change", 0))
    contribs.append({"feature": "location_change_flag", "impact": round(0.18 * loc_change, 4),
                     "desc": "Location changed" if loc_change else "Same location"})

    dev_change = features.get("device_change_flag", features.get("device_change", 0))
    contribs.append({"feature": "device_change_flag", "impact": round(0.15 * dev_change, 4),
                     "desc": "New device" if dev_change else "Known device"})

    tx_24h = float(features.get("transaction_frequency_last_24h", features.get("velocity", 0)))
    vel_impact = min(tx_24h * 0.04, 0.22)
    contribs.append({"feature": "transaction_frequency_last_24h", "impact": round(vel_impact, 4),
                     "desc": f"{tx_24h:.0f} tx in the last 24h"})

    deviation = features.get("amount_deviation", 0)
    dev_impact = min(abs(deviation) * 0.04, 0.15) * (1 if deviation > 0 else -1)
    contribs.append({"feature": "amount_deviation", "impact": round(dev_impact, 4),
                     "desc": f"Z-score: {deviation:.2f}"})

    merchant_risk = float(features.get("merchant_risk_score", 0))
    contribs.append({"feature": "merchant_risk_score", "impact": round(min(merchant_risk * 0.8, 0.2), 4),
                     "desc": f"Merchant risk prior: {merchant_risk:.3f}"})

    contribs.sort(key=lambda c: abs(c["impact"]), reverse=True)
    return contribs


def _infer_reasons(features: dict) -> list[str]:
    """Generate human-readable reasons from features."""
    reasons = []
    if features.get("unusual_amount_flag"):
        reasons.append("Amount anomaly")
    if features.get("device_change_flag", features.get("device_change")):
        reasons.append("Device anomaly")
    if features.get("location_change_flag", features.get("location_change")):
        reasons.append("Location anomaly")
    if features.get("unusual_time_flag"):
        reasons.append(f"Unusual transaction hour ({features.get('transaction_hour')})")
    if features.get("transaction_frequency_last_24h", features.get("velocity", 0)) > 5:
        reasons.append(f"High transaction velocity ({features.get('transaction_frequency_last_24h', features.get('velocity'))}/24h)")
    if abs(features.get("amount_deviation", 0)) > 3:
        reasons.append("Extreme amount deviation from pattern")
    if features.get("merchant_risk_score", 0) > 0.1:
        reasons.append("Merchant has elevated fraud risk")
    return reasons or ["Model flagged as anomalous"]
