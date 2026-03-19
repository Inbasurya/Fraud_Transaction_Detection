"""
Device Intelligence Scorer
Scores device risk based on hygiene factors, velocity, and known fraud associations.
"""

from __future__ import annotations

import time
import logging
from redis import asyncio as aioredis
from app.config import settings

logger = logging.getLogger(__name__)
redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

async def get_device_score(features: dict) -> float:
    """
    Calculate 0-100 risk score based on device intelligence.
    Higher score = Higher risk.
    """
    try:
        score = 0
        device_id = features.get("device_id")
        
        if not device_id:
            # Missing device ID is suspicious for mobile app traffic, but maybe okay for web
            return 50.0 
        
        # 1. New Device Check (High Risk Signal)
        if features.get("is_new_device", 0) == 1:
            score += 40
        
        # 2. Mule Risk: Device used by multiple customers
        # (Assuming we track this set elsewhere on login/tx)
        cust_count = await redis.scard(f"device:{device_id}:customers")
        if cust_count > 3:
            score += 35
        elif cust_count > 1:
            score += 15
            
        # 3. Device Age (Newer = Riskier)
        first_seen = await redis.get(f"device:{device_id}:first_seen")
        if first_seen:
            age_hours = (time.time() - float(first_seen)) / 3600
            if age_hours < 1:
                score += 30  # Brand new (<1 hour)
            elif age_hours < 24:
                score += 15  # < 1 day
            elif age_hours > 24 * 30:
                score -= 10 # Trusted device bonus (> 30 days)
        else:
            # If not found but supposedly not "is_new_device" (data inconsistency or first time seeing it)
            # Treat as new if we have no record
            score += 20 

        # 4. Velocity: Many txns from device in short time
        # Get count from last hour
        now = time.time()
        recent_txns = await redis.zcount(f"device:{device_id}:txns", now - 3600, now)
        if recent_txns > 10:
            score += 20
        elif recent_txns > 5:
            score += 10
            
        return max(0.0, min(100.0, score))
        
    except Exception as e:
        logger.error(f"Error in device scoring: {e}")
        return 50.0 # Default to medium risk on error
