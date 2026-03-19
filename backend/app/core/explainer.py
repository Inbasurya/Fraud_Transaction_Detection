"""
Natural language fraud explanation generator.
Converts ML features and SHAP values into analyst-readable alert text.
This is what a real SOC analyst sees when they open a fraud case.
"""

SHAP_EXPLANATIONS = {
    "amount_to_avg_ratio": {
        "high": "Amount is {val:.1f}x your usual spending",
        "medium": "Slightly higher than your average spend",
    },
    "is_new_device": {
        "high": "Transaction from an unrecognized device",
    },
    "geo_risk_score": {
        "high": "Unusual location — far from your activity area",
        "medium": "Transaction from a less-frequented location",
    },
    "txn_count_1h": {
        "high": "{val:.0f} transactions in the last hour — abnormal",
    },
    "merchant_risk_score": {
        "high": "High-risk merchant category (crypto/forex/wire)",
        "medium": "Merchant has elevated risk profile",
    },
    "is_odd_hour": {
        "high": "Transaction at unusual hour ({hour}:00 AM)",
    },
    "is_aml_structuring": {
        "high": "Amount pattern matches AML structuring (₹45K-50K range)",
    },
    "is_card_testing": {
        "high": "Micro-transaction burst — card testing pattern",
    },
}

def generate_explanation(shap_values: dict, features: dict) -> dict:
    """
    Convert SHAP values to human-readable explanation.
    Returns top 3 reasons for the decision.
    """
    explanations = []
    
    # Sort features by absolute SHAP impact
    sorted_features = sorted(
        shap_values.items(), 
        key=lambda x: abs(x[1]), 
        reverse=True
    )
    
    for feature_name, shap_val in sorted_features[:5]:
        if abs(shap_val) < 0.01:
            continue
            
        templates = SHAP_EXPLANATIONS.get(feature_name, {})
        feature_val = features.get(feature_name, 0)
        
        text = ""
        if abs(shap_val) > 0.1 and "high" in templates:
            # Handle formatting if template expects params
            try:
                text = templates["high"].format(
                    val=feature_val,
                    hour=features.get("hour_of_day", 0)
                )
            except KeyError:
                # Fallback if formatting fails (e.g. missing param)
                text = templates["high"].replace("{val:.1f}", str(feature_val)).replace("{val:.0f}", str(feature_val))
                
        elif abs(shap_val) > 0.05 and "medium" in templates:
            try:
                text = templates["medium"].format(val=feature_val)
            except KeyError:
                text = templates["medium"]
        else:
            continue
            
        if text:
            explanations.append({
                "feature": feature_name,
                "impact": round(shap_val, 3),
                "direction": "fraud" if shap_val > 0 else "safe",
                "text": text
            })
    
    return {
        "top_reasons": explanations[:3],
        "summary": generate_summary(explanations[:3])
    }

def generate_summary(reasons: list) -> str:
    if not reasons:
        return "No significant risk factors detected"
    
    fraud_reasons = [r for r in reasons if r["direction"] == "fraud"]
    if len(fraud_reasons) >= 2:
        return (f"Multiple risk factors: "
                f"{fraud_reasons[0]['text'].lower()} and "
                f"{fraud_reasons[1]['text'].lower()}")
    elif len(fraud_reasons) == 1:
        return fraud_reasons[0]["text"]
    else:
        return "Risk factors within normal range"
