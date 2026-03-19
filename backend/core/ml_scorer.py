"""
Real-time ML scoring — loads trained XGBoost model
and scores transactions in <10ms using computed features.
Falls back to rule-based scoring if model not loaded.
"""
import pickle
import json
import numpy as np
import shap
import os
from typing import Optional
from core.feature_engineer import FeatureEngineer, FEATURE_NAMES

SCALE_IDXS = [3, 4, 5, 6]  # amount, amount_log, ratios

class MLScorer:
    def __init__(self):
        self.model = None
        self.scaler = None
        self.explainer = None
        self.metrics = {}
        self.feature_importance = {}
        self.model_loaded = False

    def load_model(self):
        try:
            with open("models/xgboost_fraud.pkl", "rb") as f:
                self.model = pickle.load(f)
            with open("models/scaler.pkl", "rb") as f:
                self.scaler = pickle.load(f)
            with open("models/metrics.json") as f:
                self.metrics = json.load(f)
            with open("models/feature_importance.json") as f:
                self.feature_importance = json.load(f)
            self.explainer = shap.TreeExplainer(self.model)
            self.model_loaded = True
            print(f"ML model loaded — AUC: {self.metrics.get('auc_roc')}")
        except FileNotFoundError:
            print("No trained model found. Run: python ml/train_model.py")
            self.model_loaded = False

    async def score(self, features: dict) -> dict:
        """
        Score a transaction. Returns risk_score (0-100) and SHAP explanation.
        """
        if not self.model_loaded:
            return self._rule_fallback(features)

        # Build feature vector in correct order
        X = np.array([[features.get(f, 0.0) for f in FEATURE_NAMES]])

        # Scale amount features
        X_scaled = X.copy()
        X_scaled[:, SCALE_IDXS] = self.scaler.transform(X[:, SCALE_IDXS])

        # Predict fraud probability
        fraud_prob = float(self.model.predict_proba(X_scaled)[0][1])
        risk_score = round(fraud_prob * 100, 1)

        # SHAP explanation for this transaction
        shap_vals = self.explainer.shap_values(X_scaled)[0]
        top_shap = sorted(
            zip(FEATURE_NAMES, shap_vals),
            key=lambda x: abs(x[1]),
            reverse=True
        )[:5]
        shap_explanation = {k: round(float(v), 4) for k, v in top_shap}

        # Risk level and action
        if risk_score >= 85:
            risk_level = "fraudulent"
            action = "block"
        elif risk_score >= 70:
            risk_level = "fraudulent"
            action = "flag_and_review"
        elif risk_score >= 50:
            risk_level = "suspicious"
            action = "step_up_auth"
        elif risk_score >= 30:
            risk_level = "suspicious"
            action = "monitor"
        else:
            risk_level = "safe"
            action = "approve"

        return {
            "risk_score": risk_score,
            "fraud_probability": fraud_prob,
            "risk_level": risk_level,
            "action": action,
            "model": "xgboost_v2",
            "shap_values": shap_explanation,
            "shap_top_feature": top_shap[0][0] if top_shap else "unknown",
            "features_used": features
        }

    def _rule_fallback(self, features: dict) -> dict:
        """Fallback rule-based scoring when ML model is not loaded."""
        score = 0
        rules = []

        if features.get("txn_count_1h", 0) > 5:
            score += 35; rules.append("R001")
        if features.get("geo_risk_score", 0) > 0.8:
            score += 40; rules.append("R002")
        if features.get("is_new_device") and features.get("amount", 0) > 20000:
            score += 30; rules.append("R003")
        if features.get("is_odd_hour"):
            score += 15; rules.append("R004")
        if features.get("amount_to_avg_ratio", 1) > 5:
            score += 25; rules.append("R005")
        if features.get("is_card_testing"):
            score += 40; rules.append("R006")
        if features.get("is_aml_structuring"):
            score += 35; rules.append("R007")
        if features.get("merchant_risk_score", 0) > 0.7:
            score += 20

        score = min(score, 100)
        risk_level = "fraudulent" if score >= 70 else "suspicious" if score >= 30 else "safe"
        action = "block" if score >= 85 else "flag_and_review" if score >= 70 else \
                 "step_up_auth" if score >= 50 else "monitor" if score >= 30 else "approve"

        return {
            "risk_score": float(score),
            "fraud_probability": score / 100,
            "risk_level": risk_level,
            "action": action,
            "model": "rule_fallback",
            "shap_values": {},
            "shap_top_feature": rules[0] if rules else "none",
            "triggered_rules": rules
        }

# Singleton
scorer = MLScorer()
