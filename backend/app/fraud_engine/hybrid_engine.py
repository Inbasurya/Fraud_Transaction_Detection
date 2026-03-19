"""Hybrid fraud intelligence engine.

Pipeline:
Transaction stream -> Feature Engineering -> Kaggle model -> Behavior model
-> Rule Engine -> Risk Scoring -> Alerting/WebSocket
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.features import build_features
from app.behavior_models.account_profiler import score_behavior
from app.ml_models.kaggle_fraud_model import kaggle_model
from app.services.rule_engine import evaluate_rules
from app.analytics.fraud_network_service import transaction_cluster_risk

from backend.core.scoring import ScoringEngine, classify_risk
from backend.core.device_scorer import get_device_score

logger = logging.getLogger(__name__)

SAFE_THRESHOLD = 0.45
SUSPICIOUS_THRESHOLD = 0.75


def get_decision(risk_score: int) -> dict[str, str]:
    """Return action and priority based on risk score."""
    # Use centralized logic from scoring engine but map to legacy format
    action = classify_risk(float(risk_score))
    
    if action == "Block":
        return {"action": "BLOCK", "priority": "CRITICAL"}
    if action == "Review":
        return {"action": "REVIEW", "priority": "HIGH"}
    if action == "Monitor":
        return {"action": "MONITOR", "priority": "LOW"}
    return {"action": "APPROVE", "priority": "NONE"}


def _parse_hour(ts: datetime | str | None) -> int:
    if ts is None:
        return 12
    if isinstance(ts, datetime):
        return ts.hour
    try:
        return datetime.fromisoformat(str(ts)).hour
    except Exception:
        return 12


async def score_transaction(db: Session, tx: Any) -> dict[str, Any]:
    """Run hybrid scoring for a DB transaction record."""

    features = build_features(db, tx)
    hour = _parse_hour(tx.timestamp)
    model_scores = kaggle_model.predict_scores(features)
    kaggle_probability = float(model_scores["ensemble_probability"])

    rule_score, rule_reasons = await evaluate_rules(tx, features)
    behavior_bundle = score_behavior(db, tx, features)
    behavior_anomaly_score = float(behavior_bundle["behavior_score"])
    graph_cluster_risk = float(transaction_cluster_risk(db, tx))

    # Device Intelligence
    device_features = {
        "device_id": getattr(tx, "device_id", None) or getattr(tx, "device_type", "unknown"), # Fallback
        "user_id": getattr(tx, "user_id", None),
        "is_new_device": features.get("device_change_flag", 0) # Mapping flag from features
    }
    device_risk_100 = await get_device_score(device_features)
    device_risk_norm = device_risk_100 / 100.0

    # Initialize Scoring Engine (can be instantiated once, but lightweight enough here)
    engine = ScoringEngine()
    
    # Calculate Final Score
    # Inputs should be 0-1
    final_result = engine.score(
        rule_score=rule_score,
        ml_score=kaggle_probability,
        behavioral_score=behavior_anomaly_score,
        graph_score=graph_cluster_risk,
        device_score=device_risk_norm,
        triggered_rules=[{"rule": r} for r in rule_reasons]
    )
    
    risk_score = int(final_result["risk_score"])
    calibration = final_result.get("score_breakdown", {})

    decision = get_decision(risk_score)
    shap_details = kaggle_model.shap_explanation(features)
    
    # Enhanced Explainability
    primary_detector = f"XGBoost ({int(kaggle_probability * 100)}%) + Rule Engine"
    
    # Simplified top contributors for the payload
    top_contributors = {}
    if shap_details and 'top_features' in shap_details:
        top_contributors = {f['feature']: round(f['value'], 2) for f in shap_details['top_features'][:3]}

    exact_rule_hits = rule_reasons
    
    behavioral_deviation_str = f"{behavior_bundle.get('profile', {}).get('ema_spend_deviation_ratio', 0.0):.1f}x above EMA spend"

    reasons = []
    for text in [*shap_details.get("reasons", []), *rule_reasons]:
        if text and text not in reasons:
            reasons.append(text)

    return {
        "risk_score": risk_score,
        "action": decision["action"],
        "priority": decision["priority"],
        "explainability": {
            "primary_detector": primary_detector,
            "top_contributors": top_contributors,
            "exact_rule_hits": exact_rule_hits,
            "behavioral_deviation": behavioral_deviation_str,
            "confidence_score": final_result.get("confidence", 0.9),
            "device_risk": device_risk_norm
        },
        "reasons": reasons[:6],
        "kaggle_probability": float(kaggle_probability),
        "behavior_anomaly_score": float(behavior_anomaly_score),
        "graph_risk_score": float(graph_cluster_risk),
        "rule_score": float(rule_score),
        "device_risk_score": float(device_risk_norm),
        "shap": shap_details,
        "features": features,
        "behavior_profile": behavior_bundle["profile"],
        "weights": engine.weights,
    }


def model_metrics_payload() -> dict[str, Any]:
    """Aggregated model metrics for model intelligence dashboard."""
    supervised = kaggle_model.metrics_payload()
    from app.behavior_models import behavior_model
    behavior = behavior_model.metrics_payload()
    return {
        "kaggle_model": supervised,
        "supervised_model": supervised,
        "behavior_model": behavior,
        "hybrid_weights": {
            "supervised_model_probability": 0.40,
            "behavioral_anomaly_score": 0.25,
            "rule_engine_score": 0.20,
            "graph_cluster_risk": 0.10,
            "device_intelligence_score": 0.05
        },
        "supervised_ensemble_weights": supervised.get("ensemble_weights", {}),
        "training_statistics": {
            "supervised_dataset": supervised.get("dataset", {}),
            "behavioral_dataset": behavior.get("dataset", {}),
        },
        "risk_bands": {
            "SAFE": {"min": 0.0, "max": SAFE_THRESHOLD},
            "SUSPICIOUS": {"min": SAFE_THRESHOLD, "max": SUSPICIOUS_THRESHOLD},
            "FRAUD": {"min": SUSPICIOUS_THRESHOLD, "max": 1.0},
        },
    }
