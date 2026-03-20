"""
Train model on IEEE-CIS Fraud Detection dataset.
Expects data files in data/ folder. If not present, falls back to synthetic.

Usage:
    python -m backend.ml.train_ieee
"""

import logging
import os
import pickle
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


def load_ieee_data():
    """Load IEEE-CIS data from CSV or fall back to synthetic."""
    identity_path = Path("data/ieee_identity.csv")
    transaction_path = Path("data/ieee_transaction.csv")

    if transaction_path.exists():
        logger.info("Loading IEEE-CIS data from %s", transaction_path)
        txn_df = pd.read_csv(transaction_path)

        if identity_path.exists():
            id_df = pd.read_csv(identity_path)
            df = txn_df.merge(id_df, on="TransactionID", how="left")
        else:
            df = txn_df

        return df
    else:
        logger.warning(
            "IEEE-CIS data not found at %s — generating synthetic substitute",
            transaction_path,
        )
        return _generate_ieee_synthetic()


def _generate_ieee_synthetic(n: int = 20000):
    """Generate synthetic data with IEEE-CIS-like features."""
    rng = np.random.default_rng(123)

    n_fraud = int(n * 0.035)
    n_legit = n - n_fraud

    data = {
        "TransactionAmt": np.concatenate([
            rng.lognormal(4, 1, n_legit),
            rng.lognormal(6, 1.5, n_fraud),
        ]),
        "ProductCD": rng.choice(["W", "C", "S", "H", "R"], size=n),
        "card4": rng.choice(["visa", "mastercard", "discover", "american express"], size=n),
        "card6": rng.choice(["debit", "credit"], size=n),
        "P_emaildomain": rng.choice(
            ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "protonmail.com", None],
            size=n,
        ),
        "dist1": np.concatenate([
            rng.exponential(10, n_legit),
            rng.exponential(100, n_fraud),
        ]),
        "C1": rng.poisson(2, size=n).astype(float),
        "C2": rng.poisson(1, size=n).astype(float),
        "D1": np.concatenate([
            rng.exponential(30, n_legit),
            rng.exponential(5, n_fraud),
        ]),
        "isFraud": np.concatenate([np.zeros(n_legit), np.ones(n_fraud)]),
    }

    return pd.DataFrame(data)


def train():
    logging.basicConfig(level=logging.INFO)
    df = load_ieee_data()

    target = "isFraud" if "isFraud" in df.columns else "is_fraud"
    if target not in df.columns:
        logger.error("No target column found")
        return

    # Select numeric features only
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    numeric_cols = [c for c in numeric_cols if c != target]

    X = df[numeric_cols].fillna(0).values.astype(np.float32)
    y = df[target].values.astype(np.int32)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )

    Path("ml_models").mkdir(exist_ok=True)

    try:
        import xgboost as xgb

        logger.info("Training XGBoost on IEEE-CIS features (%d cols) …", X.shape[1])
        model = xgb.XGBClassifier(
            n_estimators=300,
            max_depth=6,
            learning_rate=0.03,
            scale_pos_weight=len(y_train[y_train == 0]) / max(len(y_train[y_train == 1]), 1),
            use_label_encoder=False,
            eval_metric="aucpr",
            random_state=42,
        )
        model.fit(X_train, y_train, verbose=False)

        y_proba = model.predict_proba(X_test)[:, 1]
        y_pred = model.predict(X_test)

        logger.info("IEEE-CIS XGBoost results:")
        logger.info("\n%s", classification_report(y_test, y_pred))
        logger.info("ROC-AUC: %.4f", roc_auc_score(y_test, y_proba))
        logger.info("PR-AUC:  %.4f", average_precision_score(y_test, y_proba))

        with open("ml_models/fraud_ieee_xgb.pkl", "wb") as f:
            pickle.dump(model, f)
        logger.info("Saved ml_models/fraud_ieee_xgb.pkl")

        # MLflow (optional)
        try:
            import mlflow
            mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", ""))
            MLFLOW_AVAILABLE = True
        except ImportError:
            MLFLOW_AVAILABLE = False
        if MLFLOW_AVAILABLE:
            try:
                mlflow.set_experiment("fraud-detection-ieee")
                with mlflow.start_run(run_name="ieee-xgb"):
                    mlflow.log_params(model.get_params())
                    mlflow.log_metric("roc_auc", roc_auc_score(y_test, y_proba))
                    mlflow.log_metric("pr_auc", average_precision_score(y_test, y_proba))
                    mlflow.xgboost.log_model(
                        model, "model", registered_model_name="fraud-ieee-xgb"
                    )
                logger.info("Logged IEEE model to MLflow")
            except Exception as exc:
                logger.warning("MLflow logging failed: %s", exc)

    except ImportError:
        logger.error("xgboost not installed")


if __name__ == "__main__":
    train()
