import logging
import joblib
import numpy as np

from sklearn.ensemble import IsolationForest
from app.ml.preprocessing import prepare_training_data

logging.basicConfig(level=logging.INFO)


MODEL_PATH = "app/ml/models/anomaly_model.pkl"


def train_anomaly_model(data_path):

    logging.info("Loading dataset...")

    X_train, X_test, y_train, y_test, scaler = prepare_training_data(data_path)

    logging.info("Selecting normal transactions for training...")

    X_normal = X_train[y_train == 0]

    logging.info("Training Isolation Forest anomaly detector...")

    model = IsolationForest(
        n_estimators=200,
        contamination=0.002,
        random_state=42,
        n_jobs=-1
    )

    model.fit(X_normal)

    logging.info("Saving anomaly detection model...")

    joblib.dump(model, MODEL_PATH)

    logging.info("Model saved to %s", MODEL_PATH)


if __name__ == "__main__":

    DATA_PATH = "app/ml/data/creditcard.csv"

    train_anomaly_model(DATA_PATH)