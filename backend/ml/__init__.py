from __future__ import annotations

"""
Model Registry helper — wraps MLflow model management.
"""

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


class ModelRegistry:
    """Light wrapper around MLflow model registry."""

    def __init__(self, tracking_uri: str | None = None):
        self.tracking_uri = tracking_uri or os.getenv(
            "MLFLOW_TRACKING_URI", "http://localhost:5001"
        )

    def list_models(self) -> list[dict[str, Any]]:
        try:
            import mlflow

            mlflow.set_tracking_uri(self.tracking_uri)
            client = mlflow.tracking.MlflowClient()
            models = client.search_registered_models()
            return [
                {
                    "name": m.name,
                    "latest_versions": [
                        {
                            "version": v.version,
                            "stage": v.current_stage,
                            "run_id": v.run_id,
                        }
                        for v in (m.latest_versions or [])
                    ],
                }
                for m in models
            ]
        except Exception as exc:
            logger.warning("Failed to list models: %s", exc)
            return []

    def get_model_metrics(self, run_id: str) -> dict[str, Any]:
        try:
            import mlflow

            mlflow.set_tracking_uri(self.tracking_uri)
            client = mlflow.tracking.MlflowClient()
            run = client.get_run(run_id)
            return dict(run.data.metrics)
        except Exception as exc:
            logger.warning("Failed to get metrics for %s: %s", run_id, exc)
            return {}
