#!/usr/bin/env python3
"""
bank_transaction_generator.py
─────────────────────────────
Generates a realistic synthetic bank transaction dataset for the
AI-Powered Fraud Monitoring System.

Usage:
    python data/bank_transaction_generator.py --rows 20000
"""

import argparse
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# ── Constants ─────────────────────────────────────────────────────────────────

MERCHANTS = [
    "Amazon", "Walmart", "Starbucks", "Apple Store", "Netflix",
    "Uber", "Shell Gas", "Zara", "McDonald's", "Best Buy",
    "Emirates", "Marriott", "Spotify", "Nike", "Whole Foods",
    "Quick Cash LLC", "Crypto Exchange X", "Offshore Trading",
]

LOCATIONS = ["NYC", "London", "Berlin", "Dubai", "Mumbai", "Singapore"]

DEVICES = ["mobile", "web", "tablet", "atm"]


def generate_dataset(n_rows: int = 20_000, n_users: int = 1_000, seed: int = 42) -> pd.DataFrame:
    """Generate synthetic bank transactions with ~4 % fraud ratio."""
    rng = np.random.default_rng(seed)

    fraud_ratio = 0.04
    n_fraud = int(n_rows * fraud_ratio)
    n_normal = n_rows - n_fraud

    base_time = datetime(2025, 1, 1)

    # ── Normal transactions (log-normal amounts) ─────────────────────────
    normal_amounts = np.round(np.exp(rng.normal(loc=3.5, scale=0.8, size=n_normal)), 2)
    normal_amounts = np.clip(normal_amounts, 1.0, 999.0)

    # ── Fraud transactions (larger amounts 1000–5000) ────────────────────
    fraud_amounts = np.round(rng.uniform(1000, 5000, size=n_fraud), 2)

    amounts = np.concatenate([normal_amounts, fraud_amounts])
    is_fraud = np.concatenate([np.zeros(n_normal, dtype=int), np.ones(n_fraud, dtype=int)])

    # Shuffle together
    idx = rng.permutation(n_rows)
    amounts = amounts[idx]
    is_fraud = is_fraud[idx]

    # ── Build remaining columns ──────────────────────────────────────────
    transaction_ids = [f"TX{uuid.uuid4().hex[:8].upper()}" for _ in range(n_rows)]
    user_ids = rng.integers(1, n_users + 1, size=n_rows)
    merchants = rng.choice(MERCHANTS, size=n_rows)
    locations = rng.choice(LOCATIONS, size=n_rows)
    devices = rng.choice(DEVICES, size=n_rows)

    # Spread timestamps over 30 days
    offsets = rng.integers(0, 30 * 24 * 3600, size=n_rows)
    timestamps = [base_time + timedelta(seconds=int(o)) for o in sorted(offsets)]

    df = pd.DataFrame({
        "transaction_id": transaction_ids,
        "user_id": user_ids,
        "amount": amounts,
        "merchant": merchants,
        "location": locations,
        "device_type": devices,
        "timestamp": timestamps,
        "is_fraud": is_fraud,
    })

    return df


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic bank transaction dataset")
    parser.add_argument("--rows", type=int, default=20_000, help="Number of rows (default: 20000)")
    parser.add_argument("--users", type=int, default=1_000, help="Number of users (default: 1000)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--output", type=str, default=None, help="Output CSV path")
    args = parser.parse_args()

    df = generate_dataset(n_rows=args.rows, n_users=args.users, seed=args.seed)

    out_path = args.output or str(Path(__file__).resolve().parent / f"bank_transactions_{args.rows}.csv")
    df.to_csv(out_path, index=False)

    fraud_count = int(df["is_fraud"].sum())
    total = len(df)
    print(f"Dataset generated: {out_path}")
    print(f"  Rows:       {total:,}")
    print(f"  Users:      {args.users:,}")
    print(f"  Fraud:      {fraud_count:,} ({fraud_count / total:.1%})")
    print(f"  Normal:     {total - fraud_count:,}")
    print(f"  Amount avg: ${df['amount'].mean():.2f}")


if __name__ == "__main__":
    main()
