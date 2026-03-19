"""Behavioral fraud detection using IsolationForest.

Features:
  transaction_amount, hour_of_day, merchant_frequency,
  device_change, location_change, user_average_spend,
  transaction_velocity
"""

from __future__ import annotations

import numpy as np
import logging
from typing import Optional, List
from sklearn.ensemble import IsolationForest

logger = logging.getLogger(__name__)

_model: Optional[IsolationForest] = None


def train_behavior_model(df) -> IsolationForest:
    """Train an IsolationForest on the 7 behavioral features.

    Parameters
    ----------
    df : pandas.DataFrame
        Must contain columns:
        transaction_amount, hour_of_day, merchant_frequency,
        device_change, location_change, user_average_spend,
        transaction_velocity
    """
    global _model

    cols = [
        "transaction_amount",
        "hour_of_day",
        "merchant_frequency",
        "device_change",
        "location_change",
        "user_average_spend",
        "transaction_velocity",
    ]
    X = df[cols].values.astype(float)
    _model = IsolationForest(
        n_estimators=150,
        contamination=0.05,
        random_state=42,
        n_jobs=-1,
    )
    _model.fit(X)
    logger.info("BehaviorModel trained on %d samples", len(X))
    return _model


def predict_behavior_risk(transaction: dict) -> float:
    """Return an anomaly score between 0 (normal) and 1 (highly anomalous).

    Uses the trained IsolationForest when available; otherwise falls back to
    a deterministic heuristic so the pipeline never breaks.
    """
    features = _extract_features(transaction)
    arr = np.array([features])

    if _model is not None:
        try:
            raw = _model.decision_function(arr)[0]
            # decision_function: negative → anomaly; map to 0‑1
            score = 1.0 / (1.0 + np.exp(raw * 3))
            return float(np.clip(score, 0.0, 1.0))
        except Exception as exc:
            logger.warning("BehaviorModel prediction failed: %s", exc)

    return _heuristic_score(transaction, features)


# ── internal helpers ──────────────────────────────────────────

def _extract_features(tx: dict) -> List[float]:
    """Pull the 7 ordered features from a transaction dict."""
    return [
        float(tx.get("transaction_amount") or tx.get("amount", 0)),
        float(tx.get("hour_of_day") or tx.get("transaction_hour", 12)),
        float(tx.get("merchant_frequency", 1)),
        float(tx.get("device_change", 0)),
        float(tx.get("location_change", 0)),
        float(tx.get("user_average_spend") or tx.get("avg_user_spend", 0)),
        float(tx.get("transaction_velocity") or tx.get("velocity", 0)),
    ]


def _heuristic_score(tx: dict, feats: List[float]) -> float:
    """Deterministic fallback when no trained model is available."""
    amount = feats[0]
    hour = feats[1]
    device_change = feats[3]
    location_change = feats[4]
    avg_spend = feats[5]
    velocity = feats[6]

    score = 0.0
    # large amount relative to average
    if avg_spend > 0 and amount > avg_spend * 3:
        score += 0.25
    # night‑time transaction
    if 1 <= hour <= 4:
        score += 0.15
    # device / location context switches
    score += 0.15 * device_change
    score += 0.15 * location_change
    # velocity spike
    if velocity > 5:
        score += 0.20
    # raw amount bump
    score += min(amount / 20_000, 0.10)

    return float(np.clip(score, 0.0, 1.0))
