#!/usr/bin/env python3
"""
bank_transaction_generator.py
─────────────────────────────
Generates a realistic synthetic bank‑transaction dataset (20 000+ rows) with
normal and fraudulent transactions for an AI fraud detection monitoring system.

Usage
─────
  # Generate 20 000 rows → data/bank_transactions_20000.csv
  python data/bank_transaction_generator.py --rows 20000

  # Generate and insert into PostgreSQL
  python data/bank_transaction_generator.py --rows 20000 --export-postgres

  # Custom seed / fraud ratio
  python data/bank_transaction_generator.py --rows 25000 --fraud-ratio 0.04 --seed 99
"""

from __future__ import annotations

import argparse
import hashlib
import math
import os
import random
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd

# ─── Constants ────────────────────────────────────────────────────────────────

CITIES = [
    ("New York", "US"),
    ("Los Angeles", "US"),
    ("Chicago", "US"),
    ("London", "UK"),
    ("Berlin", "DE"),
    ("Paris", "FR"),
    ("Singapore", "SG"),
    ("Dubai", "AE"),
    ("Mumbai", "IN"),
    ("Chennai", "IN"),
    ("Tokyo", "JP"),
    ("Sydney", "AU"),
    ("Toronto", "CA"),
    ("São Paulo", "BR"),
    ("Moscow", "RU"),
    ("Lagos", "NG"),
    ("Seoul", "KR"),
    ("Bangkok", "TH"),
]

# Rough lat/lon for distance computation
CITY_COORDS = {
    "New York": (40.71, -74.01),
    "Los Angeles": (34.05, -118.24),
    "Chicago": (41.88, -87.63),
    "London": (51.51, -0.13),
    "Berlin": (52.52, 13.41),
    "Paris": (48.86, 2.35),
    "Singapore": (1.35, 103.82),
    "Dubai": (25.20, 55.27),
    "Mumbai": (19.08, 72.88),
    "Chennai": (13.08, 80.27),
    "Tokyo": (35.68, 139.69),
    "Sydney": (-33.87, 151.21),
    "Toronto": (43.65, -79.38),
    "São Paulo": (-23.55, -46.63),
    "Moscow": (55.76, 37.62),
    "Lagos": (6.52, 3.38),
    "Seoul": (37.57, 126.98),
    "Bangkok": (13.76, 100.50),
}

MERCHANT_CATEGORIES = {
    "grocery": ["Whole Foods", "Trader Joe's", "Walmart Grocery", "Tesco", "Reliance Fresh"],
    "restaurant": ["McDonald's", "Starbucks", "Subway", "Pizza Hut", "Domino's"],
    "electronics": ["Best Buy", "Apple Store", "Samsung Store", "Micro Center", "Croma"],
    "travel": ["Delta Airlines", "Emirates", "United Airlines", "Marriott", "Airbnb"],
    "fuel": ["Shell Gas", "BP", "Chevron", "Indian Oil", "Exxon"],
    "entertainment": ["Netflix", "Spotify", "Steam", "Disney+", "AMC Theatres"],
    "fashion": ["Zara", "H&M", "Nike", "Adidas", "Gucci"],
    "ecommerce": ["Amazon", "Flipkart", "eBay", "Alibaba", "Etsy"],
    "utility": ["Electric Co.", "Water Works", "Internet ISP", "Phone Carrier", "Gas Utility"],
    "suspicious": ["Crypto Exchange X", "Offshore Trading", "Casino Intl", "Quick Cash LLC", "VPN Pay"],
}

DEVICES = ["mobile", "web", "tablet", "atm"]

CURRENCIES = ["USD", "EUR", "GBP", "INR", "SGD", "AED", "JPY", "AUD", "CAD", "BRL"]


# ─── User profile model ──────────────────────────────────────────────────────

@dataclass
class UserProfile:
    user_id: str
    account_id: str
    avg_spend: float                   # mean daily spend
    spend_std: float                   # std deviation of amounts
    home_city: str
    home_country: str
    preferred_device: str
    currency: str
    common_categories: list = field(default_factory=list)
    common_merchants: list = field(default_factory=list)


def _generate_users(n_users: int, rng: np.random.Generator) -> List[UserProfile]:
    """Create n_users with varied spending profiles."""
    users: List[UserProfile] = []
    for i in range(1, n_users + 1):
        city, country = CITIES[rng.integers(0, len(CITIES))]
        # Log‑normal baseline spend
        avg = float(np.exp(rng.normal(3.5, 0.9)))  # median ≈ $33, range $5–$2000
        avg = round(max(5.0, min(avg, 3000.0)), 2)
        std = round(avg * rng.uniform(0.2, 0.6), 2)

        cats = rng.choice(
            [c for c in MERCHANT_CATEGORIES if c != "suspicious"],
            size=rng.integers(2, 5),
            replace=False,
        ).tolist()
        merchants = []
        for c in cats:
            merchants.extend(rng.choice(MERCHANT_CATEGORIES[c], size=min(2, len(MERCHANT_CATEGORIES[c])), replace=False).tolist())

        users.append(UserProfile(
            user_id=f"U{i:04d}",
            account_id=f"ACC{100000 + i}",
            avg_spend=avg,
            spend_std=std,
            home_city=city,
            home_country=country,
            preferred_device=rng.choice(DEVICES),
            currency=rng.choice(CURRENCIES),
            common_categories=cats,
            common_merchants=merchants,
        ))
    return users


# ─── Geo helpers ──────────────────────────────────────────────────────────────

def _haversine_km(c1: str, c2: str) -> float:
    """Approximate distance in km between two city names."""
    p1 = CITY_COORDS.get(c1, (0, 0))
    p2 = CITY_COORDS.get(c2, (0, 0))
    lat1, lon1 = math.radians(p1[0]), math.radians(p1[1])
    lat2, lon2 = math.radians(p2[0]), math.radians(p2[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))


def _random_ip(rng: np.random.Generator) -> str:
    return f"{rng.integers(10,224)}.{rng.integers(0,256)}.{rng.integers(0,256)}.{rng.integers(1,255)}"


# ─── Normal transaction generation ───────────────────────────────────────────

def _generate_normal_tx(
    idx: int,
    user: UserProfile,
    base_time: datetime,
    rng: np.random.Generator,
    last_city: str,
    last_device: str,
) -> dict:
    """Generate a single normal (non‑fraud) transaction."""

    # Amount: log‑normal centered around user's avg_spend
    amount = float(np.exp(rng.normal(np.log(max(user.avg_spend, 1)), 0.4)))
    amount = round(max(0.50, min(amount, user.avg_spend * 4)), 2)

    # Timestamp: jitter within ±6 hours, mostly daytime
    hour = int(rng.normal(13, 4)) % 24  # peak around 1 PM
    if hour < 0:
        hour += 24
    minute = rng.integers(0, 60)
    day_offset = rng.integers(0, 30)
    ts = base_time + timedelta(days=int(day_offset), hours=hour, minutes=int(minute))

    # City: 85 % home city, 15 % nearby
    if rng.random() < 0.85:
        city, country = user.home_city, user.home_country
    else:
        city, country = CITIES[rng.integers(0, len(CITIES))]

    # Device: 80 % preferred
    device = user.preferred_device if rng.random() < 0.80 else rng.choice(DEVICES)

    # Merchant
    cat = rng.choice(user.common_categories)
    merchant = rng.choice(MERCHANT_CATEGORIES[cat])

    location_change = round(_haversine_km(last_city, city), 1)
    device_change = 0 if device == last_device else 1

    return {
        "transaction_id": f"TX{idx:07d}",
        "user_id": user.user_id,
        "account_id": user.account_id,
        "amount": amount,
        "currency": user.currency,
        "merchant": merchant,
        "merchant_category": cat,
        "location_city": city,
        "location_country": country,
        "device_type": device,
        "ip_address": _random_ip(rng),
        "timestamp": ts,
        "avg_user_spend": user.avg_spend,
        "transaction_velocity": 0,  # filled later per‑user
        "is_foreign_transaction": int(country != user.home_country),
        "device_change": device_change,
        "location_change": location_change,
        "unusual_time": int(1 <= hour <= 4),
        "is_fraud": 0,
        "fraud_type": "none",
    }


# ─── Fraud injection ─────────────────────────────────────────────────────────

def _inject_card_theft(
    idx: int,
    user: UserProfile,
    base_time: datetime,
    rng: np.random.Generator,
) -> dict:
    """Fraud type A – card stolen: large amount, foreign, new device, unusual merchant."""
    amount = round(float(rng.uniform(user.avg_spend * 5, user.avg_spend * 20)), 2)
    amount = max(amount, 500.0)
    foreign_cities = [(c, co) for c, co in CITIES if co != user.home_country]
    city, country = foreign_cities[rng.integers(0, len(foreign_cities))]
    device = rng.choice([d for d in DEVICES if d != user.preferred_device])
    cat = "suspicious"
    merchant = rng.choice(MERCHANT_CATEGORIES[cat])
    hour = rng.integers(0, 24)
    ts = base_time + timedelta(days=int(rng.integers(0, 30)), hours=int(hour), minutes=int(rng.integers(0, 60)))

    return {
        "transaction_id": f"TX{idx:07d}",
        "user_id": user.user_id,
        "account_id": user.account_id,
        "amount": amount,
        "currency": user.currency,
        "merchant": merchant,
        "merchant_category": cat,
        "location_city": city,
        "location_country": country,
        "device_type": device,
        "ip_address": _random_ip(rng),
        "timestamp": ts,
        "avg_user_spend": user.avg_spend,
        "transaction_velocity": 0,
        "is_foreign_transaction": 1,
        "device_change": 1,
        "location_change": round(_haversine_km(user.home_city, city), 1),
        "unusual_time": int(1 <= hour <= 4),
        "is_fraud": 1,
        "fraud_type": "card_theft",
    }


def _inject_velocity_fraud(
    start_idx: int,
    user: UserProfile,
    base_time: datetime,
    rng: np.random.Generator,
) -> List[dict]:
    """Fraud type B – rapid-fire burst: 5‑10 txs within seconds, escalating amounts."""
    burst_size = int(rng.integers(5, 11))
    ts = base_time + timedelta(days=int(rng.integers(0, 30)), hours=int(rng.integers(0, 24)))
    rows = []
    for j in range(burst_size):
        amount = round(float(user.avg_spend * (2 + j * rng.uniform(0.5, 1.5))), 2)
        rows.append({
            "transaction_id": f"TX{start_idx + j:07d}",
            "user_id": user.user_id,
            "account_id": user.account_id,
            "amount": amount,
            "currency": user.currency,
            "merchant": rng.choice(MERCHANT_CATEGORIES["ecommerce"]),
            "merchant_category": "ecommerce",
            "location_city": user.home_city,
            "location_country": user.home_country,
            "device_type": user.preferred_device,
            "ip_address": _random_ip(rng),
            "timestamp": ts + timedelta(seconds=int(j * rng.integers(1, 5))),
            "avg_user_spend": user.avg_spend,
            "transaction_velocity": burst_size,
            "is_foreign_transaction": 0,
            "device_change": 0,
            "location_change": 0.0,
            "unusual_time": int(1 <= ts.hour <= 4),
            "is_fraud": 1,
            "fraud_type": "velocity_fraud",
        })
    return rows


def _inject_account_takeover(
    idx: int,
    user: UserProfile,
    base_time: datetime,
    rng: np.random.Generator,
) -> dict:
    """Fraud type C – account takeover: device change, location jump, 1‑4 AM."""
    foreign_cities = [(c, co) for c, co in CITIES if co != user.home_country]
    city, country = foreign_cities[rng.integers(0, len(foreign_cities))]
    device = rng.choice([d for d in DEVICES if d != user.preferred_device])
    hour = int(rng.integers(1, 5))
    amount = round(float(rng.uniform(user.avg_spend * 3, user.avg_spend * 10)), 2)
    ts = base_time + timedelta(days=int(rng.integers(0, 30)), hours=hour, minutes=int(rng.integers(0, 60)))

    cat = rng.choice(user.common_categories)
    return {
        "transaction_id": f"TX{idx:07d}",
        "user_id": user.user_id,
        "account_id": user.account_id,
        "amount": amount,
        "currency": user.currency,
        "merchant": rng.choice(MERCHANT_CATEGORIES[cat]),
        "merchant_category": cat,
        "location_city": city,
        "location_country": country,
        "device_type": device,
        "ip_address": _random_ip(rng),
        "timestamp": ts,
        "avg_user_spend": user.avg_spend,
        "transaction_velocity": 0,
        "is_foreign_transaction": 1,
        "device_change": 1,
        "location_change": round(_haversine_km(user.home_city, city), 1),
        "unusual_time": 1,
        "is_fraud": 1,
        "fraud_type": "account_takeover",
    }


def _inject_merchant_fraud(
    idx: int,
    user: UserProfile,
    base_time: datetime,
    rng: np.random.Generator,
) -> dict:
    """Fraud type D – suspicious merchant: high‑value purchase at dodgy merchant."""
    cat = "suspicious"
    merchant = rng.choice(MERCHANT_CATEGORIES[cat])
    amount = round(float(rng.uniform(1000, 15000)), 2)
    hour = int(rng.integers(0, 24))
    ts = base_time + timedelta(days=int(rng.integers(0, 30)), hours=hour, minutes=int(rng.integers(0, 60)))

    return {
        "transaction_id": f"TX{idx:07d}",
        "user_id": user.user_id,
        "account_id": user.account_id,
        "amount": amount,
        "currency": user.currency,
        "merchant": merchant,
        "merchant_category": cat,
        "location_city": user.home_city,
        "location_country": user.home_country,
        "device_type": user.preferred_device,
        "ip_address": _random_ip(rng),
        "timestamp": ts,
        "avg_user_spend": user.avg_spend,
        "transaction_velocity": 0,
        "is_foreign_transaction": 0,
        "device_change": 0,
        "location_change": 0.0,
        "unusual_time": int(1 <= hour <= 4),
        "is_fraud": 1,
        "fraud_type": "merchant_fraud",
    }


def _inject_card_testing_attack(
    start_idx: int,
    user: UserProfile,
    base_time: datetime,
    rng: np.random.Generator,
) -> List[dict]:
    """Fraud type E – card testing attack: many tiny tx followed by one larger hit."""
    burst = []
    ts = base_time + timedelta(days=int(rng.integers(0, 30)), hours=int(rng.integers(0, 24)))
    merchant = rng.choice(MERCHANT_CATEGORIES["ecommerce"])
    for j in range(6):
        is_final = j == 5
        amount = round(float(rng.uniform(1.0, 12.0) if not is_final else rng.uniform(200, 1500)), 2)
        burst.append({
            "transaction_id": f"TX{start_idx + j:07d}",
            "user_id": user.user_id,
            "account_id": user.account_id,
            "amount": amount,
            "currency": user.currency,
            "merchant": merchant,
            "merchant_category": "ecommerce",
            "location_city": user.home_city,
            "location_country": user.home_country,
            "device_type": user.preferred_device,
            "ip_address": _random_ip(rng),
            "timestamp": ts + timedelta(seconds=int(j * rng.integers(5, 20))),
            "avg_user_spend": user.avg_spend,
            "transaction_velocity": 6,
            "is_foreign_transaction": 0,
            "device_change": 0,
            "location_change": 0.0,
            "unusual_time": int(1 <= ts.hour <= 4),
            "is_fraud": 1,
            "fraud_type": "card_testing_attack",
        })
    return burst


def _inject_device_switching_fraud(
    idx: int,
    user: UserProfile,
    base_time: datetime,
    rng: np.random.Generator,
) -> dict:
    device = rng.choice([d for d in DEVICES if d != user.preferred_device])
    ts = base_time + timedelta(days=int(rng.integers(0, 30)), hours=int(rng.integers(0, 24)))
    return {
        "transaction_id": f"TX{idx:07d}",
        "user_id": user.user_id,
        "account_id": user.account_id,
        "amount": round(float(rng.uniform(user.avg_spend * 2.5, user.avg_spend * 8)), 2),
        "currency": user.currency,
        "merchant": rng.choice(MERCHANT_CATEGORIES["electronics"]),
        "merchant_category": "electronics",
        "location_city": user.home_city,
        "location_country": user.home_country,
        "device_type": device,
        "ip_address": _random_ip(rng),
        "timestamp": ts,
        "avg_user_spend": user.avg_spend,
        "transaction_velocity": 0,
        "is_foreign_transaction": 0,
        "device_change": 1,
        "location_change": 0.0,
        "unusual_time": int(1 <= ts.hour <= 4),
        "is_fraud": 1,
        "fraud_type": "device_switching",
    }


def _inject_location_jump_fraud(
    idx: int,
    user: UserProfile,
    base_time: datetime,
    rng: np.random.Generator,
) -> dict:
    foreign = [(c, co) for c, co in CITIES if c != user.home_city]
    city, country = foreign[rng.integers(0, len(foreign))]
    ts = base_time + timedelta(days=int(rng.integers(0, 30)), hours=int(rng.integers(0, 24)))
    return {
        "transaction_id": f"TX{idx:07d}",
        "user_id": user.user_id,
        "account_id": user.account_id,
        "amount": round(float(rng.uniform(user.avg_spend * 3, user.avg_spend * 9)), 2),
        "currency": user.currency,
        "merchant": rng.choice(MERCHANT_CATEGORIES["travel"]),
        "merchant_category": "travel",
        "location_city": city,
        "location_country": country,
        "device_type": user.preferred_device,
        "ip_address": _random_ip(rng),
        "timestamp": ts,
        "avg_user_spend": user.avg_spend,
        "transaction_velocity": 0,
        "is_foreign_transaction": int(country != user.home_country),
        "device_change": 0,
        "location_change": round(_haversine_km(user.home_city, city), 1),
        "unusual_time": int(1 <= ts.hour <= 4),
        "is_fraud": 1,
        "fraud_type": "location_jump",
    }


def _inject_merchant_burst(
    start_idx: int,
    user: UserProfile,
    base_time: datetime,
    rng: np.random.Generator,
) -> List[dict]:
    burst_size = int(rng.integers(4, 9))
    merchant = rng.choice(MERCHANT_CATEGORIES["suspicious"])
    ts = base_time + timedelta(days=int(rng.integers(0, 30)), hours=int(rng.integers(0, 24)))
    rows = []
    for j in range(burst_size):
        rows.append({
            "transaction_id": f"TX{start_idx + j:07d}",
            "user_id": user.user_id,
            "account_id": user.account_id,
            "amount": round(float(rng.uniform(150, 2400)), 2),
            "currency": user.currency,
            "merchant": merchant,
            "merchant_category": "suspicious",
            "location_city": user.home_city,
            "location_country": user.home_country,
            "device_type": user.preferred_device,
            "ip_address": _random_ip(rng),
            "timestamp": ts + timedelta(minutes=j),
            "avg_user_spend": user.avg_spend,
            "transaction_velocity": burst_size,
            "is_foreign_transaction": 0,
            "device_change": 0,
            "location_change": 0.0,
            "unusual_time": int(1 <= ts.hour <= 4),
            "is_fraud": 1,
            "fraud_type": "merchant_burst",
        })
    return rows


# ─── Velocity post‑processing ────────────────────────────────────────────────

def _compute_velocity(df: pd.DataFrame) -> pd.DataFrame:
    """Compute per‑user rolling 1‑hour transaction velocity."""
    df = df.sort_values(["user_id", "timestamp"]).reset_index(drop=True)
    velocities = []
    for _, group in df.groupby("user_id"):
        times = group["timestamp"].values
        vel = []
        for i, t in enumerate(times):
            window_start = t - np.timedelta64(1, "h")
            count = int(np.sum((times >= window_start) & (times <= t)))
            vel.append(count)
        velocities.extend(vel)
    df["transaction_velocity"] = velocities
    return df


# ─── Main generation pipeline ────────────────────────────────────────────────

def generate_dataset(
    n_rows: int = 20000,
    n_users: int = 750,
    fraud_ratio: float = 0.04,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate the full synthetic dataset."""

    rng = np.random.default_rng(seed)
    random.seed(seed)

    print(f"Generating {n_rows:,} transactions for {n_users} users (fraud≈{fraud_ratio:.0%}) …")

    users = _generate_users(n_users, rng)
    user_map = {u.user_id: u for u in users}

    n_fraud_target = int(n_rows * fraud_ratio)
    n_normal = n_rows - n_fraud_target

    base_time = datetime(2025, 1, 1)
    rows: List[dict] = []
    idx = 1

    # ── Normal transactions ───────────────────────────────────────────────
    last_city = {u.user_id: u.home_city for u in users}
    last_device = {u.user_id: u.preferred_device for u in users}

    for _ in range(n_normal):
        user = users[rng.integers(0, len(users))]
        tx = _generate_normal_tx(idx, user, base_time, rng, last_city[user.user_id], last_device[user.user_id])
        last_city[user.user_id] = tx["location_city"]
        last_device[user.user_id] = tx["device_type"]
        rows.append(tx)
        idx += 1

    # ── Fraud transactions ────────────────────────────────────────────────
    fraud_types = [
        "card_theft",
        "velocity_fraud",
        "account_takeover",
        "merchant_fraud",
        "card_testing_attack",
        "device_switching",
        "location_jump",
        "merchant_burst",
    ]
    fraud_generated = 0

    while fraud_generated < n_fraud_target:
        user = users[rng.integers(0, len(users))]
        fraud_type = rng.choice(fraud_types)

        if fraud_type == "card_theft":
            rows.append(_inject_card_theft(idx, user, base_time, rng))
            idx += 1
            fraud_generated += 1

        elif fraud_type == "velocity_fraud":
            burst = _inject_velocity_fraud(idx, user, base_time, rng)
            rows.extend(burst)
            idx += len(burst)
            fraud_generated += len(burst)

        elif fraud_type == "account_takeover":
            rows.append(_inject_account_takeover(idx, user, base_time, rng))
            idx += 1
            fraud_generated += 1

        elif fraud_type == "merchant_fraud":
            rows.append(_inject_merchant_fraud(idx, user, base_time, rng))
            idx += 1
            fraud_generated += 1
        elif fraud_type == "card_testing_attack":
            burst = _inject_card_testing_attack(idx, user, base_time, rng)
            rows.extend(burst)
            idx += len(burst)
            fraud_generated += len(burst)
        elif fraud_type == "device_switching":
            rows.append(_inject_device_switching_fraud(idx, user, base_time, rng))
            idx += 1
            fraud_generated += 1
        elif fraud_type == "location_jump":
            rows.append(_inject_location_jump_fraud(idx, user, base_time, rng))
            idx += 1
            fraud_generated += 1
        elif fraud_type == "merchant_burst":
            burst = _inject_merchant_burst(idx, user, base_time, rng)
            rows.extend(burst)
            idx += len(burst)
            fraud_generated += len(burst)

    # ── Build DataFrame ───────────────────────────────────────────────────
    df = pd.DataFrame(rows)

    # Derived time features
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["transaction_hour"] = df["timestamp"].dt.hour
    df["is_weekend"] = df["timestamp"].dt.dayofweek.isin([5, 6]).astype(int)

    # Sort chronologically and recompute velocity
    df = _compute_velocity(df)

    # Shuffle to mix fraud/normal, then re‑sort by time
    df = df.sample(frac=1, random_state=seed).sort_values("timestamp").reset_index(drop=True)

    actual_fraud = df["is_fraud"].sum()
    total = len(df)
    print(f"Done — {total:,} rows | {actual_fraud:,} fraud ({actual_fraud/total:.2%})")
    print(f"Fraud breakdown:\n{df[df['is_fraud']==1]['fraud_type'].value_counts().to_string()}")

    return df


# ─── PostgreSQL export ────────────────────────────────────────────────────────

def export_to_postgres(df: pd.DataFrame, db_url: str):
    """Insert rows into the PostgreSQL 'transactions' table via SQLAlchemy."""
    from sqlalchemy import create_engine

    engine = create_engine(db_url)
    # Map to schema expected by the Transaction model
    export_df = df.rename(columns={
        "location_city": "location",
    })[["transaction_id", "user_id", "amount", "merchant", "location", "device_type", "timestamp"]].copy()

    # user_id is a string like U0042 — extract the int; the DB FK references users.id
    export_df["user_id"] = export_df["user_id"].str.replace("U", "").astype(int)

    export_df.to_sql("transactions", engine, if_exists="append", index=False, method="multi", chunksize=500)
    print(f"Exported {len(export_df)} rows to PostgreSQL table 'transactions'.")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate a synthetic bank‑transaction dataset for fraud detection."
    )
    parser.add_argument("--rows", type=int, default=20000, help="Number of transactions to generate (default: 20000)")
    parser.add_argument("--users", type=int, default=750, help="Number of simulated users (default: 750)")
    parser.add_argument("--fraud-ratio", type=float, default=0.04, help="Target fraud ratio 0‑1 (default: 0.04)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--output", type=str, default=None, help="Output CSV path (default: data/bank_transactions_<rows>.csv)")
    parser.add_argument("--export-postgres", action="store_true", help="Also insert into PostgreSQL")
    parser.add_argument("--db-url", type=str, default="postgresql://postgres:postgres@localhost:5432/frauddb",
                        help="PostgreSQL connection URL")
    args = parser.parse_args()

    df = generate_dataset(
        n_rows=args.rows,
        n_users=args.users,
        fraud_ratio=args.fraud_ratio,
        seed=args.seed,
    )

    out_path = args.output or str(Path(__file__).resolve().parent / f"bank_transactions_{args.rows}.csv")
    df.to_csv(out_path, index=False)
    print(f"Saved → {out_path}")

    if args.export_postgres:
        export_to_postgres(df, args.db_url)

    # Print sample
    print("\n── Sample rows ─────────────────────────────────────────")
    print(df.head(5).to_string(index=False))
    print("\n── Sample fraud row ────────────────────────────────────")
    fraud_rows = df[df["is_fraud"] == 1]
    if len(fraud_rows) > 0:
        print(fraud_rows.iloc[0].to_string())


if __name__ == "__main__":
    main()
