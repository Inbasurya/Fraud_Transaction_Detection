"""CLI entrypoint for training the production fraud model."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from app.ml_models.kaggle_fraud_model import kaggle_model

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def main(data_path: str | None = None, output_dir: str | None = None) -> dict:
    if output_dir:
        target = Path(output_dir)
        target.mkdir(parents=True, exist_ok=True)

    metrics = kaggle_model.retrain(data_path)
    if output_dir:
        metrics_path = Path(output_dir) / "training_metrics.json"
        metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train the fraud detection ensemble")
    parser.add_argument("--data", default=None, help="Optional path to a training CSV file")
    parser.add_argument("--output", default="app/ml/models", help="Directory to store auxiliary outputs")
    args = parser.parse_args()

    payload = main(args.data, args.output)
    print(json.dumps(payload, indent=2))
