"""Supervised fraud detection model using ensemble of RandomForest, XGBoost, and LightGBM.

Trains on Kaggle credit card fraud dataset and outputs fraud_probability.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

_MODEL_DIR = Path(__file__).resolve().parent.parent.parent / "ml_models"
_MODEL_DIR.mkdir(exist_ok=True)


class SupervisedFraudModel:
    """Ensemble of RF + XGBoost + LightGBM for fraud probability prediction."""

    FEATURE_COLS = [
        "amount",
        "transaction_hour",
        "transaction_amount_ratio",
        "transaction_frequency_last_24h",
        "location_change_flag",
        "device_change_flag",
        "merchant_risk_score",
        "time_since_last_transaction",
        "unusual_time_flag",
        "account_transaction_velocity",
        "amount_deviation",
        "location_stability_score",
        "device_stability_score",
    ]

    WEIGHTS = {"rf": 0.45, "xgb": 0.35, "lgbm": 0.20}

    def __init__(self):
        self.rf_model = None
        self.xgb_model = None
        self.lgbm_model = None
        self.scaler: Optional[StandardScaler] = None
        self.is_trained = False
        self.metrics: dict = {}
        self._load_models()

    # ── Persistence ───────────────────────────────────────────

    def _model_path(self, name: str) -> Path:
        return _MODEL_DIR / f"supervised_{name}.pkl"

    def _load_models(self):
        try:
            if all(self._model_path(n).exists() for n in ("rf", "xgb", "lgbm", "scaler")):
                self.rf_model = joblib.load(self._model_path("rf"))
                self.xgb_model = joblib.load(self._model_path("xgb"))
                self.lgbm_model = joblib.load(self._model_path("lgbm"))
                self.scaler = joblib.load(self._model_path("scaler"))
                self.is_trained = True
                logger.info("Supervised fraud models loaded from disk")
        except Exception as exc:
            logger.warning("Could not load supervised models: %s", exc)

    def _save_models(self):
        joblib.dump(self.rf_model, self._model_path("rf"))
        joblib.dump(self.xgb_model, self._model_path("xgb"))
        joblib.dump(self.lgbm_model, self._model_path("lgbm"))
        joblib.dump(self.scaler, self._model_path("scaler"))
        logger.info("Supervised fraud models saved to disk")

    # ── Training ──────────────────────────────────────────────

    def train(self, df: pd.DataFrame, target_col: str = "is_fraud") -> dict:
        """Train ensemble on a dataframe with features and target column."""
        available = [c for c in self.FEATURE_COLS if c in df.columns]
        if not available:
            raise ValueError("No matching feature columns found in training data")

        X = df[available].fillna(0).values
        y = df[target_col].values.astype(int)

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        self.scaler = StandardScaler()
        X_train_s = self.scaler.fit_transform(X_train)
        X_test_s = self.scaler.transform(X_test)

        # Handle class imbalance
        try:
            from imblearn.over_sampling import SMOTE
            smote = SMOTE(random_state=42)
            X_train_s, y_train = smote.fit_resample(X_train_s, y_train)
        except ImportError:
            logger.warning("imbalanced-learn not installed; skipping SMOTE")

        # ── RandomForest ──
        self.rf_model = RandomForestClassifier(
            n_estimators=200, max_depth=15, min_samples_split=5,
            class_weight="balanced", random_state=42, n_jobs=-1,
        )
        self.rf_model.fit(X_train_s, y_train)

        # ── XGBoost ──
        try:
            from xgboost import XGBClassifier
            scale_ratio = float(np.sum(y_train == 0)) / max(float(np.sum(y_train == 1)), 1)
            self.xgb_model = XGBClassifier(
                n_estimators=200, max_depth=8, learning_rate=0.05,
                scale_pos_weight=scale_ratio, eval_metric="logloss",
                use_label_encoder=False, random_state=42, n_jobs=-1,
            )
            self.xgb_model.fit(X_train_s, y_train)
        except ImportError:
            logger.warning("XGBoost not installed; falling back to RF only")

        # ── LightGBM ──
        try:
            from lightgbm import LGBMClassifier
            self.lgbm_model = LGBMClassifier(
                n_estimators=200, max_depth=10, learning_rate=0.05,
                class_weight="balanced", random_state=42, n_jobs=-1,
                verbose=-1,
            )
            self.lgbm_model.fit(X_train_s, y_train)
        except ImportError:
            logger.warning("LightGBM not installed; falling back to RF + XGB")

        self.is_trained = True
        self._save_models()

        # Evaluate
        y_prob = self._ensemble_predict_proba(X_test_s)
        y_pred = (y_prob >= 0.5).astype(int)

        self.metrics = {
            "accuracy": round(accuracy_score(y_test, y_pred), 4),
            "precision": round(precision_score(y_test, y_pred, zero_division=0), 4),
            "recall": round(recall_score(y_test, y_pred, zero_division=0), 4),
            "f1_score": round(f1_score(y_test, y_pred, zero_division=0), 4),
            "roc_auc": round(roc_auc_score(y_test, y_prob), 4),
            "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
            "classification_report": classification_report(y_test, y_pred, output_dict=True),
        }
        logger.info("Supervised model trained — AUC: %.4f", self.metrics["roc_auc"])
        return self.metrics

    # ── Prediction ────────────────────────────────────────────

    def _ensemble_predict_proba(self, X_scaled: np.ndarray) -> np.ndarray:
        """Weighted ensemble probability."""
        probs = np.zeros(X_scaled.shape[0])
        total_weight = 0.0

        if self.rf_model is not None:
            probs += self.WEIGHTS["rf"] * self.rf_model.predict_proba(X_scaled)[:, 1]
            total_weight += self.WEIGHTS["rf"]

        if self.xgb_model is not None:
            probs += self.WEIGHTS["xgb"] * self.xgb_model.predict_proba(X_scaled)[:, 1]
            total_weight += self.WEIGHTS["xgb"]

        if self.lgbm_model is not None:
            probs += self.WEIGHTS["lgbm"] * self.lgbm_model.predict_proba(X_scaled)[:, 1]
            total_weight += self.WEIGHTS["lgbm"]

        if total_weight > 0:
            probs /= total_weight

        return probs

    def predict_fraud_probability(self, features: dict) -> float:
        """Predict fraud probability for a single transaction's features."""
        if not self.is_trained:
            return self._heuristic_score(features)

        feature_vector = np.array(
            [[features.get(col, 0.0) for col in self.FEATURE_COLS]]
        )
        X_scaled = self.scaler.transform(feature_vector)
        prob = float(self._ensemble_predict_proba(X_scaled)[0])
        return round(min(max(prob, 0.0), 1.0), 4)

    def _heuristic_score(self, features: dict) -> float:
        """Fallback rule-based score when models aren't trained."""
        score = 0.0
        ratio = features.get("transaction_amount_ratio", 1.0)
        if ratio > 5:
            score += 0.3
        elif ratio > 3:
            score += 0.15
        if features.get("device_change_flag", 0):
            score += 0.15
        if features.get("location_change_flag", 0):
            score += 0.15
        if features.get("unusual_time_flag", 0):
            score += 0.1
        velocity = features.get("account_transaction_velocity", 0)
        if velocity > 5:
            score += 0.15
        return min(round(score, 4), 1.0)

    def get_metrics(self) -> dict:
        return self.metrics


# Module-level singleton
supervised_fraud_model = SupervisedFraudModel()
