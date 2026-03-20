"""MLflow-backed Model Registry with A/B testing support.

Manages champion/challenger model lifecycle:
- Load production model from MLflow registry
- A/B test two model versions
- Log prediction scores for retraining
- Auto-promote challenger if AUC improves by threshold
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

import joblib
import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ModelVersion:
    name: str
    version: str
    model: Any = None
    scaler: Any = None
    auc: float = 0.0
    loaded_at: float = 0.0


class ModelRegistry:
    """Loads models from MLflow or local fallback, supports A/B testing."""

    def __init__(self) -> None:
        self.champion: ModelVersion | None = None
        self.challenger: ModelVersion | None = None
        self._ab_test_active = False
        self._champion_weight = 0.9
        self._challenger_weight = 0.1
        self._prediction_log: list[dict] = []
        self._mlflow_client = None

    def _get_mlflow(self):
        if self._mlflow_client is not None:
            return self._mlflow_client
        try:
            import mlflow
            mlflow.set_tracking_uri(getattr(settings, "MLFLOW_TRACKING_URI", ""))
            self._mlflow_client = mlflow.MlflowClient()
            return self._mlflow_client
        except ImportError:
            logger.warning("MLflow not installed; skipping MLflow integration.")
            return None
        except Exception as exc:
            logger.warning("MLflow unavailable: %s", exc)
            return None

    def load_production_model(self) -> bool:
        """Load the production model from MLflow registry or local fallback."""
        client = self._get_mlflow()
        if client is not None:
            try:
                import mlflow
                model_uri = "models:/fraud-detection-ensemble/Production"
                model = mlflow.sklearn.load_model(model_uri)
                self.champion = ModelVersion(
                    name="fraud-detection-ensemble",
                    version="Production",
                    model=model,
                    loaded_at=time.time(),
                )
                logger.info("Champion model loaded from MLflow")
                return True
            except Exception as exc:
                logger.warning("MLflow model load failed, trying local: %s", exc)

        # Fallback to local model
        try:
            from ml_models.kaggle_fraud_model import fraud_model
            if fraud_model and fraud_model.rf_model is not None:
                self.champion = ModelVersion(
                    name="local-ensemble",
                    version="local",
                    model=fraud_model,
                    loaded_at=time.time(),
                )
                logger.info("Champion model loaded from local fallback")
                return True
        except Exception:
            pass
        return False

    def load_challenger(self, model_name: str = "fraud-detection-ensemble", version: str = "Staging") -> bool:
        """Load a challenger model for A/B testing."""
        client = self._get_mlflow()
        if client is None:
            return False
        try:
            import mlflow
            model_uri = f"models:/{model_name}/{version}"
            model = mlflow.sklearn.load_model(model_uri)
            self.challenger = ModelVersion(
                name=model_name,
                version=version,
                model=model,
                loaded_at=time.time(),
            )
            self._ab_test_active = True
            logger.info("Challenger model loaded: %s/%s", model_name, version)
            return True
        except Exception as exc:
            logger.warning("Failed to load challenger: %s", exc)
            return False

    def predict(self, features: dict[str, Any]) -> dict[str, Any]:
        """Predict using champion (and optionally challenger for A/B test)."""
        result: dict[str, Any] = {"champion_score": 0.0, "source": "heuristic"}

        if self.champion and self.champion.model is not None:
            try:
                champion_score = self._predict_single(self.champion.model, features)
                result["champion_score"] = champion_score
                result["source"] = f"{self.champion.name}/{self.champion.version}"
            except Exception as exc:
                logger.error("Champion prediction failed: %s", exc)

        if self._ab_test_active and self.challenger and self.challenger.model is not None:
            try:
                challenger_score = self._predict_single(self.challenger.model, features)
                result["challenger_score"] = challenger_score
                result["ab_test"] = True
                # Blend scores
                result["blended_score"] = (
                    result["champion_score"] * self._champion_weight
                    + challenger_score * self._challenger_weight
                )
            except Exception:
                pass

        # Log for retraining
        self._prediction_log.append({
            "features": features,
            "score": result.get("blended_score", result["champion_score"]),
            "timestamp": time.time(),
        })
        if len(self._prediction_log) > 10000:
            self._prediction_log = self._prediction_log[-5000:]

        return result

    def _predict_single(self, model: Any, features: dict[str, Any]) -> float:
        """Get fraud probability from a model."""
        if hasattr(model, "predict_fraud_probability"):
            return float(model.predict_fraud_probability(features))
        if hasattr(model, "predict_proba"):
            feature_array = np.array([list(features.values())])
            proba = model.predict_proba(feature_array)
            return float(proba[0][1]) if proba.shape[1] > 1 else float(proba[0][0])
        return 0.0

    def log_training_run(
        self,
        params: dict[str, Any],
        metrics: dict[str, float],
        model: Any,
        model_name: str = "fraud-detection-ensemble",
    ) -> str | None:
        """Log a training run to MLflow with params, metrics, and model artifact."""
        try:
            import mlflow
            import mlflow.sklearn

            mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
            mlflow.set_experiment(settings.MLFLOW_EXPERIMENT_NAME)

            with mlflow.start_run() as run:
                mlflow.log_params(params)
                mlflow.log_metrics(metrics)
                mlflow.sklearn.log_model(
                    model,
                    artifact_path="model",
                    registered_model_name=model_name,
                )
                logger.info("MLflow run logged: %s", run.info.run_id)
                return run.info.run_id
        except Exception as exc:
            logger.warning("MLflow logging failed: %s", exc)
            return None

    def should_promote_challenger(self, new_auc: float, current_auc: float) -> bool:
        """Check if challenger should be promoted (>2% AUC improvement)."""
        return new_auc - current_auc > settings.MODEL_AUTO_PROMOTE_AUC_THRESHOLD

    def get_prediction_log(self) -> list[dict]:
        return list(self._prediction_log)

    def status(self) -> dict[str, Any]:
        return {
            "champion": {
                "name": self.champion.name if self.champion else None,
                "version": self.champion.version if self.champion else None,
                "loaded_at": self.champion.loaded_at if self.champion else None,
            },
            "challenger": {
                "name": self.challenger.name if self.challenger else None,
                "version": self.challenger.version if self.challenger else None,
            } if self.challenger else None,
            "ab_test_active": self._ab_test_active,
            "prediction_log_size": len(self._prediction_log),
        }


# Singleton
model_registry = ModelRegistry()
