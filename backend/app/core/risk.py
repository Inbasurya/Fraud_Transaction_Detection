"""Risk scoring engine — blends ML probability, anomaly score, and rule score."""


def compute_risk_score(
    fraud_probability: float,
    anomaly_score: float,
    rule_score: float,
) -> float:
    """Weighted combination: 0.5 * fraud_prob + 0.3 * anomaly + 0.2 * rules."""
    return round(
        0.5 * fraud_probability + 0.3 * anomaly_score + 0.2 * rule_score,
        4,
    )


def classify_risk(score: float) -> str:
    if score < 0.4:
        return "SAFE"
    if score < 0.7:
        return "SUSPICIOUS"
    return "FRAUD"
