"""Behavioral feature engineering service.

Computes advanced features for real-time fraud detection:
  - amount_over_customer_avg
  - transaction_velocity
  - unusual_time_flag
  - location_change_flag
  - geo_distance (haversine)
  - device_change_flag
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models.transaction_model import Transaction
from app.models.customer_model import Customer
from app.models.device_model import Device


# ── City coordinate lookup (major banking cities) ─────────────────────
_CITY_COORDS: dict[str, tuple[float, float]] = {
    "new york": (40.7128, -74.0060),
    "los angeles": (34.0522, -118.2437),
    "chicago": (41.8781, -87.6298),
    "houston": (29.7604, -95.3698),
    "phoenix": (33.4484, -112.0740),
    "philadelphia": (39.9526, -75.1652),
    "san antonio": (29.4241, -98.4936),
    "san diego": (32.7157, -117.1611),
    "dallas": (32.7767, -96.7970),
    "san jose": (37.3382, -121.8863),
    "london": (51.5074, -0.1278),
    "tokyo": (35.6762, 139.6503),
    "dubai": (25.2048, 55.2708),
    "singapore": (1.3521, 103.8198),
    "mumbai": (19.0760, 72.8777),
    "berlin": (52.5200, 13.4050),
    "paris": (48.8566, 2.3522),
    "sydney": (-33.8688, 151.2093),
    "toronto": (43.6532, -79.3832),
    "sao paulo": (-23.5505, -46.6333),
    "lagos": (6.5244, 3.3792),
    "moscow": (55.7558, 37.6173),
    "shanghai": (31.2304, 121.4737),
    "beijing": (39.9042, 116.4074),
    "seoul": (37.5665, 126.9780),
    "miami": (25.7617, -80.1918),
    "atlanta": (33.7490, -84.3880),
    "boston": (42.3601, -71.0589),
    "seattle": (47.6062, -122.3321),
    "denver": (39.7392, -104.9903),
    "detroit": (42.3314, -83.0458),
    "minneapolis": (44.9778, -93.2650),
    "portland": (45.5152, -122.6784),
    "las vegas": (36.1699, -115.1398),
    "austin": (30.2672, -97.7431),
}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute distance between two lat/lon points in kilometres."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _lookup_coords(location: Optional[str]) -> Optional[tuple[float, float]]:
    if not location:
        return None
    return _CITY_COORDS.get(location.strip().lower())


def compute_behavioral_features(
    db: Session,
    tx: Transaction,
    customer: Optional[Customer] = None,
) -> dict:
    """Compute all behavioral features for a transaction.

    Returns a dict with:
      amount_over_customer_avg, transaction_velocity, unusual_time_flag,
      location_change_flag, geo_distance, device_change_flag, and more.
    """
    ts = tx.timestamp if isinstance(tx.timestamp, datetime) else datetime.fromisoformat(str(tx.timestamp))

    # ── Fetch customer profile ────────────────────────────────
    if customer is None:
        customer = (
            db.query(Customer)
            .filter(Customer.customer_id == str(tx.user_id))
            .first()
        )

    avg_amount = float(customer.avg_transaction_amount) if customer and customer.avg_transaction_amount else 0.0
    avg_amount = max(avg_amount, 1.0)

    # ── Recent history ────────────────────────────────────────
    history = (
        db.query(Transaction)
        .filter(Transaction.user_id == tx.user_id, Transaction.id != tx.id)
        .order_by(Transaction.timestamp.desc())
        .limit(200)
        .all()
    )
    last_tx = history[0] if history else None

    # ── Amount features ───────────────────────────────────────
    amount = float(tx.amount or 0.0)
    amount_over_customer_avg = amount / avg_amount

    # ── Transaction velocity (last hour) ──────────────────────
    one_hour_ago = ts - timedelta(hours=1)
    transaction_velocity = sum(
        1 for h in history if h.timestamp and h.timestamp >= one_hour_ago
    )

    # ── Time features ─────────────────────────────────────────
    unusual_time_flag = 1.0 if 0 <= ts.hour <= 5 else 0.0

    # ── Location change ───────────────────────────────────────
    location_change_flag = 0.0
    if last_tx and last_tx.location and tx.location:
        if last_tx.location.strip().lower() != tx.location.strip().lower():
            location_change_flag = 1.0

    # ── Geo distance ──────────────────────────────────────────
    geo_distance = 0.0
    if last_tx and last_tx.location and tx.location:
        prev_coords = _lookup_coords(last_tx.location)
        curr_coords = _lookup_coords(tx.location)
        if prev_coords and curr_coords:
            geo_distance = _haversine_km(
                prev_coords[0], prev_coords[1],
                curr_coords[0], curr_coords[1],
            )

    # ── Time since last transaction (minutes) ─────────────────
    time_since_last = 24 * 60.0
    if last_tx and last_tx.timestamp:
        time_since_last = max((ts - last_tx.timestamp).total_seconds() / 60.0, 0.0)

    # ── Impossible travel detection ───────────────────────────
    impossible_travel = False
    if geo_distance > 2000 and time_since_last < 10:
        impossible_travel = True

    # ── Device change ─────────────────────────────────────────
    device_change_flag = 0.0
    if last_tx and last_tx.device_type and tx.device_type:
        if last_tx.device_type.strip().lower() != tx.device_type.strip().lower():
            device_change_flag = 1.0

    # ── New device detection (via devices table) ──────────────
    new_device_flag = 0.0
    if tx.device_type and customer:
        known_device = (
            db.query(Device)
            .filter(
                Device.customer_id == customer.customer_id,
                Device.device_type == tx.device_type,
            )
            .first()
        )
        if not known_device:
            new_device_flag = 1.0

    # ── 24h velocity ──────────────────────────────────────────
    trailing_24h = ts - timedelta(hours=24)
    tx_count_24h = sum(1 for h in history if h.timestamp and h.timestamp >= trailing_24h)

    return {
        "amount_over_customer_avg": round(amount_over_customer_avg, 4),
        "transaction_velocity": float(transaction_velocity),
        "unusual_time_flag": unusual_time_flag,
        "location_change_flag": location_change_flag,
        "geo_distance": round(geo_distance, 2),
        "device_change_flag": device_change_flag,
        "new_device_flag": new_device_flag,
        "impossible_travel": float(impossible_travel),
        "time_since_last_transaction": round(time_since_last, 2),
        "tx_count_24h": float(tx_count_24h),
        "amount": amount,
        "transaction_hour": float(ts.hour),
    }
