"""
Natural language fraud explanation generator.
Converts ML features and SHAP values into analyst-readable alert text.
This is what a real SOC analyst sees when they open a fraud case.
"""

RULE_EXPLANATIONS = {
    "R001": "Unusually high transaction velocity — {value} transactions in 1 hour (normal: 1-2)",
    "R002": "Geographic impossibility — customer location jumped {distance}km in {minutes} minutes",
    "R003": "High-value transaction ({amount}) from an unrecognised device used for first time",
    "R004": "Transaction at {hour}:00 — outside this customer's normal activity window",
    "R005": "Transaction amount is {ratio}x this customer's 30-day average of {avg}",
    "R006": "Card testing pattern detected — {count} micro-transactions under ₹100 in 1 hour",
    "R007": "AML structuring pattern — {count} transactions just below ₹50,000 threshold",
}

FEATURE_EXPLANATIONS = {
    "amount_anomaly": "Amount deviates {z:.1f} standard deviations from customer baseline",
    "merchant_anomaly": "Customer has never transacted with this merchant before",
    "geo_anomaly": "City not in customer's known location history",
    "device_anomaly": "Unrecognised device — trust score {score:.0%}",
    "time_anomaly": "Transaction at unusual hour for this customer",
    "is_card_testing": "Multiple micro-transactions suggest card testing attack",
    "is_aml_structuring": "Amount just below ₹50,000 RBI reporting threshold",
    "network_risk_score": "Customer connected to suspicious transaction network",
    "sim_swap_risk": "Possible SIM swap — recent device change + multiple OTP requests",
}

def generate_explanation(txn: dict, features: dict, shap_values: dict) -> dict:
    """Generate plain-English explanation for SOC analyst."""
    reasons = []
    
    # Top SHAP features driving the score
    if shap_values:
        top_features = sorted(shap_values.items(), key=lambda x: abs(x[1]), reverse=True)[:3]
        for feat, val in top_features:
            if feat in FEATURE_EXPLANATIONS and abs(val) > 0.05:
                explanation = FEATURE_EXPLANATIONS[feat].format(
                    z=features.get("amount_anomaly", 0) * 4,
                    score=1 - features.get("device_anomaly", 0),
                    ratio=round(features.get("amount_to_avg_ratio", 1), 1),
                    avg=round(features.get("amount_mean", 1000)),
                    count=int(features.get("txn_count_1h", 0)),
                    hour=int(features.get("hour_of_day", 0)),
                    distance=int(features.get("geo_risk_score", 0) * 1000),
                    minutes=30
                )
                reasons.append(explanation)

    # Triggered rule explanations
    rule_names = txn.get("rule_names", [])
    for rule_id in txn.get("triggered_rules", [])[:2]:
        if rule_id in RULE_EXPLANATIONS:
            reasons.append(RULE_EXPLANATIONS[rule_id].format(
                value=int(features.get("txn_count_1h", 0)),
                amount=f"₹{txn['amount']:,.0f}",
                ratio=round(features.get("amount_to_avg_ratio", 1), 1),
                avg=f"₹{features.get('amount_mean', 1000):,.0f}",
                count=int(features.get("txn_count_1h", 0)),
                hour=int(features.get("hour_of_day", 0)),
                distance=500,
                minutes=20
            ))

    # Fraud scenario description
    scenario = txn.get("scenario_description", "")

    return {
        "headline": _generate_headline(txn, features),
        "risk_score": txn.get("risk_score", 0),
        "action_taken": txn.get("action", "monitor"),
        "top_reasons": reasons[:3],
        "scenario": scenario,
        "recommended_action": _recommend_action(txn, features),
        "confidence": "High" if len(reasons) >= 2 else "Medium"
    }

def _generate_headline(txn: dict, features: dict) -> str:
    score = txn.get("risk_score", 0)
    if features.get("is_card_testing"):
        return f"Card testing attack detected on {txn['customer_id']}"
    if features.get("is_aml_structuring"):
        return f"AML structuring pattern — {txn['customer_id']} making structured transfers"
    if features.get("sim_swap_risk", 0) > 0.5:
        return f"Possible SIM swap fraud — {txn['customer_id']} account at risk"
    if features.get("network_risk_score", 0) > 0.6:
        return f"Mule network activity detected — {txn['customer_id']}"
    if score >= 85:
        return f"High-confidence fraud — {txn['customer_id']} transaction blocked"
    return f"Suspicious activity — {txn['customer_id']} requires review"

def _recommend_action(txn: dict, features: dict) -> str:
    score = txn.get("risk_score", 0)
    if score >= 90:
        return "Block card immediately. Create P1 case. Call customer within 15 minutes."
    if score >= 75:
        return "Send OTP. Block if OTP fails. Create P2 case for analyst review."
    if score >= 60:
        return "Send OTP for verification. Monitor account for next 2 hours."
    return "Flag for monitoring. No customer action needed yet."
