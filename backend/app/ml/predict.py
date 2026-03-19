"""Fraud prediction module — loads trained model + scaler, provides predict()."""

import os
import joblib
import numpy as np
import pandas as pd
from typing import Dict, Any
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

_BASE = Path(__file__).resolve().parent / "models"
MODEL_PATH = _BASE / "fraud_model.pkl"
SCALER_PATH = _BASE / "scaler.pkl"
ANOMALY_PATH = _BASE / "anomaly_model.pkl"

_model = None
_scaler = None
_anomaly_model = None


def _load_artifacts():
    global _model, _scaler, _anomaly_model
    try:
        _model = joblib.load(MODEL_PATH)
        logger.info("Fraud model loaded from %s", MODEL_PATH)
    except Exception as e:
        logger.warning("Fraud model not found (%s) — using fallback heuristic", e)
        _model = None

    try:
        _scaler = joblib.load(SCALER_PATH)
        logger.info("Scaler loaded from %s", SCALER_PATH)
    except Exception:
        _scaler = None

    try:
        _anomaly_model = joblib.load(ANOMALY_PATH)
        logger.info("Anomaly model loaded from %s", ANOMALY_PATH)
    except Exception:
        _anomaly_model = None


def _ensure_loaded():
    if _model is None and not MODEL_PATH.exists():
        _load_artifacts()
    elif _model is None:
        _load_artifacts()


def _transform(transaction: Dict[str, Any]) -> pd.DataFrame:
    amount = float(transaction.get("amount", 0.0))
    timestamp = transaction.get("timestamp")
    hour = 0
    if timestamp:
        try:
            hour = pd.to_datetime(timestamp).hour
        except Exception:
            hour = 0

    features = [[amount, hour]]
    if _scaler is not None:
        try:
            features = _scaler.transform(features)
        except Exception:
            pass
    return pd.DataFrame(features)


def predict(transaction: Dict[str, Any]) -> Dict[str, float]:
    """Return fraud_probability (0‑1) using the trained model or a heuristic."""
    _ensure_loaded()
    features = _transform(transaction)

    if _model is not None:
        try:
            proba = float(_model.predict_proba(features)[0, 1])
            return {"fraud_probability": proba}
        except Exception as e:
            logger.error("Model prediction failed: %s", e)

    # Heuristic fallback when no trained model is available
    amount = float(transaction.get("amount", 0))
    hour = features.iloc[0, 1] if len(features.columns) > 1 else 0
    prob = min(amount / 15000.0, 0.85)
    if 1 <= hour <= 4:
        prob = min(prob + 0.1, 1.0)
    return {"fraud_probability": round(prob, 4)}


def predict_anomaly(transaction: Dict[str, Any]) -> float:
    """Return anomaly score 0‑1 (1 = most anomalous) via Isolation Forest."""
    _ensure_loaded()
    features = _transform(transaction)

    if _anomaly_model is not None:
        try:
            raw = _anomaly_model.decision_function(features)[0]
            # decision_function: negative = anomaly. map to 0‑1
            score = 1.0 / (1.0 + np.exp(raw * 3))
            return float(np.clip(score, 0.0, 1.0))
        except Exception as e:
            logger.error("Anomaly model failed: %s", e)

    # Heuristic fallback
    amount = float(transaction.get("amount", 0))
    return min(amount / 20000.0, 0.7)

