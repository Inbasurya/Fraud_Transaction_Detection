"""Bank-style rule engine for fraud detection."""


def compute_rule_score(tx, features: dict) -> tuple[float, list[str]]:
    """Return (rule_score 0-1, list of triggered reasons)."""
    score = 0.0
    reasons = []

    # Rule 1: amount > 5x average user spend
    avg = features.get("avg_user_spend", 0)
    if avg > 0 and tx.amount > avg * 5:
        score += 0.2
        reasons.append(f"Amount ${tx.amount:.2f} exceeds 5x avg spend ${avg:.2f}")

    # Rule 2: location changed from last transaction
    if features.get("location_change"):
        score += 0.2
        reasons.append("Location changed from previous transaction")

    # Rule 3: new / different device
    if features.get("device_change"):
        score += 0.2
        reasons.append("Device changed from previous transaction")

    # Rule 4: unusual time (1 AM – 4 AM)
    if features.get("unusual_time_flag"):
        score += 0.1
        reasons.append(f"Transaction at unusual hour ({features.get('transaction_hour')})")

    # Rule 5: unusually high amount (>3x avg)
    if features.get("unusual_amount_flag"):
        score += 0.15
        reasons.append("Unusually high amount (>3x average)")

    # Rule 6: high velocity (>5 tx in last hour)
    if features.get("velocity", 0) > 5:
        score += 0.15
        reasons.append(f"High velocity: {features['velocity']} transactions in last hour")

    return min(score, 1.0), reasons
