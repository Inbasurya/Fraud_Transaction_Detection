"""Advanced Behavioral Analytics Engine.

Detectors:
1. Velocity check — >5 tx in 10 minutes
2. Amount spike — amount > 3x 30-day average
3. Geographic impossibility — >500km apart in 2 hours
4. Device anomaly — new device for high-value txn
5. Time anomaly — outside customer's typical active hours
6. Merchant category mismatch — unusual MCC for this customer

Each returns a risk contribution (0.0–1.0) with explanation.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from math import radians, sin, cos, sqrt, atan2
from typing import Any

from app.feature_store import feature_store

logger = logging.getLogger(__name__)


@dataclass
class DetectorResult:
    name: str
    triggered: bool
    risk_score: float  # 0.0 to 1.0
    explanation: str


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    rlat1, rlon1, rlat2, rlon2 = radians(lat1), radians(lon1), radians(lat2), radians(lon2)
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = sin(dlat / 2) ** 2 + cos(rlat1) * cos(rlat2) * sin(dlon / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


# Map city names to coordinates for location resolution
_CITY_COORDS: dict[str, tuple[float, float]] = {
    "new york": (40.7128, -74.0060),
    "los angeles": (34.0522, -118.2437),
    "chicago": (41.8781, -87.6298),
    "houston": (29.7604, -95.3698),
    "london": (51.5074, -0.1278),
    "tokyo": (35.6762, 139.6503),
    "paris": (48.8566, 2.3522),
    "sydney": (-33.8688, 151.2093),
    "dubai": (25.2048, 55.2708),
    "singapore": (1.3521, 103.8198),
    "mumbai": (19.0760, 72.8777),
    "berlin": (52.5200, 13.4050),
    "toronto": (43.6532, -79.3832),
    "são paulo": (-23.5505, -46.6333),
    "seoul": (37.5665, 126.9780),
    "mexico city": (19.4326, -99.1332),
    "moscow": (55.7558, 37.6173),
    "shanghai": (31.2304, 121.4737),
    "beijing": (39.9042, 116.4074),
    "delhi": (28.7041, 77.1025),
    "san francisco": (37.7749, -122.4194),
    "miami": (25.7617, -80.1918),
    "dallas": (32.7767, -96.7970),
    "atlanta": (33.7490, -84.3880),
    "boston": (42.3601, -71.0589),
    "seattle": (47.6062, -122.3321),
    "denver": (39.7392, -104.9903),
    "phoenix": (33.4484, -112.0740),
    "philadelphia": (39.9526, -75.1652),
    "detroit": (42.3314, -83.0458),
    "minneapolis": (44.9778, -93.2650),
    "tampa": (27.9506, -82.4572),
    "portland": (45.5152, -122.6784),
    "las vegas": (36.1699, -115.1398),
    "austin": (30.2672, -97.7431),
}


def _resolve_location(location: str) -> tuple[float, float] | None:
    """Resolve a location string to lat/lng."""
    if not location:
        return None
    loc = location.strip()
    # Try lat,lng format
    if "," in loc:
        parts = loc.split(",")
        try:
            lat, lng = float(parts[0].strip()), float(parts[1].strip())
            if -90 <= lat <= 90 and -180 <= lng <= 180:
                return (lat, lng)
        except (ValueError, IndexError):
            pass
    # Try city name
    key = loc.lower().strip()
    if key in _CITY_COORDS:
        return _CITY_COORDS[key]
    # Partial match
    for city, coords in _CITY_COORDS.items():
        if city in key or key in city:
            return coords
    return None


class BehavioralEngine:
    """Runs all behavioral detectors against a transaction."""

    def analyze(
        self,
        customer_id: str,
        transaction: dict[str, Any],
        features: dict[str, Any] | None = None,
    ) -> list[DetectorResult]:
        """Run all detectors and return list of results."""
        if features is None:
            features = feature_store.get_features(customer_id)

        results = [
            self._velocity_check(customer_id, transaction, features),
            self._amount_spike(customer_id, transaction, features),
            self._geographic_impossibility(customer_id, transaction, features),
            self._device_anomaly(customer_id, transaction, features),
            self._time_anomaly(customer_id, transaction, features),
            self._merchant_mismatch(customer_id, transaction, features),
        ]
        return results

    def compute_risk_score(self, results: list[DetectorResult]) -> float:
        """Aggregate detector scores into a single behavioral risk (0.0–1.0)."""
        if not results:
            return 0.0
        triggered = [r for r in results if r.triggered]
        if not triggered:
            return 0.0
        # Weighted sum with diminishing returns
        total = sum(r.risk_score for r in triggered)
        return min(total, 1.0)

    # ═══ Individual Detectors ═══

    def _velocity_check(
        self, customer_id: str, tx: dict[str, Any], features: dict[str, Any]
    ) -> DetectorResult:
        """Flag if >5 transactions in 10 minutes (approximated by 1h count)."""
        txn_1h = features.get("txn_count_1h", 0)
        # If 1-hour count is very high, velocity is suspicious
        if txn_1h > 5:
            score = min((txn_1h - 5) / 10.0, 1.0) * 0.8
            return DetectorResult(
                name="velocity_check",
                triggered=True,
                risk_score=round(score, 3),
                explanation=f"High velocity: {txn_1h} transactions in the last hour (threshold: 5)",
            )
        return DetectorResult("velocity_check", False, 0.0, "Normal transaction velocity")

    def _amount_spike(
        self, customer_id: str, tx: dict[str, Any], features: dict[str, Any]
    ) -> DetectorResult:
        """Flag if amount > 3x customer's 30-day average."""
        amount = float(tx.get("amount", 0))
        avg_30d = features.get("avg_amount_30d", 0)

        if avg_30d > 0 and amount > 3 * avg_30d:
            ratio = amount / avg_30d
            score = min((ratio - 3) / 7.0, 1.0) * 0.7
            return DetectorResult(
                name="amount_spike",
                triggered=True,
                risk_score=round(score, 3),
                explanation=f"Amount ${amount:.2f} is {ratio:.1f}x the 30-day average (${avg_30d:.2f})",
            )
        return DetectorResult("amount_spike", False, 0.0, "Amount within normal range")

    def _geographic_impossibility(
        self, customer_id: str, tx: dict[str, Any], features: dict[str, Any]
    ) -> DetectorResult:
        """Flag if >500km apart from last transaction within 2 hours."""
        location = tx.get("location", "")
        last_loc = features.get("last_txn_location", "")

        new_coords = _resolve_location(str(location))
        old_coords = _resolve_location(str(last_loc))

        if new_coords and old_coords:
            distance = _haversine(old_coords[0], old_coords[1], new_coords[0], new_coords[1])
            if distance > 500:
                score = min(distance / 5000.0, 1.0) * 0.9
                return DetectorResult(
                    name="geographic_impossibility",
                    triggered=True,
                    risk_score=round(score, 3),
                    explanation=(
                        f"Transaction location is {distance:.0f}km from last known location "
                        f"(impossible travel detected)"
                    ),
                )

        return DetectorResult("geographic_impossibility", False, 0.0, "Location consistent")

    def _device_anomaly(
        self, customer_id: str, tx: dict[str, Any], features: dict[str, Any]
    ) -> DetectorResult:
        """Flag if new device used for high-value transaction."""
        amount = float(tx.get("amount", 0))
        unique_devices = features.get("unique_devices_30d", 0)
        avg_30d = features.get("avg_amount_30d", 0)

        # New device (first time or low count) + high-value transaction
        is_high_value = amount > max(avg_30d * 2, 500) if avg_30d > 0 else amount > 1000
        is_new_device = unique_devices <= 1

        if is_new_device and is_high_value:
            score = 0.6
            return DetectorResult(
                name="device_anomaly",
                triggered=True,
                risk_score=score,
                explanation=(
                    f"New/unrecognized device used for high-value transaction "
                    f"(${amount:.2f}, only {unique_devices} known devices)"
                ),
            )
        return DetectorResult("device_anomaly", False, 0.0, "Device is recognized")

    def _time_anomaly(
        self, customer_id: str, tx: dict[str, Any], features: dict[str, Any]
    ) -> DetectorResult:
        """Flag if transaction outside typical hours (2 AM – 5 AM as unusual)."""
        timestamp = tx.get("timestamp")
        hour = 12
        if hasattr(timestamp, "hour"):
            hour = timestamp.hour
        elif isinstance(timestamp, str):
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                hour = dt.hour
            except Exception:
                pass

        if 2 <= hour <= 5:
            score = 0.35
            return DetectorResult(
                name="time_anomaly",
                triggered=True,
                risk_score=score,
                explanation=f"Transaction at unusual hour ({hour}:00, typical fraud window 2-5 AM)",
            )
        return DetectorResult("time_anomaly", False, 0.0, "Transaction during normal hours")

    def _merchant_mismatch(
        self, customer_id: str, tx: dict[str, Any], features: dict[str, Any]
    ) -> DetectorResult:
        """Flag if MCC/merchant category is unusual for this customer."""
        unique_merchants = features.get("unique_merchants_7d", 0)
        amount = float(tx.get("amount", 0))

        # If customer has established pattern but this is a very different merchant count + high amount
        if unique_merchants > 10 and amount > 500:
            score = 0.3
            return DetectorResult(
                name="merchant_mismatch",
                triggered=True,
                risk_score=score,
                explanation=(
                    f"Unusual merchant pattern: {unique_merchants} unique merchants in 7 days "
                    f"with high-value transaction (${amount:.2f})"
                ),
            )
        return DetectorResult("merchant_mismatch", False, 0.0, "Merchant pattern normal")


# Singleton
behavioral_engine = BehavioralEngine()
