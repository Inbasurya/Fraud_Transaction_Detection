from __future__ import annotations

"""
Feature Store — real-time feature aggregation backed by Redis.
Uses sorted-sets for windowed aggregations (1h, 24h, 7d).
Also provides haversine distance and IP velocity features.
Target: < 5 ms per feature vector.
"""

import math
import time
from typing import Any

import redis.asyncio as redis

from config import get_settings


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in km between two GPS points."""
    R = 6371.0
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δφ = math.radians(lat2 - lat1)
    Δλ = math.radians(lon2 - lon1)
    a = math.sin(Δφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(Δλ / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class FeatureStore:
    """
    Writes recent transaction signals into Redis sorted-sets keyed by
    customer_id.  Reads back windowed aggregates for rule / ML engines.
    """

    WINDOWS = {
        "1h": 3600,
        "24h": 86400,
        "7d": 604800,
    }

    def __init__(self, redis_client: redis.Redis | None = None):
        self._r = redis_client

    async def _ensure_client(self) -> redis.Redis:
        if self._r is None:
            settings = get_settings()
            self._r = redis.from_url(
                settings.REDIS_URL, decode_responses=True
            )
        return self._r

    # ------------------------------------------------------------------
    # Write path
    # ------------------------------------------------------------------

    async def record_transaction(self, txn: dict) -> None:
        """Store amount + location + device + IP into sorted-sets."""
        r = await self._ensure_client()
        cid = txn["customer_id"]
        ts = txn.get("timestamp", time.time())
        pipe = r.pipeline(transaction=False)

        # Amount sorted-set  (score = epoch)
        pipe.zadd(f"fs:{cid}:amounts", {f'{txn["id"]}:{txn["amount"]}': ts})
        # Trim older entries (keep last 7d + buffer)
        pipe.zremrangebyscore(f"fs:{cid}:amounts", "-inf", ts - self.WINDOWS["7d"])

        # Location sorted-set
        loc = f'{txn["id"]}:{txn.get("lat", 0)}:{txn.get("lng", 0)}'
        pipe.zadd(f"fs:{cid}:locations", {loc: ts})
        pipe.zremrangebyscore(f"fs:{cid}:locations", "-inf", ts - self.WINDOWS["7d"])

        # Device sorted-set
        pipe.zadd(f"fs:{cid}:devices", {txn.get("device_fingerprint", "unknown"): ts})

        # IP sorted-set
        pipe.zadd(f"fs:{cid}:ips", {txn.get("ip_address", "0.0.0.0"): ts})
        pipe.zremrangebyscore(f"fs:{cid}:ips", "-inf", ts - self.WINDOWS["24h"])

        # Merchant-category counts
        pipe.zadd(f"fs:{cid}:merchants", {txn.get("merchant_category", "other"): ts})
        pipe.set(f"fs:{cid}:last_city", txn.get("city", ""), ex=self.WINDOWS["7d"])

        await pipe.execute()

    # ------------------------------------------------------------------
    # Read path — windowed features
    # ------------------------------------------------------------------

    async def get_features(self, txn: dict) -> dict[str, Any]:
        """
        Build a feature vector for the transaction.
        Returns dict with all numeric features for rule + ML engines.
        """
        r = await self._ensure_client()
        cid = txn["customer_id"]
        now = txn.get("timestamp", time.time())

        features: dict[str, Any] = {}

        # --- Transaction counts & amounts per window ---
        for label, secs in self.WINDOWS.items():
            start = now - secs
            amounts_raw = await r.zrangebyscore(
                f"fs:{cid}:amounts", start, now, withscores=False
            )
            amounts = []
            for entry in amounts_raw:
                parts = entry.rsplit(":", 1)
                if len(parts) == 2:
                    try:
                        amounts.append(float(parts[1]))
                    except ValueError:
                        pass

            features[f"txn_count_{label}"] = len(amounts)
            features[f"txn_total_{label}"] = sum(amounts) if amounts else 0.0
            features[f"txn_avg_{label}"] = (
                sum(amounts) / len(amounts) if amounts else 0.0
            )
            features[f"txn_max_{label}"] = max(amounts) if amounts else 0.0

        # --- Amount deviation from customer average ---
        customer_avg = txn.get("customer_avg_amount", 0.0) or 1.0
        features["amount_deviation"] = txn.get("amount", 0) / customer_avg
        features["amount_to_avg_ratio"] = txn.get("amount", 0) / max(features.get("txn_avg_24h", 0.0), 1.0)
        features["amount_to_max_ratio"] = txn.get("amount", 0) / max(features.get("txn_max_7d", 0.0), 1.0)

        # --- Distance from previous transaction ---
        features["distance_from_prev_km"] = await self._distance_from_prev(
            r, cid, txn, now
        )

        # --- Unique devices in 24 h ---
        devices_24h = await r.zrangebyscore(
            f"fs:{cid}:devices", now - self.WINDOWS["24h"], now
        )
        features["unique_devices_24h"] = len(set(devices_24h))

        # --- Is device known? ---
        all_devices = await r.zrangebyscore(f"fs:{cid}:devices", "-inf", "+inf")
        features["is_new_device"] = int(
            txn.get("device_fingerprint", "") not in set(all_devices)
        )
        features["device_count_30d"] = len(set(all_devices))

        # --- Unique IPs in 24 h ---
        ips_24h = await r.zrangebyscore(
            f"fs:{cid}:ips", now - self.WINDOWS["24h"], now
        )
        features["unique_ips_24h"] = len(set(ips_24h))

        # --- Time-of-day bucket (0-3 = night, 4-8 = morning, ...) ---
        from datetime import datetime, timezone as tz

        dt = datetime.fromtimestamp(now, tz=tz.utc)
        features["hour_of_day"] = dt.hour
        features["is_weekend"] = int(dt.weekday() >= 5)
        features["is_night"] = int(dt.hour < 6 or dt.hour > 22)
        features["is_odd_hour"] = features["is_night"]

        # --- Merchant-category diversity in 24 h ---
        merchants_24h = await r.zrangebyscore(
            f"fs:{cid}:merchants", now - self.WINDOWS["24h"], now
        )
        features["merchant_diversity_24h"] = len(set(merchants_24h))
        merchants_7d = await r.zrangebyscore(
            f"fs:{cid}:merchants", now - self.WINDOWS["7d"], now
        )
        features["unique_merchants_7d"] = len(set(merchants_7d))

        # --- Last-seen timing + city/geo features ---
        latest_amount = await r.zrevrangebyscore(
            f"fs:{cid}:amounts", now, "-inf", start=0, num=1, withscores=True
        )
        if latest_amount:
            features["time_since_last_h"] = max((now - float(latest_amount[0][1])) / 3600.0, 0.0)
        else:
            features["time_since_last_h"] = 999.0

        last_city = await r.get(f"fs:{cid}:last_city")
        if isinstance(last_city, bytes):
            last_city = last_city.decode("utf-8", errors="ignore")
        features["city_changed"] = int(bool(last_city and txn.get("city") and str(last_city) != str(txn.get("city"))))
        features["geo_risk_score"] = min(
            1.0,
            0.9 if (features["city_changed"] and features["time_since_last_h"] < 2) else features["distance_from_prev_km"] / 1000.0,
        )
        merchant_name = str(txn.get("merchant", "")).upper()
        features["is_international"] = int(any(k in merchant_name for k in ("INTL", "FOREX", "WIRE", "CRYPTO")))
        features["merchant_risk_score"] = self._merchant_risk_score(merchant_name)

        return features

    async def _distance_from_prev(
        self, r: redis.Redis, cid: str, txn: dict, now: float
    ) -> float:
        """Haversine distance (km) between this txn and the previous one."""
        locs = await r.zrangebyscore(
            f"fs:{cid}:locations",
            now - self.WINDOWS["1h"],
            now,
            withscores=False,
        )
        if len(locs) < 1:
            return 0.0

        # Latest stored location
        prev = locs[-1]
        parts = prev.split(":")
        if len(parts) < 3:
            return 0.0
        try:
            prev_lat, prev_lng = float(parts[1]), float(parts[2])
        except ValueError:
            return 0.0

        cur_lat = txn.get("lat", 0.0)
        cur_lng = txn.get("lng", 0.0)
        return round(_haversine(prev_lat, prev_lng, cur_lat, cur_lng), 2)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    async def close(self) -> None:
        if self._r:
            await self._r.close()

    @staticmethod
    def _merchant_risk_score(merchant_name: str) -> float:
        m = merchant_name.upper()
        if any(x in m for x in ("CRYPTO", "WIRE", "CASINO", "GAMBLING")):
            return 0.9
        if any(x in m for x in ("FOREX", "INTL", "INTERNATIONAL")):
            return 0.75
        if any(x in m for x in ("ATM", "CASH", "POS")):
            return 0.6
        return 0.1
