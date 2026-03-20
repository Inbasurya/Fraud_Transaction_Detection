#!/usr/bin/env python3
"""
transaction_streamer.py
───────────────────────
Reads the generated CSV and streams one transaction per second to the
FastAPI fraud monitoring backend via POST /transaction/simulate.

Usage:
    python data/transaction_streamer.py
    python data/transaction_streamer.py --csv data/bank_transactions_20000.csv --rate 1
"""

import argparse
import os
import sys
import time
from pathlib import Path

import pandas as pd
import requests

DEFAULT_CSV = Path(__file__).resolve().parent / "bank_transactions_20000.csv"
API_URL = os.getenv("API_URL", "http://localhost:8000/transaction/simulate")


def stream(csv_path: str, api_url: str, rate: float):
    """Stream transactions from CSV to the FastAPI backend."""
    csv_file = Path(csv_path)
    if not csv_file.exists():
        print(f"Error: CSV not found → {csv_file}")
        print("Generate it first:")
        print("  python data/bank_transaction_generator.py --rows 20000")
        sys.exit(1)

    df = pd.read_csv(csv_file, parse_dates=["timestamp"])
    total = len(df)
    delay = 1.0 / rate if rate > 0 else 1.0

    print(f"Streaming {total:,} transactions → {api_url}")
    print(f"Rate: {rate} tx/sec")
    print("─" * 50)

    sent = 0
    errors = 0

    try:
        for _, row in df.iterrows():
            payload = {
                "transaction_id": str(row["transaction_id"]),
                "user_id": int(row["user_id"]),
                "amount": float(row["amount"]),
                "merchant": str(row["merchant"]),
                "location": str(row["location"]),
                "device_type": str(row["device_type"]),
                "timestamp": str(row["timestamp"]),
            }

            try:
                resp = requests.post(api_url, json=payload, timeout=10)
                status = resp.status_code

                if status in (200, 201):
                    data = resp.json()
                    risk = data.get("risk_category", "SAFE")
                    tag = {"FRAUD": "🚨", "SUSPICIOUS": "⚠️ ", "SAFE": "✅"}.get(risk, "  ")
                    print(f"Sent {payload['transaction_id']} → status {status}  {tag} {risk}")
                else:
                    print(f"Sent {payload['transaction_id']} → status {status}  (unexpected)")
                    errors += 1

            except requests.exceptions.ConnectionError:
                errors += 1
                if errors <= 3:
                    print(f"Connection error — is the backend running at {api_url}?")
                if errors >= 10:
                    print("Too many connection errors. Aborting.")
                    sys.exit(1)
            except requests.exceptions.Timeout:
                errors += 1
                print(f"Timeout sending {payload['transaction_id']}")

            sent += 1
            time.sleep(delay)

    except KeyboardInterrupt:
        pass

    print("\n" + "═" * 50)
    print(f"Done — Sent: {sent:,} | Errors: {errors}")
    print("═" * 50)


def main():
    parser = argparse.ArgumentParser(description="Stream transactions to FastAPI backend")
    parser.add_argument("--csv", type=str, default=str(DEFAULT_CSV), help="Path to CSV dataset")
    parser.add_argument("--api", type=str, default=API_URL, help="Backend API URL")
    parser.add_argument("--rate", type=float, default=1.0, help="Transactions per second (default: 1)")
    args = parser.parse_args()

    stream(csv_path=args.csv, api_url=args.api, rate=args.rate)


if __name__ == "__main__":
    main()
