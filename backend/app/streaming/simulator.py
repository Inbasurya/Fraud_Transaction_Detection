"""Transaction streaming simulator — sends synthetic bank transactions to the backend.

Supports two modes:
  1. Kaggle CSV  — load a real dataset and replay rows
  2. Synthetic   — generate random bank-style transactions

Usage:
  python -m app.streaming.simulator --mode synthetic --tps 1
  python -m app.streaming.simulator --mode kaggle --csv /path/to/creditcard.csv --tps 1
"""

import time
import random
import math
import os
import requests
from datetime import datetime, timedelta
from typing import Optional

API_URL = os.getenv("API_URL", "http://localhost:8000/transaction/simulate")

MERCHANTS = [
    "Amazon", "Flipkart", "Walmart", "Uber", "Netflix",
    "Apple Store", "Starbucks", "Shell Gas", "Delta Airlines",
    "Zara", "Nike", "Google Play", "Steam", "Spotify",
]
LOCATIONS = [
    "New York", "Chennai", "London", "Mumbai", "Tokyo",
    "Dubai", "Sydney", "Berlin", "Toronto", "Singapore",
]
DEVICES = ["mobile", "desktop", "tablet", "smartwatch"]
USER_POOL = list(range(1, 101))  # 100 simulated users


def _generate_synthetic_transaction(idx: int) -> dict:
    user_id = random.choice(USER_POOL)

    # Occasionally inject suspicious patterns
    is_anomaly = random.random() < 0.08
    if is_anomaly:
        amount = round(random.uniform(5000, 25000), 2)
        hour_offset = random.randint(1, 4)  # 1-4 AM
    else:
        amount = round(random.uniform(5, 3000), 2)
        hour_offset = random.randint(6, 23)

    ts = datetime.utcnow().replace(hour=hour_offset % 24, minute=random.randint(0, 59))

    return {
        "transaction_id": f"TX{10000000 + idx}",
        "user_id": user_id,
        "amount": amount,
        "merchant": random.choice(MERCHANTS),
        "location": random.choice(LOCATIONS),
        "device_type": random.choice(DEVICES),
        "timestamp": ts.isoformat(),
    }


def _load_kaggle(csv_path: str):
    import pandas as pd

    df = pd.read_csv(csv_path)
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)
    return df


def _kaggle_row_to_tx(row, idx: int) -> dict:
    amount = float(row.get("Amount", row.get("amount", random.uniform(10, 5000))))
    return {
        "transaction_id": f"KG{10000000 + idx}",
        "user_id": random.choice(USER_POOL),
        "amount": round(amount, 2),
        "merchant": random.choice(MERCHANTS),
        "location": random.choice(LOCATIONS),
        "device_type": random.choice(DEVICES),
        "timestamp": datetime.utcnow().isoformat(),
    }


def run_simulation(
    mode: str = "synthetic",
    csv_path: Optional[str] = None,
    tps: float = 1.0,
    count: Optional[int] = None,
):
    delay = 1.0 / max(tps, 0.1)
    sent = 0

    if mode == "kaggle" and csv_path:
        df = _load_kaggle(csv_path)
        total = len(df)
        for idx, (_, row) in enumerate(df.iterrows()):
            if count is not None and sent >= count:
                break
            tx = _kaggle_row_to_tx(row, idx)
            _send(tx, sent)
            sent += 1
            time.sleep(delay)
    else:
        while count is None or sent < count:
            tx = _generate_synthetic_transaction(sent)
            _send(tx, sent)
            sent += 1
            time.sleep(delay)

    print(f"\nSimulation complete — sent {sent} transactions.")


def _send(tx: dict, idx: int):
    try:
        resp = requests.post(API_URL, json=tx, timeout=10)
        data = resp.json()
        cat = data.get("risk_category", "?")
        score = data.get("risk_score", 0)
        symbol = {"SAFE": "✅", "SUSPICIOUS": "⚠️", "FRAUD": "🚨"}.get(cat, "❓")
        print(
            f"[{idx:>5}] {symbol} {tx['transaction_id']}  "
            f"${tx['amount']:>10,.2f}  {cat:<12} score={score:.4f}"
        )
    except Exception as e:
        print(f"[{idx:>5}] ❌ Error: {e}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Transaction streaming simulator")
    parser.add_argument("--mode", choices=["synthetic", "kaggle"], default="synthetic")
    parser.add_argument("--csv", type=str, help="Path to Kaggle CSV (for kaggle mode)")
    parser.add_argument("--tps", type=float, default=1.0, help="Transactions per second")
    parser.add_argument("--count", type=int, help="Number of transactions (omit for infinite)")
    args = parser.parse_args()

    run_simulation(mode=args.mode, csv_path=args.csv, tps=args.tps, count=args.count)
