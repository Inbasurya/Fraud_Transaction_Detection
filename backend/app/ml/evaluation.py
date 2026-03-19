import os
import logging

import pandas as pd
import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier

from sklearn.metrics import (
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
)

from app.ml.preprocessing import prepare_training_data

# configure simple logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


# ---------------------------------------------------------------------------
# evaluation helpers
# ---------------------------------------------------------------------------

def evaluate_model(name, y_true, y_pred, y_score=None) -> dict:
    """Compute standard classification metrics for a single model.

    Returns a dictionary containing precision, recall, f1 score and ROC AUC.
    The returned dict also includes the model name under the `Model` key so
    it can be directly appended to a dataframe.
    """
    result = {
        "Model": name,
        "Precision": precision_score(y_true, y_pred, zero_division=0),
        "Recall": recall_score(y_true, y_pred, zero_division=0),
        "F1": f1_score(y_true, y_pred, zero_division=0),
    }

    if y_score is not None:
        try:
            result["ROC_AUC"] = roc_auc_score(y_true, y_score)
        except Exception:
            result["ROC_AUC"] = None
    else:
        result["ROC_AUC"] = None

    return result


# ---------------------------------------------------------------------------
# driver
# ---------------------------------------------------------------------------

def run_evaluation(data_path: str):
    """Load data, models and compute evaluation summary for all configured
    detectors.
    """
    # load and split data using existing preprocessing pipeline
    logging.info("Preparing training data...")
    X_train, X_test, y_train, y_test, scaler = prepare_training_data(data_path)

    # baseline classifiers trained on the fly for comparison
    logging.info("Training baseline classifiers (LR & RF)...")
    lr_model = LogisticRegression(max_iter=1000, random_state=42)
    lr_model.fit(X_train, y_train)
    rf_model = RandomForestClassifier(n_estimators=100, random_state=42)
    rf_model.fit(X_train, y_train)

    # load previously trained XGBoost model and the isolation forest anomaly model
    logging.info("Loading persisted models...")
    ml_model = joblib.load("app/ml/models/fraud_model.pkl")
    anomaly_model = joblib.load("app/ml/models/anomaly_model.pkl")

    results = []

    # evaluate logistic regression
    logging.info("Evaluating Logistic Regression...")
    y_pred = lr_model.predict(X_test)
    y_score = lr_model.predict_proba(X_test)[:, 1] if hasattr(lr_model, "predict_proba") else None
    results.append(evaluate_model("Logistic Regression", y_test, y_pred, y_score))

    # evaluate random forest
    logging.info("Evaluating Random Forest...")
    y_pred = rf_model.predict(X_test)
    y_score = rf_model.predict_proba(X_test)[:, 1] if hasattr(rf_model, "predict_proba") else None
    results.append(evaluate_model("Random Forest", y_test, y_pred, y_score))

    # evaluate XGBoost
    logging.info("Evaluating XGBoost (fraud_model.pkl)...")
    y_pred = ml_model.predict(X_test)
    y_score = ml_model.predict_proba(X_test)[:, 1] if hasattr(ml_model, "predict_proba") else None
    results.append(evaluate_model("XGBoost", y_test, y_pred, y_score))

    # anomaly detection with Isolation Forest
    logging.info("Computing anomaly predictions (Isolation Forest)...")
    scores = -anomaly_model.score_samples(X_test)
    scores = (scores - scores.min()) / (scores.max() - scores.min())
    y_pred_anom = (scores > 0.5).astype(int)
    results.append(evaluate_model("Isolation Forest", y_test, y_pred_anom, scores))

    # hybrid model: weighted combination of ML probability and anomaly score
    logging.info("Evaluating hybrid ML + anomaly model...")
    ml_probs = y_score if y_score is not None else ml_model.predict_proba(X_test)[:, 1]
    hybrid_score = 0.7 * ml_probs + 0.3 * scores
    y_pred_hybrid = (hybrid_score > 0.5).astype(int)
    results.append(evaluate_model("Hybrid Model", y_test, y_pred_hybrid, hybrid_score))

    # assemble results dataframe and persist
    df = pd.DataFrame(results)
    os.makedirs("results", exist_ok=True)
    df.to_csv("results/model_comparison.csv", index=False)

    # print human readable summary
    print("\nModel Evaluation Results\n")
    for r in results:
        print(f"{r['Model']:20} ROC-AUC: {r.get('ROC_AUC', 0):.4f}")

    return df, results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate fraud detection models")
    parser.add_argument("--data", required=True, help="Path to dataset CSV")
    args = parser.parse_args()

    run_evaluation(args.data)
