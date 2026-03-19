"""
Fraud Memory — Redis-backed pattern tracking.
Stores fingerprints of confirmed/blocked fraud to trigger PREVENTION SMS 
when similar patterns appear in future transactions.
"""
import json
import logging

logger = logging.getLogger("fraud_memory")

class FraudMemory:
    def __init__(self, redis_client=None):
        self.redis = redis_client
        # Memory prefixes
        self.PREFIX_CITY = "fraud:city:"
        self.PREFIX_DEVICE = "fraud:device:"
        self.PREFIX_CUSTOMER = "fraud:cus:"
        

    async def record_blocked_transaction(self, txn: dict):
        """Record a block event. USES redis sorted set for time-window checks."""
        if not self.redis:
            return
            
        cid = txn.get('customer_id', 'unknown')
        now = time.time()
        
        try:
            # 1. Store in sliding window (60 min)
            key = f"fraud:blocked:{cid}"
            await self.redis.zadd(key, {str(now): now})
            await self.redis.zremrangebyscore(key, 0, now - 3600)
            await self.redis.expire(key, 3600)
            
            # 2. Legacy markers (city, device)
            city = txn.get('city', 'unknown').lower()
            device = txn.get('device', 'unknown')
            expiry = 86400 
            
            await self.redis.incr(f"{self.PREFIX_CITY}{city}")
            await self.redis.expire(f"{self.PREFIX_CITY}{city}", expiry)
            
            await self.redis.incr(f"{self.PREFIX_DEVICE}{device}")
            await self.redis.expire(f"{self.PREFIX_DEVICE}{device}", expiry)
            
            print(f"[MEMORY] Logged block for {cid}. Pattern: {txn.get('patterns_matched')}")
            
        except Exception as e:
            logger.error(f"Error recording fraud memory: {e}")

    async def should_send_preventive_sms(self, customer_id: str) -> bool:
        """
        Logic: 
        - Are there >= 3 blocks in last 60 mins?
        - Was a preventive SMS NOT sent in the last 4 hours?
        """
        if not self.redis:
            return False
            
        try:
            # Check 1: Count in 60 min window
            now = time.time()
            key = f"fraud:blocked:{customer_id}"
            count = await self.redis.zcount(key, now - 3600, now)
            
            if count < 3:
                return False
                
            # Check 2: Rate limit (4 hours)
            alert_key = f"fraud:alert_sent:{customer_id}"
            if await self.redis.exists(alert_key):
                return False
                
            return True
        except Exception as e:
            logger.error(f"Error checking preventive alert logic: {e}")
            return False

    async def mark_preventive_alert_sent(self, customer_id: str):
        """Set 4-hour lock on preventive alerts for this customer."""
        if self.redis:
            key = f"fraud:alert_sent:{customer_id}"
            await self.redis.set(key, "1", ex=14400) # 4 hours

    async def check_prevention_needed(self, txn: dict) -> tuple[bool, str]:
        # ... logic for Type 2 Prevention Warnings (same location/device)
        if not self.redis: return False, ""
        city = txn.get('city', 'unknown').lower()
        device = txn.get('device', 'unknown')
        if await self.redis.get(f"{self.PREFIX_DEVICE}{device}"):
            return True, f"device ({device})"
        city_hits = await self.redis.get(f"{self.PREFIX_CITY}{city}")
        if city_hits and int(city_hits) >= 2:
            return True, f"high-fraud city ({city})"
        return False, ""

import time
# Singleton to be initialized in main.py
fraud_memory = FraudMemory()

def init_fraud_memory(redis_client):
    global fraud_memory
    fraud_memory.redis = redis_client
    print("[MEMORY] Fraud memory initialized with Redis")
    return fraud_memory
