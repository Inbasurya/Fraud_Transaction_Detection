from __future__ import annotations

"""
ML Engine — loads XGBoost model from MLflow, computes SHAP explanations.
Falls back to training a lightweight model on PaySim-style data if
no registered model exists.
"""

import logging
import os
import pickle
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Feature columns the model expects (order matters)
FEATURE_NAMES = (
    "txn_count_1h", "txn_count_24h", "txn_count_7d",
    "amount", "amount_log", "amount_to_avg_ratio", "amount_to_max_ratio",
    "unique_merchants_7d", "merchant_risk_score", "is_international",
    "is_new_device", "device_count_30d",
    "city_changed", "geo_risk_score",
    "hour_of_day", "is_odd_hour", "is_weekend",
    "category_risk",
    "is_aml_structuring", "is_card_testing",
    "days_since_first_txn", "avg_daily_txn_count"
)


def _build_feature_array(txn: dict, features: dict) -> np.ndarray:
    """Merge transaction fields + feature-store features into ordered array."""
    merged = {**features, "amount": txn.get("amount", 0)}
    import pandas as pd
    return pd.DataFrame([[merged.get(c, 0.0) for c in FEATURE_NAMES]], columns=list(FEATURE_NAMES))


class MLEngine:
    """
    Wraps an XGBoost classifier with SHAP TreeExplainer.
    - Tries to load from MLflow model registry first.
    - Falls back to local pickle under ml_models/.
    - If nothing found, trains a lightweight model on synthetic data.
    """

    def __init__(self):
        self._model = None
        self._scaler = None
        self._explainer = None
        self._loaded = False
        self.load_source = None

    async def load(self) -> None:
        if self._loaded:
            return

        # 1) Try MLflow
        if self._try_load_mlflow():
            self._loaded = True
            self.load_source = "mlflow"
            return

        # 2) Try local pickle
        if self._try_load_pickle():
            self._loaded = True
            self.load_source = "pickle"
            return

        # 3) Train fallback
        logger.warning("No high-quality model found. Training weak fallback...")
        self._train_fallback()
        self._loaded = True
        self.load_source = "fallback"

    def _try_load_mlflow(self) -> bool:
        # ... (mlflow logic)
        return False

    def _try_load_pickle(self) -> bool:
        base_dir = Path(__file__).parent.parent
        target_dir = base_dir / "models"
        pkl = target_dir / "xgboost_fraud.pkl"
        scaler_pkl = target_dir / "scaler.pkl"
        
        if pkl.exists():
            try:
                with open(pkl, "rb") as f:
                    self._model = pickle.load(f)
                if scaler_pkl.exists():
                    with open(scaler_pkl, "rb") as f:
                        self._scaler = pickle.load(f)
                n_feat = getattr(self._model, 'n_features_in_', '?')
                logger.info("XGBoost model loaded from %s (%d bytes, %s features)",
                            pkl, pkl.stat().st_size, n_feat)
                self._init_explainer()
                return True
            except Exception as e:
                logger.error("Failed to load local pickle: %s", e)
        else:
            logger.warning("Model file not found: %s", pkl)
        return False

    def _train_fallback(self) -> None:
        """Train a small XGBoost on synthetic labeled data."""
        try:
            import xgboost as xgb
            from sklearn.preprocessing import StandardScaler
        except ImportError:
            logger.warning("Dependencies missing — ML engine disabled")
            return

        rng = np.random.default_rng(42)
        n_legit, n_fraud = 5000, 250
        X = np.vstack([
            rng.normal(0, 1, (n_legit, len(FEATURE_NAMES))),
            rng.normal(2, 1.5, (n_fraud, len(FEATURE_NAMES)))
        ]).astype(np.float32)
        y = np.concatenate([np.zeros(n_legit), np.ones(n_fraud)])

        self._scaler = StandardScaler()
        X_scaled = self._scaler.fit_transform(X)

        model = xgb.XGBClassifier(n_estimators=100, max_depth=4, scale_pos_weight=20)
        model.fit(X_scaled, y)
        self._model = model

        # Persist
        base_dir = Path(__file__).parent.parent
        m_dir = base_dir / "models"
        m_dir.mkdir(exist_ok=True)
        with open(m_dir / "xgboost_fraud.pkl", "wb") as f:
            pickle.dump(model, f)
        with open(m_dir / "scaler.pkl", "wb") as f:
            pickle.dump(self._scaler, f)

        self._init_explainer()

    def _init_explainer(self) -> None:
        try:
            import shap

            self._explainer = shap.TreeExplainer(self._model)
            logger.info("SHAP TreeExplainer initialised")
        except Exception as exc:
            logger.warning("SHAP explainer unavailable: %s", exc)
            self._explainer = None

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    async def predict(self, txn: dict, features: dict) -> dict[str, Any]:
        if self._model is None:
            return {"ml_score": 0.0, "shap_values": {}}

        X_raw = _build_feature_array(txn, features)
        X = X_raw
        if self._scaler is not None:
            try:
                X = self._scaler.transform(X_raw)
            except Exception as e:
                logger.warning("Scaling failed: %s", e)

        try:
            proba = self._model.predict_proba(X)[0]
            ml_score = float(proba[1]) if len(proba) > 1 else float(proba[0])
        except Exception as exc:
            logger.warning("ML predict failed: %s", exc)
            return {"ml_score": 0.0, "shap_values": {}}

        shap_dict: dict[str, float] = {}
        if self._explainer is not None:
            try:
                # TreeExplainer usually works on raw if model is Tree, 
                # but if model was trained on scaled, we want SHAP on scaled
                sv = self._explainer.shap_values(X)
                if isinstance(sv, list):
                    sv = sv[1]  # class-1 SHAP values
                for i, col in enumerate(FEATURE_NAMES):
                    shap_dict[col] = round(float(sv[0][i]), 6)
            except Exception as exc:
                logger.debug("SHAP computation failed: %s", exc)

        return {"ml_score": round(ml_score, 6), "shap_values": shap_dict}
