"""
Rule Engine — deterministic rules that fire instantly.
Returns cumulative risk contribution from all triggered rules.
Designed to catch obvious fraud patterns before ML models run.
"""

from typing import Any

# Each rule is (id, name, condition_fn, score_contribution)
RULES: list[tuple[str, str, Any, float]] = [
    (
        "R001",
        "high_amount",
        lambda txn, feat: txn.get("amount", 0) > 50000,
        0.25,
    ),
    (
        "R002",
        "velocity_1h",
        lambda txn, feat: feat.get("txn_count_1h", 0) > 15,
        0.25,
    ),
    (
        "R003",
        "new_device",
        lambda txn, feat: feat.get("is_new_device", 0) == 1,
        0.20,
    ),
    (
        "R004",
        "geo_impossible_travel",
        lambda txn, feat: (
            feat.get("distance_from_prev_km", 0) > 500
            or (
                feat.get("city_changed", 0) == 1
                and feat.get("time_since_last_h", 99) < 2
            )
        ),
        0.85,
    ),
    (
        "R005",
        "odd_hour",
        lambda txn, feat: (
            feat.get("is_night", feat.get("is_odd_hour", 0)) == 1
        )
        and txn.get("amount", 0) > 10000,
        0.35,
    ),
    (
        "R006",
        "amount_deviation",
        lambda txn, feat: (
            feat.get("amount_deviation", feat.get("amount_to_avg_ratio", 0)) > 7.0
        ),
        0.30,
    ),
    (
        "R007",
        "aml_structuring",
        lambda txn, feat: 45000 <= txn.get("amount", 0) < 50000 and feat.get("txn_count_24h", 0) >= 2,
        0.35,
    ),
    # New Bank-Grade Rules
    (
        "R008",
        "sim_swap_risk",
        lambda txn, feat: (
            (feat.get("device_change_24h", 0) == 1 or feat.get("is_new_device", 0) == 1)
            and txn.get("amount", 0) > 10000
            and str(txn.get("merchant_category", "")).lower() in ["banking", "wallet"]
        ),
        0.35,
    ),
    (
        "R009",
        "mule_account_pattern",
        lambda txn, feat: (
            feat.get("unique_sources_1h", 0) >= 3 
            and feat.get("amount_to_avg_ratio", 0) > 3.0
        ),
        0.40,
    ),
    (
        "R010",
        "account_takeover",
        lambda txn, feat: (
            feat.get("is_new_device", 0) == 1
            and feat.get("password_reset_2h", 0) == 1
            and txn.get("amount", 0) > 20000
        ),
        0.45,
    ),
    (
        "R011",
        "round_amount_structuring",
        lambda txn, feat: (
            txn.get("amount", 0) > 5000 
            and txn.get("amount", 0) % 1000 == 0
            and feat.get("is_new_device", 0) == 1
            and str(txn.get("merchant_category", "")).lower() in ["crypto", "wire", "international"]
        ),
        0.20,
    )
]


class RuleEngine:
    """
    Evaluates a fixed set of deterministic rules against
    a transaction + its feature vector.
    """

    def __init__(self) -> None:
        self.rules = RULES

    def evaluate(self, txn: dict, features: dict) -> tuple[float, list[dict]]:
        """
        Returns
        -------
        score : float  — cumulative rule score (clamped to 1.0)
        triggered : list[dict]  — list of fired rule dicts
        """
        total_score = 0.0
        triggered_rules = []

        for rule in self.rules:
            rule_id, rule_name, logic_fn, impact = rule
            try:
                if logic_fn(txn, features):
                    triggered_rules.append(
                        {
                            "rule_id": rule_id,
                            "rule_name": rule_name,
                            "score": impact, # Impact for breakdown
                        }
                    )
                    total_score += impact
            except Exception:
                # Log error if needed, but keep engine running
                continue

        # Score implies certainty of fraud (0 to 1.0)
        # Multiple rules firing increases certainty
        return min(total_score, 1.0), triggered_rules
