"""
Train XGBoost + LightGBM on PaySim-style synthetic data.
Logs to MLflow. Produces ml_models/fraud_xgb.pkl + ml_models/fraud_lgb.pkl.

Usage:
    python -m backend.ml.train_paysim
"""

import os
import pickle
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    classification_report,
    roc_auc_score,
    average_precision_score,
)

logger = logging.getLogger(__name__)

FEATURE_COLS = [
    "amount",
    "txn_count_1h",
    "txn_total_1h",
    "txn_avg_1h",
    "txn_max_1h",
    "txn_count_24h",
    "txn_total_24h",
    "txn_avg_24h",
    "txn_max_24h",
    "txn_count_7d",
    "txn_total_7d",
    "txn_avg_7d",
    "txn_max_7d",
    "amount_deviation",
    "distance_from_prev_km",
    "unique_devices_24h",
    "is_new_device",
    "unique_ips_24h",
    "hour_of_day",
    "is_weekend",
    "is_night",
    "merchant_diversity_24h",
]


def generate_synthetic_dataset(n_legit: int = 20000, n_fraud: int = 1000):
    """Generate labeled synthetic dataset mimicking PaySim patterns."""
    rng = np.random.default_rng(42)

    # Legit
    X_legit = rng.normal(loc=0, scale=1, size=(n_legit, len(FEATURE_COLS)))
    X_legit[:, 0] = rng.lognormal(mean=7, sigma=1, size=n_legit)  # amount
    X_legit[:, 18] = rng.integers(8, 22, size=n_legit)  # hour_of_day
    X_legit[:, 19] = rng.binomial(1, 0.28, size=n_legit)  # is_weekend
    X_legit[:, 20] = 0  # is_night

    # Fraud
    X_fraud = rng.normal(loc=1.5, scale=1.5, size=(n_fraud, len(FEATURE_COLS)))
    X_fraud[:, 0] = rng.lognormal(mean=9, sigma=1.5, size=n_fraud)  # higher amounts
    X_fraud[:, 1] = rng.poisson(8, size=n_fraud)  # high velocity 1h
    X_fraud[:, 14] = rng.exponential(200, size=n_fraud)  # large distances
    X_fraud[:, 16] = rng.binomial(1, 0.7, size=n_fraud)  # new device
    X_fraud[:, 18] = rng.integers(0, 5, size=n_fraud)  # odd hours
    X_fraud[:, 20] = 1  # is_night

    X = np.vstack([X_legit, X_fraud]).astype(np.float32)
    y = np.concatenate([np.zeros(n_legit), np.ones(n_fraud)]).astype(np.int32)

    df = pd.DataFrame(X, columns=FEATURE_COLS)
    df["is_fraud"] = y
    return df


def train():
    logging.basicConfig(level=logging.INFO)
    logger.info("Generating synthetic PaySim-style dataset …")
    df = generate_synthetic_dataset()

    X = df[FEATURE_COLS].values
    y = df["is_fraud"].values
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )

    Path("ml_models").mkdir(exist_ok=True)

    # ── XGBoost ─────────────────────────────────────────────────
    try:
        import xgboost as xgb

        logger.info("Training XGBoost …")
        xgb_model = xgb.XGBClassifier(
            n_estimators=200,
            max_depth=5,
            learning_rate=0.05,
            scale_pos_weight=len(y_train[y_train == 0]) / max(len(y_train[y_train == 1]), 1),
            use_label_encoder=False,
            eval_metric="aucpr",
            random_state=42,
        )
        xgb_model.fit(X_train, y_train, verbose=False)
        y_pred = xgb_model.predict(X_test)
        y_proba = xgb_model.predict_proba(X_test)[:, 1]

        logger.info("XGBoost results:")
        logger.info("\n%s", classification_report(y_test, y_pred))
        logger.info("ROC-AUC: %.4f", roc_auc_score(y_test, y_proba))
        logger.info("PR-AUC:  %.4f", average_precision_score(y_test, y_proba))

        with open("ml_models/fraud_xgb.pkl", "wb") as f:
            pickle.dump(xgb_model, f)
        logger.info("Saved ml_models/fraud_xgb.pkl")

        _log_to_mlflow("fraud-xgb", xgb_model, X_test, y_test, y_proba, "xgboost")
    except ImportError:
        logger.warning("xgboost not installed, skipping")

    # ── LightGBM ────────────────────────────────────────────────
    try:
        import lightgbm as lgb

        logger.info("Training LightGBM …")
        lgb_model = lgb.LGBMClassifier(
            n_estimators=200,
            max_depth=5,
            learning_rate=0.05,
            scale_pos_weight=len(y_train[y_train == 0]) / max(len(y_train[y_train == 1]), 1),
            random_state=42,
            verbose=-1,
        )
        lgb_model.fit(X_train, y_train)
        y_pred = lgb_model.predict(X_test)
        y_proba = lgb_model.predict_proba(X_test)[:, 1]

        logger.info("LightGBM results:")
        logger.info("\n%s", classification_report(y_test, y_pred))
        logger.info("ROC-AUC: %.4f", roc_auc_score(y_test, y_proba))
        logger.info("PR-AUC:  %.4f", average_precision_score(y_test, y_proba))

        with open("ml_models/fraud_lgb.pkl", "wb") as f:
            pickle.dump(lgb_model, f)
        logger.info("Saved ml_models/fraud_lgb.pkl")

        _log_to_mlflow("fraud-lgb", lgb_model, X_test, y_test, y_proba, "lightgbm")
    except ImportError:
        logger.warning("lightgbm not installed, skipping")


def _log_to_mlflow(name, model, X_test, y_test, y_proba, flavor):
    try:
        import mlflow
        mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", ""))
        MLFLOW_AVAILABLE = True
    except ImportError:
        MLFLOW_AVAILABLE = False
    if MLFLOW_AVAILABLE:
        try:
            mlflow.set_experiment("fraud-detection")
            with mlflow.start_run(run_name=name):
                mlflow.log_params(model.get_params())
                mlflow.log_metric("roc_auc", roc_auc_score(y_test, y_proba))
                mlflow.log_metric("pr_auc", average_precision_score(y_test, y_proba))
                if flavor == "xgboost":
                    mlflow.xgboost.log_model(model, "model", registered_model_name=name)
                elif flavor == "lightgbm":
                    mlflow.lightgbm.log_model(model, "model", registered_model_name=name)
            logger.info("Logged %s to MLflow", name)
        except Exception as exc:
            logger.warning("MLflow logging failed: %s", exc)


if __name__ == "__main__":
    train()
