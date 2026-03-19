import numpy as np
import shap
from typing import Dict, Any, List

from app.models import transaction_model
from app.ml import predict

_explainer = None
_feature_names: List[str] = []


def _ensure_explainer():
    global _explainer, _feature_names
    if _explainer is None:
        if predict._model is None:
            predict._load_artifacts()
        model = predict._model
        if model is None:
            raise RuntimeError("Model not available for explanation")
        base_names = ["amount", "hour", "merchant", "device"]
        n = getattr(model, "n_features_in_", len(base_names))
        names = base_names.copy()
        while len(names) < n:
            names.append(f"f{len(names)}")
        _feature_names = names
        try:
            _explainer = shap.Explainer(model, feature_names=_feature_names)
        except Exception:
            _explainer = shap.Explainer(model)


def explain_transaction(tx: transaction_model.Transaction) -> Dict[str, Any]:
    if tx is None:
        raise ValueError("Transaction is None")

    tx_dict = {
        "transaction_id": tx.transaction_id,
        "user_id": tx.user_id,
        "amount": tx.amount,
        "merchant": tx.merchant,
        "location": tx.location,
        "device_type": tx.device_type,
        "timestamp": tx.timestamp,
    }

    prob_result = predict.predict(tx_dict)
    fraud_prob = prob_result.get("fraud_probability", 0.0)

    _ensure_explainer()
    features_df = predict._transform(tx_dict)

    try:
        shap_values = _explainer(features_df)
    except Exception as e:
        raise RuntimeError(f"Failed to compute SHAP values: {e}")

    vals = np.array(shap_values.values)[0]
    names = _feature_names

    abs_vals = np.abs(vals)
    top_idx = np.argsort(abs_vals)[::-1][:3]
    top_features = []
    for i in top_idx:
        top_features.append({"feature": names[i], "impact": float(vals[i])})

    return {
        "transaction_id": tx.transaction_id,
        "fraud_probability": float(fraud_prob),
        "top_features": top_features,
    }

