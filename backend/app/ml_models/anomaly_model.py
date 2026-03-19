"""Behavioral anomaly detection using IsolationForest and Autoencoder.

Outputs anomaly_score (0 = normal, 1 = highly anomalous).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import joblib
import numpy as np

logger = logging.getLogger(__name__)

_MODEL_DIR = Path(__file__).resolve().parent.parent.parent / "ml_models"
_MODEL_DIR.mkdir(exist_ok=True)


class AnomalyModel:
    """Combined IsolationForest + Autoencoder anomaly scorer."""

    FEATURE_COLS = [
        "amount",
        "transaction_hour",
        "transaction_amount_ratio",
        "transaction_frequency_last_24h",
        "location_change_flag",
        "device_change_flag",
        "time_since_last_transaction",
        "account_transaction_velocity",
        "amount_deviation",
    ]

    def __init__(self):
        self.isolation_forest = None
        self.autoencoder = None
        self.scaler = None
        self.is_trained = False
        self._load_models()

    # ── Persistence ───────────────────────────────────────────

    def _model_path(self, name: str) -> Path:
        return _MODEL_DIR / f"anomaly_{name}.pkl"

    def _load_models(self):
        try:
            if self._model_path("iforest").exists() and self._model_path("scaler").exists():
                self.isolation_forest = joblib.load(self._model_path("iforest"))
                self.scaler = joblib.load(self._model_path("scaler"))
                self.is_trained = True
                logger.info("Anomaly models loaded from disk")
                if self._model_path("autoencoder").exists():
                    self.autoencoder = joblib.load(self._model_path("autoencoder"))
        except Exception as exc:
            logger.warning("Could not load anomaly models: %s", exc)

    def _save_models(self):
        if self.isolation_forest:
            joblib.dump(self.isolation_forest, self._model_path("iforest"))
        if self.scaler:
            joblib.dump(self.scaler, self._model_path("scaler"))
        if self.autoencoder:
            joblib.dump(self.autoencoder, self._model_path("autoencoder"))
        logger.info("Anomaly models saved to disk")

    # ── Training ──────────────────────────────────────────────

    def train(self, data: np.ndarray):
        """Train IsolationForest and Autoencoder on feature matrix.

        Args:
            data: 2D numpy array of shape (n_samples, n_features)
        """
        from sklearn.ensemble import IsolationForest
        from sklearn.preprocessing import StandardScaler

        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(data)

        # IsolationForest
        self.isolation_forest = IsolationForest(
            n_estimators=200,
            contamination=0.05,
            max_samples="auto",
            random_state=42,
            n_jobs=-1,
        )
        self.isolation_forest.fit(X_scaled)

        # Simple autoencoder via MLPRegressor (identity mapping)
        try:
            from sklearn.neural_network import MLPRegressor

            n_features = X_scaled.shape[1]
            hidden_size = max(n_features // 2, 3)
            self.autoencoder = MLPRegressor(
                hidden_layer_sizes=(hidden_size, max(hidden_size // 2, 2), hidden_size),
                activation="relu",
                solver="adam",
                max_iter=200,
                random_state=42,
            )
            self.autoencoder.fit(X_scaled, X_scaled)
        except Exception as exc:
            logger.warning("Autoencoder training failed: %s", exc)

        self.is_trained = True
        self._save_models()
        logger.info("Anomaly models trained on %d samples", data.shape[0])

    # ── Scoring ───────────────────────────────────────────────

    def predict_anomaly_score(self, features: dict) -> float:
        """Compute anomaly score for a single transaction (0 = normal, 1 = anomalous)."""
        if not self.is_trained:
            return self._heuristic_anomaly(features)

        feature_vector = np.array(
            [[features.get(col, 0.0) for col in self.FEATURE_COLS]]
        )
        X_scaled = self.scaler.transform(feature_vector)

        # IsolationForest score: decision_function returns negative for anomalies
        if_raw = self.isolation_forest.decision_function(X_scaled)[0]
        # Convert to 0-1 range: more negative = more anomalous
        if_score = max(0.0, min(1.0, 0.5 - if_raw))

        # Autoencoder reconstruction error
        ae_score = 0.0
        if self.autoencoder is not None:
            reconstructed = self.autoencoder.predict(X_scaled)
            mse = float(np.mean((X_scaled - reconstructed) ** 2))
            ae_score = min(1.0, mse / 2.0)  # Normalize

        # Blend: 60% IsolationForest, 40% Autoencoder
        combined = 0.6 * if_score + 0.4 * ae_score
        return round(min(max(combined, 0.0), 1.0), 4)

    def _heuristic_anomaly(self, features: dict) -> float:
        """Fallback anomaly scoring without trained models."""
        score = 0.0
        ratio = features.get("transaction_amount_ratio", 1.0)
        if ratio > 5:
            score += 0.35
        elif ratio > 3:
            score += 0.2
        if features.get("device_change_flag", 0):
            score += 0.15
        if features.get("unusual_time_flag", 0):
            score += 0.15
        velocity = features.get("account_transaction_velocity", 0)
        if velocity > 5:
            score += 0.2
        deviation = abs(features.get("amount_deviation", 0))
        if deviation > 3:
            score += 0.15
        return min(round(score, 4), 1.0)

    def get_model_info(self) -> dict:
        return {
            "is_trained": self.is_trained,
            "has_isolation_forest": self.isolation_forest is not None,
            "has_autoencoder": self.autoencoder is not None,
        }


# Module-level singleton
anomaly_model = AnomalyModel()
