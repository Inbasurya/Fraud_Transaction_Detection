"""
Ensures the XGBoost fraud model exists on disk.
Called at startup when the model file is not found
(e.g. cold deploys on Render where .pkl is not committed).
Trains on synthetic data (~15 K samples) in roughly 30 seconds.
"""
from __future__ import annotations

import logging
import os

import numpy as np
import joblib

logger = logging.getLogger(__name__)

# Absolute path — resolves correctly regardless of CWD
MODEL_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "../ml_models/xgboost_fraud_model.pkl")
)

FEATURE_NAMES = [
    "txn_count_1h", "txn_count_24h", "txn_count_7d",
    "amount", "amount_log", "amount_to_avg_ratio",
    "amount_to_max_ratio", "merchant_risk_score",
    "is_new_device", "geo_risk_score", "city_changed",
    "is_odd_hour", "hour_of_day", "is_aml_structuring",
    "is_card_testing", "is_international",
    "unique_merchants_7d", "device_count_30d",
    "is_weekend", "category_risk",
    "days_since_first_txn", "avg_daily_txn_count",
]


def model_exists() -> bool:
    return os.path.exists(MODEL_PATH)


def train_and_save_model():
    """Train XGBoost on synthetic data and save to MODEL_PATH."""
    import xgboost as xgb
    from sklearn.model_selection import train_test_split

    logger.info("Training XGBoost model on synthetic data...")
    np.random.seed(42)

    n = 15_000
    fraud_rate = 0.008

    X = np.column_stack([
        np.random.poisson(2, n),                        # txn_count_1h
        np.random.poisson(8, n),                        # txn_count_24h
        np.random.poisson(25, n),                       # txn_count_7d
        np.random.lognormal(7, 1.5, n),                 # amount
        np.random.normal(7, 1.5, n),                    # amount_log
        np.random.lognormal(0, 0.5, n),                 # amount_to_avg_ratio
        np.random.uniform(0.01, 1.0, n),                # amount_to_max_ratio
        np.random.beta(1, 5, n),                        # merchant_risk_score
        np.random.binomial(1, 0.05, n),                 # is_new_device
        np.random.beta(1, 4, n),                        # geo_risk_score
        np.random.binomial(1, 0.08, n),                 # city_changed
        np.random.binomial(1, 0.12, n),                 # is_odd_hour
        np.random.randint(0, 24, n),                    # hour_of_day
        np.random.binomial(1, 0.02, n),                 # is_aml_structuring
        np.random.binomial(1, 0.01, n),                 # is_card_testing
        np.random.binomial(1, 0.05, n),                 # is_international
        np.random.poisson(5, n),                        # unique_merchants_7d
        np.random.poisson(1.5, n),                      # device_count_30d
        np.random.binomial(1, 0.28, n),                 # is_weekend
        np.random.beta(1, 4, n),                        # category_risk
        np.random.exponential(90, n),                   # days_since_first_txn
        np.random.poisson(3, n),                        # avg_daily_txn_count
    ])

    y = np.zeros(n)
    fraud_idx = np.random.choice(n, int(n * fraud_rate), replace=False)
    # Make fraud patterns distinguishable
    X[fraud_idx, 7] = np.random.uniform(0.7, 1.0, len(fraud_idx))   # high merchant_risk
    X[fraud_idx, 8] = 1                                               # is_new_device
    X[fraud_idx, 5] = np.random.uniform(5, 20, len(fraud_idx))       # high amount_ratio
    X[fraud_idx, 9] = np.random.uniform(0.6, 1.0, len(fraud_idx))   # high geo_risk
    y[fraud_idx] = 1

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=5,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=int((1 - fraud_rate) / fraud_rate),
        eval_metric="auc",
        random_state=42,
        tree_method="hist",
        device="cpu",
    )
    model.fit(X_train, y_train, verbose=False)

    from sklearn.metrics import roc_auc_score
    y_pred = model.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, y_pred)
    logger.info("Model trained — AUC: %.4f", auc)

    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    logger.info("Model saved to %s", MODEL_PATH)
    return model


def load_or_train_model():
    """Return (model, FEATURE_NAMES). Trains if the pkl is missing or corrupt."""
    if model_exists():
        try:
            model = joblib.load(MODEL_PATH)
            logger.info("Model loaded from %s", MODEL_PATH)
            return model, FEATURE_NAMES
        except Exception as exc:
            logger.error("Model load failed (%s) — retraining", exc)

    logger.warning("Model not found — training now (this takes ~30 s)...")
    model = train_and_save_model()
    return model, FEATURE_NAMES
