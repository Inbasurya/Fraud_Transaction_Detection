"""Production-grade bank-style fraud rule engine.

Rules (from specification):
  1. IF amount > 5x avg_transaction_amount  → risk += 0.2
  2. IF device_change_flag                  → risk += 0.15
  3. IF unusual_time_flag                   → risk += 0.1
  4. IF transaction_velocity > threshold    → risk += 0.2
  5. IF geo_distance > 2000 km within 10 min → risk += 0.3

Additional production rules:
  6. New device never seen before           → risk += 0.15
  7. High absolute amount (> $10 000)       → risk += 0.1
  8. Amount deviation z-score > 3σ          → risk += 0.12
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RuleResult:
    rule_score: float
    triggered_rules: list[str] = field(default_factory=list)


def evaluate_fraud_rules(features: dict, tx=None) -> RuleResult:
    """Evaluate all fraud rules against computed features.

    Args:
        features: dict of engineered features (from feature_engineering or core/features).
        tx: optional transaction object for direct attribute access.

    Returns:
        RuleResult with aggregated score (capped at 1.0) and list of triggered rule descriptions.
    """
    score = 0.0
    reasons: list[str] = []

    amount = features.get("amount", 0.0)
    if tx is not None:
        amount = float(getattr(tx, "amount", amount) or amount)

    avg_amount = features.get("avg_user_spend", 0) or features.get("amount_over_customer_avg", 0)

    # ── Rule 1: Amount > 5× average ──────────────────────────
    ratio = features.get("transaction_amount_ratio", 0) or features.get("amount_over_customer_avg", 0)
    if ratio > 5.0:
        score += 0.20
        reasons.append(f"Amount {ratio:.1f}× exceeds 5× customer average")
    elif ratio > 3.0:
        score += 0.10
        reasons.append(f"Amount {ratio:.1f}× exceeds 3× customer average")

    # ── Rule 2: Device change ─────────────────────────────────
    if features.get("device_change_flag", 0) or features.get("device_change", 0):
        score += 0.15
        reasons.append("Device changed from previous transaction")

    # ── Rule 3: Unusual time (midnight–5 AM) ──────────────────
    if features.get("unusual_time_flag", 0):
        hour = features.get("transaction_hour", "?")
        score += 0.10
        reasons.append(f"Transaction at unusual hour ({hour}:00)")

    # ── Rule 4: High transaction velocity ─────────────────────
    velocity = features.get("transaction_velocity", 0) or features.get("velocity", 0)
    if velocity > 8:
        score += 0.20
        reasons.append(f"Critical velocity: {velocity} transactions in last hour")
    elif velocity > 5:
        score += 0.15
        reasons.append(f"High velocity: {velocity} transactions in last hour")

    # ── Rule 5: Impossible travel (> 2000 km within 10 min) ──
    geo_distance = features.get("geo_distance", 0)
    time_since = features.get("time_since_last_transaction", 9999)
    if geo_distance > 2000 and time_since < 10:
        score += 0.30
        reasons.append(
            f"Impossible travel: {geo_distance:.0f} km in {time_since:.1f} min"
        )
    elif features.get("impossible_travel", 0):
        score += 0.30
        reasons.append("Impossible travel detected")

    # ── Rule 6: New device never seen ─────────────────────────
    if features.get("new_device_flag", 0):
        score += 0.15
        reasons.append("Transaction from previously unseen device")

    # ── Rule 7: High absolute amount ─────────────────────────
    if amount > 10_000:
        score += 0.10
        reasons.append(f"High absolute amount: ${amount:,.2f}")

    # ── Rule 8: Statistical deviation ─────────────────────────
    deviation = features.get("amount_deviation", 0)
    if abs(deviation) > 3:
        score += 0.12
        reasons.append(f"Amount deviation z-score {deviation:.2f} (>3σ)")

    # ── Rule 9: Location change ───────────────────────────────
    if features.get("location_change_flag", 0) or features.get("location_change", 0):
        score += 0.15
        reasons.append("Location changed from previous transaction")

    final_score = min(score, 1.0)
    logger.debug("Rule engine: score=%.4f, triggered=%d rules", final_score, len(reasons))

    return RuleResult(rule_score=round(final_score, 4), triggered_rules=reasons)
