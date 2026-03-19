"""Bank-grade fraud pattern rule engine.

Detects:
  - Rapid transactions (velocity spike)
  - Location hopping
  - Device switching
  - High-amount spike
  - Night-time activity
  - Merchant anomaly
  - SIM Swap
  - Mule Account
  - Round Amount Structuring
  - International Fraud
"""
from __future__ import annotations

import logging
import asyncio
import time
from typing import Any, Tuple, List, Dict
from redis import asyncio as aioredis
from app.config import settings

logger = logging.getLogger(__name__)

# Initialize Redis client (module-level)
try:
    redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
except Exception as e:
    logger.error(f"Failed to initialize Redis for rules: {e}")
    redis_client = None


# -----------------------------------------------------------------------------
# Individual Rule Implementations
# -----------------------------------------------------------------------------

async def rule_velocity(features: dict, customer_id: int, redis: Any) -> Dict[str, Any]:
    """R001 - Velocity Attack"""
    # Prefer pre-calculated velocity, fallback to estimate
    velocity_1h = features.get("account_transaction_velocity", 0)
    if velocity_1h == 0:
        velocity_1h = features.get("transaction_frequency_last_24h", 0) / 24.0

    score = 0
    reason = ""
    if velocity_1h > 8:
        excess = velocity_1h - 8
        score = 35 + (excess * 3)
        score = min(60, score)
        reason = f"R001: High transaction velocity — {int(velocity_1h)} txns in 1 hour"

    return {
        "rule_id": "R001",
        "score": float(score),
        "triggered": score > 0,
        "reason": reason
    }

async def rule_geo_anomaly(features: dict, customer_id: int, redis: Any) -> Dict[str, Any]:
    """R002 - Geographic Anomaly"""
    city_changed = features.get("location_change_flag", 0) == 1.0
    time_diff = features.get("time_since_last_transaction", 9999)
    
    score = 0
    reason = ""
    
    if city_changed:
        if time_diff < 60:
            score = 30 + 25
            reason = f"R002: Impossible travel - Jump within {int(time_diff)} mins"
        else:
            score = 30
            reason = "R002: Location jump detected"
            
    return {"rule_id": "R002", "score": float(score), "triggered": score > 0, "reason": reason}

async def rule_new_device(features: dict, customer_id: int, redis: Any) -> Dict[str, Any]:
    """R003 - New Device High Value"""
    is_new = features.get("device_change_flag", 0) == 1.0
    amount = features.get("amount", 0)
    
    score = 0
    reason = ""
    if is_new and amount > 10000:
        score = 25 + min(20, amount / 10000)
        reason = f"R003: High-value transaction ({int(amount)}) from new device"

    return {"rule_id": "R003", "score": float(score), "triggered": score > 0, "reason": reason}

async def rule_odd_hour(features: dict, customer_id: int, redis: Any) -> Dict[str, Any]:
    """R004 - Odd Hour Transaction"""
    hour = features.get("transaction_hour", 12)
    amount = features.get("amount", 0)
    merchant = str(features.get("merchant", "")).lower()
    
    score = 0
    reason = ""
    if hour in [0, 1, 2, 3, 4] and amount > 5000:
        score = 20
        if "crypto" in merchant or "forex" in merchant:
            score += 15
        reason = f"R004: Large transaction at {int(hour)}:00 AM"

    return {"rule_id": "R004", "score": float(score), "triggered": score > 0, "reason": reason}

async def rule_amount_spike(features: dict, customer_id: int, redis: Any) -> Dict[str, Any]:
    """R005 - Amount Spike"""
    ratio = features.get("transaction_amount_ratio", 1.0)
    
    score = 0
    reason = ""
    if ratio > 5:
        score = 15 * min(4, ratio / 5)
        score = min(40, score)
        reason = f"R005: Amount is {ratio:.1f}x your average"

    return {"rule_id": "R005", "score": float(score), "triggered": score > 0, "reason": reason}

async def rule_card_testing(features: dict, customer_id: int, redis: Any) -> Dict[str, Any]:
    """R006 - Card Testing"""
    amount = features.get("amount", 0)
    count = features.get("account_transaction_velocity", 0)
    
    score = 0
    reason = ""
    if amount < 100 and count > 5:
        score = 55
        reason = "R006: Micro-transaction burst pattern detected"

    return {"rule_id": "R006", "score": float(score), "triggered": score > 0, "reason": reason}

async def rule_aml_structuring(features: dict, customer_id: int, redis: Any) -> Dict[str, Any]:
    """R007 - AML Structuring"""
    amount = features.get("amount", 0)
    
    score = 0
    reason = ""
    if 45000 <= amount <= 49999:
        score = 30
        reason = "R007: Amount structured just below 50K threshold"

    return {"rule_id": "R007", "score": float(score), "triggered": score > 0, "reason": reason}

async def rule_sim_swap(features: dict, customer_id: int, redis: Any) -> Dict[str, Any]:
    """R008 - SIM Swap Detection"""
    if not redis: return {"rule_id": "R008", "score": 0.0, "triggered": False, "reason": ""}
    
    # Check change flag first to avoid unnecessary redis calls
    if features.get("device_change_flag", 0) == 0:
         return {"rule_id": "R008", "score": 0.0, "triggered": False, "reason": ""}

    try:
        device_change_time = await redis.get(f"customer:{customer_id}:device_change_time")
        hours = 0.5 # Default recent if key missing but flag set
        if device_change_time:
             hours = (time.time() - float(device_change_time)) / 3600
    except Exception:
        hours = 0.5

    score = 0
    amount = features.get("amount", 0)
    
    if hours < 2 and amount > 5000:
        score = 65
    elif hours < 24 and amount > 8000:
        score = 40
        
    reason = f"R008: SIM Swap Risk - Device changed {hours:.1f}h ago" if score > 0 else ""
    return {"rule_id": "R008", "score": float(score), "triggered": score > 0, "reason": reason}

async def rule_mule_account(features: dict, customer_id: int, redis: Any) -> Dict[str, Any]:
    """R009 - Mule Account Detection"""
    if not redis: return {"rule_id": "R009", "score": 0.0, "triggered": False, "reason": ""}

    score = 0
    reason = ""
    try:
        inbound_senders = await redis.scard(f"customer:{customer_id}:inbound_senders_1h")
        if inbound_senders >= 5: score += 50
        elif inbound_senders >= 3: score += 30
        
        if score > 0:
            last_inbound = await redis.get(f"customer:{customer_id}:last_inbound_time")
            if last_inbound:
                mins = (time.time() - float(last_inbound)) / 60
                merchant = str(features.get("merchant", "")).lower()
                if mins < 30 and ("transfer" in merchant or "upi" in merchant):
                    score += 25
        
        if score > 0:
            reason = f"R009: Mule pattern ({inbound_senders} sources)"
    except Exception:
        pass
            
    return {"rule_id": "R009", "score": float(min(75, score)), "triggered": score > 0, "reason": reason}

async def rule_round_amount(features: dict, customer_id: int, redis: Any) -> Dict[str, Any]:
    """R010 - Round Amount Structuring"""
    amount = features.get("amount", 0)
    merchant = str(features.get("merchant", "")).lower()
    
    risky_merchants = ["crypto", "forex", "wire", "exchange", "transfer"]
    is_risky = any(x in merchant for x in risky_merchants)
    
    targets = [10000, 25000, 50000, 75000, 100000, 200000, 500000]
    is_round = any(abs(amount - t) < 50 for t in targets)
    
    score = 0
    reason = ""
    if is_round and is_risky:
        score = 35
        if features.get("device_change_flag", 0) == 1:
            score = 55
        reason = f"R010: Round amount {int(amount)} to high-risk merchant"

    return {"rule_id": "R010", "score": float(score), "triggered": score > 0, "reason": reason}

async def rule_international_fraud(features: dict, customer_id: int, redis: Any) -> Dict[str, Any]:
    """R011 - International Fraud Pattern"""
    if not features.get("is_international", False):
        return {"rule_id": "R011", "score": 0.0, "triggered": False, "reason": ""}

    score = 10
    amount = features.get("amount", 0)
    if amount > 25000: score += 15
    if features.get("device_change_flag", 0): score += 20
    if features.get("transaction_hour", 12) < 5: score += 15
    if features.get("account_transaction_velocity", 0) > 3: score += 20
    
    score = min(65, score)
    reason = "R011: International transaction with risk factors" if score > 10 else ""
    return {"rule_id": "R011", "score": float(score), "triggered": score > 10, "reason": reason}


# -----------------------------------------------------------------------------
# Main Evaluation Loop
# -----------------------------------------------------------------------------

async def evaluate_rules(tx: Any, features: dict) -> Tuple[float, List[str]]:
    """
    Run all fraud-pattern rules in PARALLEL and return (score 0-1, triggered reasons).
    """
    customer_id = getattr(tx, "user_id", 0)
    
    # Ensure merchant key exists for rules
    if "merchant" not in features:
        features["merchant"] = getattr(tx, "merchant", "")

    rule_functions = [
        rule_velocity, rule_geo_anomaly, rule_new_device, rule_odd_hour,
        rule_amount_spike, rule_card_testing, rule_aml_structuring,
        rule_sim_swap, rule_mule_account, rule_round_amount, rule_international_fraud
    ]
    
    try:
        # ASYNC GATHER EXECUTION
        results = await asyncio.gather(
            *[func(features, customer_id, redis_client) for func in rule_functions]
        )
        
        triggered = [r for r in results if r["triggered"]]
        reasons = [r["reason"] for r in triggered]
        
        if not triggered:
            return 0.0, []
            
        # Aggregation Logic: Max + 30% of rest (capped at 100)
        scores = sorted([r["score"] for r in triggered], reverse=True)
        primary = scores[0]
        secondary = sum(scores[1:]) * 0.30
        
        final_score = min(100.0, primary + secondary)
        
        # Return normalized 0-1 for compatibility
        return final_score / 100.0, reasons
        
    except Exception as e:
        logger.error(f"Async rule evaluation failed: {e}")
        return 0.0, []
