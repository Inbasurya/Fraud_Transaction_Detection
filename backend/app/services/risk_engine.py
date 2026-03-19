"""Hybrid risk scoring engine.

Combines all fraud detection signals into a unified risk score:
  risk_score = 0.40 × ML_probability
             + 0.25 × anomaly_score
             + 0.20 × graph_risk_score
             + 0.15 × rule_engine_score

Classification:
  risk < 0.3  → SAFE
  0.3 – 0.6   → SUSPICIOUS
  > 0.6       → FRAUD
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Weights per the specification
WEIGHT_ML = 0.40
WEIGHT_ANOMALY = 0.25
WEIGHT_GRAPH = 0.20
WEIGHT_RULES = 0.15


@dataclass
class RiskAssessment:
    risk_score: float
    risk_category: str
    ml_probability: float
    anomaly_score: float
    graph_risk_score: float
    rule_score: float
    reasons: list[str] = field(default_factory=list)
    weights: dict = field(default_factory=dict)


def compute_hybrid_risk(
    ml_probability: float,
    anomaly_score: float,
    graph_risk_score: float,
    rule_score: float,
    rule_reasons: list[str] | None = None,
) -> RiskAssessment:
    """Compute the hybrid risk score from all signals.

    Returns a RiskAssessment with the final score, category, and breakdown.
    """
    risk_score = (
        WEIGHT_ML * ml_probability
        + WEIGHT_ANOMALY * anomaly_score
        + WEIGHT_GRAPH * graph_risk_score
        + WEIGHT_RULES * rule_score
    )
    risk_score = round(min(max(risk_score, 0.0), 1.0), 4)

    if risk_score < 0.30:
        category = "SAFE"
    elif risk_score < 0.50:
        category = "SUSPICIOUS"
    elif risk_score < 0.70:
        category = "REVIEW"
    elif risk_score < 0.85:
        category = "HIGH_RISK"
    else:
        category = "FRAUD"

    reasons = list(rule_reasons or [])
    if ml_probability > 0.6:
        reasons.append(f"ML model flagged high fraud probability ({ml_probability:.2f})")
    if anomaly_score > 0.5:
        reasons.append(f"Behavioral anomaly detected (score {anomaly_score:.2f})")
    if graph_risk_score > 0.3:
        reasons.append(f"Graph analysis indicates risk (score {graph_risk_score:.2f})")

    logger.debug(
        "Hybrid risk: %.4f (%s) — ML=%.3f, Anomaly=%.3f, Graph=%.3f, Rules=%.3f",
        risk_score, category, ml_probability, anomaly_score, graph_risk_score, rule_score,
    )

    return RiskAssessment(
        risk_score=risk_score,
        risk_category=category,
        ml_probability=round(ml_probability, 4),
        anomaly_score=round(anomaly_score, 4),
        graph_risk_score=round(graph_risk_score, 4),
        rule_score=round(rule_score, 4),
        reasons=reasons,
        weights={
            "ml": WEIGHT_ML,
            "anomaly": WEIGHT_ANOMALY,
            "graph": WEIGHT_GRAPH,
            "rules": WEIGHT_RULES,
        },
    )


# ── Legacy compatibility ─────────────────────────────────────

def calculate_risk_score(probability: float) -> float:
    return probability * 100


def categorize_risk(score: float) -> str:
    if score < 30:
        return "low"
    elif score < 70:
        return "medium"
    else:
        return "high"

