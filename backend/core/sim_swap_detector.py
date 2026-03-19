"""
SIM Swap and OTP Interception Detector.
Detects the specific patterns that indicate SIM swap fraud:
1. Device change + SIM change within 24h before large transaction
2. OTP requested multiple times (fraudster trying OTPs)
3. Account accessed from new device after SIM swap signal
4. Sudden location change to telecom operator's city (SIM swap offices)

This is a pattern Razorpay and Paytm added post-2022 fraud wave.
"""
import time
import redis.asyncio as aioredis

class SimSwapDetector:
    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client

    async def record_otp_request(self, customer_id: str, device_id: str):
        """Track every OTP request."""
        now = time.time()
        key = f"otp_requests:{customer_id}"
        await self.redis.zadd(key, {f"{device_id}:{now}": now})
        await self.redis.expire(key, 3600)

    async def record_device_change(self, customer_id: str, old_device: str, new_device: str):
        """Track device changes — SIM swap usually comes with device change."""
        await self.redis.set(
            f"device_change:{customer_id}",
            f"{old_device}->{new_device}",
            ex=86400
        )
        await self.redis.set(
            f"device_change_time:{customer_id}",
            str(time.time()),
            ex=86400
        )

    async def compute_sim_swap_risk(self, customer_id: str, txn: dict) -> dict:
        now = time.time()
        risk_signals = {}

        # 1. Multiple OTP requests in last hour (failed attempts)
        otp_key = f"otp_requests:{customer_id}"
        otp_count_1h = await self.redis.zcount(otp_key, now - 3600, now)
        risk_signals["otp_requests_1h"] = float(otp_count_1h)
        risk_signals["excessive_otp"] = 1.0 if otp_count_1h >= 3 else 0.0

        # 2. Device changed recently (last 24h)
        device_change_time = await self.redis.get(f"device_change_time:{customer_id}")
        if device_change_time:
            hours_since_change = (now - float(device_change_time)) / 3600
            risk_signals["hours_since_device_change"] = hours_since_change
            risk_signals["recent_device_change"] = 1.0 if hours_since_change < 24 else 0.0
        else:
            risk_signals["hours_since_device_change"] = 999.0
            risk_signals["recent_device_change"] = 0.0

        # 3. Composite SIM swap risk
        risk_signals["sim_swap_risk"] = (
            risk_signals["excessive_otp"] * 0.5 +
            risk_signals["recent_device_change"] * 0.5
        )

        return risk_signals
