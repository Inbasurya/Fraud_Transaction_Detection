"""Model registry with three-tier fallback: MLflow → local pickle → default baseline.

Always returns a usable model so the scoring pipeline is never blocked.
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any, Tuple

import numpy as np
from sklearn.ensemble import RandomForestClassifier

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def load_model() -> Tuple[Any, str]:
    """Load the fraud-detection model.

    Returns
    -------
    (model, source) where *source* is one of ``"mlflow"``, ``"local"``, or
    ``"default"``.  The model object is guaranteed to expose a ``.predict()``
    method.
    """

    # ── 1. MLflow ─────────────────────────────────────────────
    try:
        import mlflow
        from mlflow.exceptions import MlflowException

        mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
        model = mlflow.pyfunc.load_model("models:/fraud_model/Production")
        logger.info("model_loaded", extra={"source": "mlflow",
                                            "uri": settings.MLFLOW_TRACKING_URI})
        return model, "mlflow"
    except ImportError:
        logger.warning("model_mlflow_import_failed",
                        extra={"reason": "mlflow package not installed"})
    except ConnectionError as exc:
        logger.warning("model_mlflow_connection_error",
                        extra={"error": str(exc),
                               "uri": settings.MLFLOW_TRACKING_URI})
    except Exception as exc:
        # Covers MlflowException, HTTP 403, and any unexpected error
        logger.warning("model_mlflow_unavailable",
                        extra={"error": str(exc),
                               "uri": settings.MLFLOW_TRACKING_URI})

    # ── 2. Local pickle ───────────────────────────────────────
    local_path = Path(settings.MODEL_LOCAL_PATH)
    try:
        with local_path.open("rb") as fh:
            model = pickle.load(fh)  # noqa: S301 — trusted internal artefact
        logger.info("model_loaded", extra={"source": "local",
                                            "path": str(local_path)})
        return model, "local"
    except FileNotFoundError:
        logger.warning("model_local_not_found",
                        extra={"path": str(local_path)})
    except Exception as exc:
        logger.warning("model_local_load_failed",
                        extra={"path": str(local_path),
                               "error": str(exc)})

    # ── 3. Default baseline ──────────────────────────────────
    rng = np.random.RandomState(42)
    x_dummy = rng.rand(100, 5)
    y_dummy = (rng.rand(100) > 0.9).astype(int)

    model = RandomForestClassifier(n_estimators=10, random_state=42)
    model.fit(x_dummy, y_dummy)

    logger.warning("model_loaded_default_baseline",
                    extra={"source": "default",
                           "reason": "mlflow and local pickle both unavailable"})
    return model, "default"
