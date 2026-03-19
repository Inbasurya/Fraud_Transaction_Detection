"""Redis-based Feature Store for real-time customer features.

Uses Redis sorted sets with timestamps for time-windowed aggregations.
All feature reads use pipelining for <5ms latency.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from math import radians, sin, cos, sqrt, atan2
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        import redis
        _redis_client = redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        _redis_client.ping()
        logger.info("FeatureStore connected to Redis")
        return _redis_client
    except Exception as exc:
        logger.warning("Redis unavailable for FeatureStore: %s", exc)
        return None


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    rlat1, rlon1, rlat2, rlon2 = radians(lat1), radians(lon1), radians(lat2), radians(lon2)
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = sin(dlat / 2) ** 2 + cos(rlat1) * cos(rlat2) * sin(dlon / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


class FeatureStore:
    """Redis-backed real-time feature store for per-customer features."""

    # Key prefixes
    _TXN_TS = "fs:txn_ts:"          # sorted set: member=tx_id, score=timestamp
    _TXN_AMOUNTS = "fs:txn_amt:"    # sorted set: member=tx_id, score=timestamp (amount in hash)
    _MERCHANTS = "fs:merchants:"    # sorted set: member=merchant, score=timestamp
    _DEVICES = "fs:devices:"        # sorted set: member=device_fp, score=timestamp
    _FAILED = "fs:failed:"          # sorted set: member=tx_id, score=timestamp
    _LAST_LOC = "fs:last_loc:"      # string: "lat,lng"
    _AMOUNTS_SUM = "fs:amt_sum:"    # hash: total, count (for 30-day rolling)
    _PROFILE = "fs:profile:"        # hash: cached profile data

    def update_features(self, customer_id: str, transaction: dict[str, Any]) -> None:
        """Update all real-time features after a transaction."""
        r = _get_redis()
        if r is None:
            return

        now = time.time()
        tx_id = str(transaction.get("transaction_id", now))
        amount = float(transaction.get("amount", 0))
        merchant = str(transaction.get("merchant", "unknown"))
        device = str(transaction.get("device_type", "") or transaction.get("device_fingerprint", ""))
        location = transaction.get("location", "")
        is_failed = transaction.get("is_failed", False)

        pipe = r.pipeline(transaction=False)

        # txn_count_1h / txn_count_24h — sorted set with timestamps
        pipe.zadd(f"{self._TXN_TS}{customer_id}", {tx_id: now})
        # Keep 7 days max
        pipe.zremrangebyscore(f"{self._TXN_TS}{customer_id}", 0, now - 7 * 86400)

        # Amount tracking for 30-day avg
        pipe.hincrbyfloat(f"{self._AMOUNTS_SUM}{customer_id}", "total", amount)
        pipe.hincrby(f"{self._AMOUNTS_SUM}{customer_id}", "count", 1)
        pipe.expire(f"{self._AMOUNTS_SUM}{customer_id}", 31 * 86400)

        # unique_merchants_7d
        pipe.zadd(f"{self._MERCHANTS}{customer_id}", {merchant: now})
        pipe.zremrangebyscore(f"{self._MERCHANTS}{customer_id}", 0, now - 7 * 86400)

        # unique_devices_30d
        if device:
            pipe.zadd(f"{self._DEVICES}{customer_id}", {device: now})
            pipe.zremrangebyscore(f"{self._DEVICES}{customer_id}", 0, now - 30 * 86400)

        # last_txn_location
        if location and "," in str(location):
            pipe.set(f"{self._LAST_LOC}{customer_id}", str(location))

        # failed_txn_count_1h
        if is_failed:
            pipe.zadd(f"{self._FAILED}{customer_id}", {tx_id: now})
            pipe.zremrangebyscore(f"{self._FAILED}{customer_id}", 0, now - 3600)

        pipe.execute()

    def get_features(self, customer_id: str) -> dict[str, Any]:
        """Retrieve all real-time features using pipelined reads (<5ms target)."""
        r = _get_redis()
        if r is None:
            return self._default_features()

        now = time.time()
        one_hour_ago = now - 3600
        one_day_ago = now - 86400
        seven_days_ago = now - 7 * 86400
        thirty_days_ago = now - 30 * 86400

        pipe = r.pipeline(transaction=False)

        # 0: txn_count_1h
        pipe.zcount(f"{self._TXN_TS}{customer_id}", one_hour_ago, now)
        # 1: txn_count_24h
        pipe.zcount(f"{self._TXN_TS}{customer_id}", one_day_ago, now)
        # 2,3: avg_amount_30d (total, count)
        pipe.hget(f"{self._AMOUNTS_SUM}{customer_id}", "total")
        pipe.hget(f"{self._AMOUNTS_SUM}{customer_id}", "count")
        # 4: unique_merchants_7d
        pipe.zcount(f"{self._MERCHANTS}{customer_id}", seven_days_ago, now)
        # 5: unique_devices_30d
        pipe.zcount(f"{self._DEVICES}{customer_id}", thirty_days_ago, now)
        # 6: last_txn_location
        pipe.get(f"{self._LAST_LOC}{customer_id}")
        # 7: failed_txn_count_1h
        pipe.zcount(f"{self._FAILED}{customer_id}", one_hour_ago, now)

        results = pipe.execute()

        txn_count_1h = int(results[0] or 0)
        txn_count_24h = int(results[1] or 0)
        amt_total = float(results[2] or 0)
        amt_count = int(results[3] or 0)
        avg_amount_30d = amt_total / amt_count if amt_count > 0 else 0.0
        unique_merchants_7d = int(results[4] or 0)
        unique_devices_30d = int(results[5] or 0)
        last_txn_location = results[6] or ""
        failed_txn_count_1h = int(results[7] or 0)

        return {
            "txn_count_1h": txn_count_1h,
            "txn_count_24h": txn_count_24h,
            "avg_amount_30d": round(avg_amount_30d, 2),
            "unique_merchants_7d": unique_merchants_7d,
            "unique_devices_30d": unique_devices_30d,
            "last_txn_location": last_txn_location,
            "failed_txn_count_1h": failed_txn_count_1h,
        }

    def get_location_distance(self, customer_id: str, new_lat: float, new_lng: float) -> float:
        """Compute distance in km from last known location."""
        r = _get_redis()
        if r is None:
            return 0.0
        last_loc = r.get(f"{self._LAST_LOC}{customer_id}")
        if not last_loc or "," not in last_loc:
            return 0.0
        try:
            parts = last_loc.split(",")
            old_lat, old_lng = float(parts[0].strip()), float(parts[1].strip())
            return _haversine(old_lat, old_lng, new_lat, new_lng)
        except (ValueError, IndexError):
            return 0.0

    def cache_customer_profile(self, customer_id: str, profile: dict[str, Any]) -> None:
        """Cache customer profile with 5-minute TTL."""
        r = _get_redis()
        if r is None:
            return
        key = f"{self._PROFILE}{customer_id}"
        r.set(key, json.dumps(profile, default=str), ex=300)

    def get_cached_profile(self, customer_id: str) -> dict[str, Any] | None:
        """Get cached customer profile."""
        r = _get_redis()
        if r is None:
            return None
        data = r.get(f"{self._PROFILE}{customer_id}")
        if data:
            return json.loads(data)
        return None

    @staticmethod
    def _default_features() -> dict[str, Any]:
        return {
            "txn_count_1h": 0,
            "txn_count_24h": 0,
            "avg_amount_30d": 0.0,
            "unique_merchants_7d": 0,
            "unique_devices_30d": 0,
            "last_txn_location": "",
            "failed_txn_count_1h": 0,
        }


# Singleton
feature_store = FeatureStore()
