"""
Behavioral Engine — maintains per-customer behavioral profiles (DNA)
and flags deviations from normal patterns.
Implements: 24h spending vector, merchant affinity, location consistency, velocity anomaly.
"""

import json
import logging
import math
import time
from typing import Any, Optional
from redis import asyncio as aioredis # Compatible with pydantic-settings

logger = logging.getLogger(__name__)


async def _safe_get_profile(r: aioredis.Redis, key: str) -> Optional[dict]:
    """Read bp:{cid} safely — handles leftover HASH keys from old code."""
    try:
        key_type = await r.type(key)
        # decode_responses may return str or bytes depending on config
        if key_type in (b"hash", "hash"):
            logger.warning(f"Deleting corrupt HASH key: {key}")
            await r.delete(key)
            return None
        if key_type in (b"none", "none"):
            return None
        raw = await r.get(key)
        return json.loads(raw) if raw else None
    except Exception as e:
        logger.error(f"Profile read error for {key}: {e}")
        return None


class BehavioralEngine:
    DECAY_FACTOR = 0.10

    def __init__(self, redis_client: Optional[aioredis.Redis] = None):
        self._r = redis_client

    async def _ensure_client(self) -> aioredis.Redis:
        if self._r is None:
            from app.config import settings
            self._r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        return self._r

    def _get_cohort_defaults(self, txn_amount: float) -> dict:
        if txn_amount > 50000:
            avg, var = 45000.0, 20000.0**2
        elif txn_amount > 10000:
            avg, var = 12000.0, 5000.0**2
        elif txn_amount > 2000:
            avg, var = 3500.0, 1500.0**2
        else:
            avg, var = 800.0, 400.0**2

        return {
            "hour_vector": [0.04] * 24,
            "amount_mean": avg,
            "amount_variance": var,
            "merchant_affinity": {},
            "known_cities": {},
            "home_city": None,
            "velocity_stats": {"hourly_avg": 1.0},
            "txn_count": 0,
            "last_updated": time.time()
        }

    async def update_profile(self, txn: dict) -> None:
        r = await self._ensure_client()
        cid = txn["customer_id"]
        key = f"bp:{cid}"
        amount = float(txn.get("amount", 0))

        data = await _safe_get_profile(r, key)
        if data:
            profile = data
        else:
            profile = self._get_cohort_defaults(amount)

        # Update 24h vector
        # Use timestamp if available, else current time
        ts = txn.get("timestamp")
        # Handle timestamp format (isoformat str or float)
        if isinstance(ts, str):
            try:
                # Basic ISO parsing if needed, but synthetic engine usually gives nice strings
                # Or if time.time() used
                # For simplicity, if string, parse or use current time
                # backend/routers/ws.py sends ISO string
                import datetime
                dt = datetime.datetime.fromisoformat(ts.replace('Z', '+00:00'))
                hour = dt.hour
            except:
                hour = int(time.strftime("%H"))
        elif isinstance(ts, (int, float)):
             hour = int(time.strftime("%H", time.gmtime(ts)))
        else:
             hour = int(time.strftime("%H"))
            
        profile["hour_vector"][hour] = profile["hour_vector"][hour] * (1 - self.DECAY_FACTOR) + self.DECAY_FACTOR
        
        # Update Amount Profile
        old_mean = profile["amount_mean"]
        profile["amount_mean"] = old_mean * (1 - self.DECAY_FACTOR) + amount * self.DECAY_FACTOR
        # Variance update
        profile["amount_variance"] = profile["amount_variance"] * (1 - self.DECAY_FACTOR) + self.DECAY_FACTOR * (amount - old_mean)**2
        
        # Update Merchant Affinity
        merchant = txn.get("merchant_id", "unknown")
        profile["merchant_affinity"][merchant] = min(1.0, profile["merchant_affinity"].get(merchant, 0.0) + 0.1)
        
        # Location Consistency
        city = txn.get("city", "unknown")
        profile["known_cities"][city] = profile["known_cities"].get(city, 0) + 1
        profile["home_city"] = max(profile["known_cities"], key=profile["known_cities"].get)
        
        # Velocity Update
        # Assume feature_engineer passed 'txn_count_1h' if integrated, else just count this txn?
        # Ideally we get this from features. But update_profile is called AFTER scoring and presumably features computed.
        # But update_profile usually takes just txn.
        # We'll rely on txn metadata or skip velocity update here if feature unavailable
        # Just incrementing global hourly avg slightly towards 1 (meaning activity exists)
        profile["velocity_stats"]["hourly_avg"] = profile["velocity_stats"]["hourly_avg"] * (1 - self.DECAY_FACTOR) + 1.0 * self.DECAY_FACTOR
        
        profile["txn_count"] += 1
        profile["last_updated"] = time.time()
        
        await r.set(key, json.dumps(profile), ex=86400 * 90)

    async def score(self, txn: dict, features: dict) -> dict[str, Any]:
        """
        Returns behavioral risk score (0-1) and breakdown.
        """
        r = await self._ensure_client()
        cid = txn["customer_id"]
        amount = float(txn.get("amount", 0))
        
        data = await _safe_get_profile(r, f"bp:{cid}")
        if not data:
            return {"behavioral_score": 0.1, "flags": ["new_profile"], "is_warmup": True}
        
        profile = data
        
        # Warm-up Period (5 txns)
        if profile["txn_count"] < 5:
            return {"behavioral_score": 0.05, "flags": ["warmup"], "is_warmup": True}

        # 1. Amount Deviation (35%)
        # DNA: amount_mean, amount_variance
        avg_amt = profile["amount_mean"]
        std_dev = math.sqrt(profile.get("amount_variance", 10000))
        std_dev = max(std_dev, 10.0) # Avoid div by zero
        
        z_score = abs(amount - avg_amt) / std_dev
        # Cap deviations
        amount_dev = min(1.0, z_score / 3.0) 

        # 2. Velocity Deviation (25%)
        curr_vel = features.get("txn_count_1h", 1)
        avg_vel = profile["velocity_stats"]["hourly_avg"]
        # Ratio of current to average
        vel_ratio = curr_vel / max(avg_vel, 0.5)
        if vel_ratio > 3.0: 
             velocity_dev = 1.0
        else:
             velocity_dev = max(0.0, vel_ratio - 1.0) / 2.0
        
        # 3. Location Deviation (20%)
        city = txn.get("city", "unknown")
        home = profile.get("home_city")
        if city == home:
            loc_dev = 0.0
        elif city in profile.get("known_cities", {}):
            loc_dev = 0.2
        else:
            loc_dev = 1.0

        # 4. Merchant Deviation (20%)
        merchant = txn.get("merchant_id", "unknown")
        affinity = profile["merchant_affinity"].get(merchant, 0.0)
        # If affinity is high (used often), dev is low.
        merchant_dev = 1.0 - affinity
        
        # Weighted Average Formula
        anomaly_score = (
            amount_dev * 0.35 +
            velocity_dev * 0.25 +
            loc_dev * 0.20 +
            merchant_dev * 0.20
        )
        
        return {
            "behavioral_score": round(anomaly_score, 3), # 0-1 range
            "components": {
                "amount": round(amount_dev, 2),
                "velocity": round(velocity_dev, 2),
                "location": round(loc_dev, 2),
                "merchant": round(merchant_dev, 2)
            }
        }

    async def close(self):
        if self._r:
            await self._r.close()
            self._r = None
