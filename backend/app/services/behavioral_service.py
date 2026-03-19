"""Bank-grade Customer Behavioral Profiling Service.

Implements a real-time behavioral DNA system using Redis hashes.
Tracks spending patterns, merchants, locations, velocity, and devices.
Updates profiles instantly after every transaction using Exponential Moving Averages (EMA).
"""

from __future__ import annotations

import json
import logging
import math
import time
from typing import Any, Dict, List, Optional
from redis import asyncio as aioredis
from app.config import settings

logger = logging.getLogger(__name__)

# Initialize Redis client
try:
    redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
except Exception as e:
    logger.error(f"Failed to initialize Redis for behavioral service: {e}")
    redis_client = None


# -----------------------------------------------------------------------------
# Cold Start Logic
# -----------------------------------------------------------------------------

def get_cold_start_score(features: dict, account_age_days: int) -> float:
    """Calculate risk score for new customers based on cohorts."""
    if account_age_days < 7:
        base_risk = 25  # New account, slightly elevated
    elif account_age_days < 30:
        base_risk = 15  # Young account, moderate
    else:
        base_risk = 5   # Mature account, low baseline
    
    # New accounts doing crypto/forex = high risk
    if features.get("merchant_risk_score", 0) > 0.7:
        base_risk += 30
    
    # New account high value = elevated risk
    if features.get("amount", 0) > 25000:
        base_risk += 15
    
    return float(min(60, base_risk))


# -----------------------------------------------------------------------------
# Core Behavioral Scoring
# -----------------------------------------------------------------------------

async def get_customer_profile(customer_id: int, redis: Any) -> Dict[str, Any]:
    """Fetch profile from Redis and parse JSON fields."""
    if not redis:
        return {}
        
    try:
        data = await redis.hgetall(f"customer:{customer_id}:profile")
        if not data:
            return {}
            
        # Type conversion and Safe JSON Loading
        # Helper to safely load JSON or return default
        def safe_json(key, default):
            val = data.get(key)
            if not val:
                return default
            try:
                return json.loads(val)
            except json.JSONDecodeError:
                return default

        # Helper to safely convert to float/int
        def safe_float(key, default=0.0):
            try:
                return float(data.get(key, default))
            except (ValueError, TypeError):
                return default

        def safe_int(key, default=0):
            try:
                return int(data.get(key, default))
            except (ValueError, TypeError):
                return default

        profile = {
            "avg_amount": safe_float("avg_amount"),
            "max_amount_30d": safe_float("max_amount_30d"),
            "std_amount": safe_float("std_amount"),
            "geo_consistency": safe_float("geo_consistency"),
            "crypto_exposure": safe_float("crypto_exposure"),
            "avg_daily_txns": safe_float("avg_daily_txns"),
            "avg_hourly_txns": safe_float("avg_hourly_txns"),
            "account_age_days": safe_int("account_age_days"),
            "total_txns": safe_int("total_txns"),
            "last_updated": safe_float("last_updated"),
            "home_city": data.get("home_city", ""),
            # Parse JSON fields
            "hourly_vector": safe_json("hourly_vector", [0.0]*24),
            "preferred_hours": safe_json("preferred_hours", []),
            "city_history": safe_json("city_history", {}),
            "top_merchants": safe_json("top_merchants", {}),
            "merchant_categories": safe_json("merchant_categories", {}),
            "trusted_devices": safe_json("trusted_devices", []),
        }

        # Ensure hourly vector is List[float] of length 24
        if not isinstance(profile["hourly_vector"], list) or len(profile["hourly_vector"]) != 24:
             profile["hourly_vector"] = [0.0]*24

        return profile
    except Exception as e:
        logger.error(f"Error fetching profile for {customer_id}: {e}")
        return {}


async def get_behavioral_score(customer_id: int, features: dict, redis: Any = None) -> float:
    """
    Calculate anomaly score (0-100) based on deviation from profile.
    """
    redis = redis or redis_client
    if not redis:
        return 0.0

    profile = await get_customer_profile(customer_id, redis)
    
    # Cold Start Check
    total_txns = profile.get("total_txns", 0)
    if total_txns < 5:
        # If profile missing, estimate age from features or default to new
        age = profile.get("account_age_days", features.get("account_age_days", 0))
        return get_cold_start_score(features, age)
    
    anomaly_scores = {}
    
    # 1. AMOUNT ANOMALY (35% weight)
    avg_amount = profile.get("avg_amount", 0)
    std_amount = max(profile.get("std_amount", 0), avg_amount * 0.3)
    amount = features.get("amount", 0)
    
    if std_amount > 0:
        z_score = abs(amount - avg_amount) / std_amount
        # Cap z-score at 3 for reasonable scaling
        amount_anomaly = min(100, z_score * 25) 
    else:
        amount_anomaly = 0
    anomaly_scores["amount"] = amount_anomaly * 0.35
    
    # 2. TIME ANOMALY (20% weight)
    # Ensure hour is valid 0-23
    try:
        hour = int(features.get("hour_of_day", features.get("transaction_hour", 12)))
    except (ValueError, TypeError):
        hour = 12
        
    hourly_vector = profile.get("hourly_vector", [0.0]*24)
    
    time_anomaly = 0
    if hourly_vector and 0 <= hour < 24:
        expected_prob = hourly_vector[hour]
        if expected_prob < 0.02:
            time_anomaly = 85  # Almost never transacts this hour
        elif expected_prob < 0.05:
            time_anomaly = 50
    anomaly_scores["time"] = time_anomaly * 0.20
    
    # 3. LOCATION ANOMALY (20% weight)  
    current_city = features.get("city", "")
    home_city = profile.get("home_city", "")
    
    location_anomaly = 0
    if current_city and home_city:
        if current_city != home_city:
            geo_consistency = profile.get("geo_consistency", 0)
            # Low consistency = travels often = less suspicious
            # High consistency = rarely travels = suspicious
            location_anomaly = 70 * geo_consistency
    elif not home_city:
        location_anomaly = 0 # No history
    else:
        location_anomaly = 15  # Unknown city
    anomaly_scores["location"] = location_anomaly * 0.20
    
    # 4. MERCHANT ANOMALY (15% weight)
    top_merchants = profile.get("top_merchants", {})
    current_merchant = features.get("merchant", "")
    
    merchant_anomaly = 0
    if current_merchant and current_merchant not in top_merchants:
        merchant_anomaly = 30  # New merchant
        if features.get("merchant_risk_score", 0) > 0.7:
            merchant_anomaly = 65  # New AND high-risk merchant
    anomaly_scores["merchant"] = merchant_anomaly * 0.15
    
    # 5. VELOCITY ANOMALY (10% weight)
    current_1h = features.get("txn_count_1h", features.get("velocity", 0))
    avg_hourly = profile.get("avg_hourly_txns", 0.5) # Default baseline
    
    velocity_anomaly = 0
    if avg_hourly > 0:
        velocity_ratio = current_1h / avg_hourly
        if velocity_ratio > 3:
             velocity_anomaly = min(100, (velocity_ratio - 2) * 20)
    anomaly_scores["velocity"] = velocity_anomaly * 0.10
    
    total_score = sum(anomaly_scores.values())
    return round(min(100.0, total_score), 1)


# -----------------------------------------------------------------------------
# Profile Updates
# -----------------------------------------------------------------------------

async def update_customer_profile(customer_id: int, features: dict, 
                                   risk_score: float, redis: Any = None):
    """Update profile with new transaction data using EMA."""
    redis = redis or redis_client
    if not redis:
        return

    alpha = 0.1  # EMA smoothing factor
    
    # Fetch existing profile
    profile = await get_customer_profile(customer_id, redis)
    current_amount = features.get("amount", 0)
    
    # Update EMA amounts
    old_avg = profile.get("avg_amount", current_amount)
    new_avg = (1 - alpha) * old_avg + alpha * current_amount
    
    old_std = profile.get("std_amount", old_avg * 0.2)
    new_std = (1 - alpha) * old_std + alpha * abs(current_amount - new_avg)
    
    # Update hourly vector
    hourly_vector = profile.get("hourly_vector", [0.0] * 24)
    if not isinstance(hourly_vector, list) or len(hourly_vector) != 24:
        hourly_vector = [0.0] * 24
        
    try:
        hour = int(features.get("hour_of_day", features.get("transaction_hour", 12)))
    except (ValueError, TypeError):
        hour = 12
    
    if 0 <= hour < 24:
        # Increase probability for current hour
        # Simple update: increase index, normalize later
        # Or running average per hour slot?
        # Let's do a simple probability distribution update
        # Decay all slots slightly
        hourly_vector = [(1 - alpha) * p for p in hourly_vector]
        # Boost current slot
        hourly_vector[hour] += alpha
        
        # Normalize vector so it sums to 1
        total = sum(hourly_vector) or 1
        hourly_vector = [v/total for v in hourly_vector]
    
    # Update city history
    city = features.get("city", "")
    city_history = profile.get("city_history", {})
    home_city = profile.get("home_city", "")
    geo_consistency = profile.get("geo_consistency", 0.0)
    
    if city:
        city_history[city] = city_history.get(city, 0) + 1
        # Recalculate home city
        home_city = max(city_history, key=city_history.get)
        total_city_txns = sum(city_history.values())
        if total_city_txns > 0:
            geo_consistency = city_history.get(home_city, 0) / total_city_txns
    
    # Update merchant tracking
    merchant = features.get("merchant", "")
    top_merchants = profile.get("top_merchants", {})
    if merchant:
        top_merchants[merchant] = top_merchants.get(merchant, 0) + 1
        # Keep only top 20 merchants
        top_merchants = dict(sorted(
            top_merchants.items(), 
            key=lambda x: x[1], 
            reverse=True)[:20])
    
    # Update velocity baseline
    # 1-hour velocity EMA
    current_1h = features.get("txn_count_1h", features.get("velocity", 0))
    old_hourly = profile.get("avg_hourly_txns", 0.5)
    # If old is 0 (new profile), initialize with current
    if old_hourly == 0: old_hourly = max(0.5, float(current_1h))
    new_hourly = (1 - alpha) * old_hourly + alpha * float(current_1h)

    # 24-hour velocity EMA
    current_24h = features.get("txn_count_24h", 0)
    old_daily = profile.get("avg_daily_txns", 3.0)
    if old_daily == 0: old_daily = max(3.0, float(current_24h))
    new_daily = (1 - alpha) * old_daily + alpha * float(current_24h)
    
    # Update trusted devices
    trusted_devices = profile.get("trusted_devices", [])
    device_id = features.get("device_id", "")
    
    # Only add device if low risk transaction
    if device_id and device_id not in trusted_devices and risk_score < 40:
        trusted_devices.append(device_id)
        if len(trusted_devices) > 10:
            trusted_devices = trusted_devices[-10:]  # Keep last 10
    
    # Prepare Data for Redis
    # Convert lists/dicts to JSON strings
    updated_profile_data = {
        "avg_amount": new_avg,
        "std_amount": new_std,
        "max_amount_30d": max(profile.get("max_amount_30d", 0), current_amount),
        "hourly_vector": json.dumps(hourly_vector),
        "home_city": home_city,
        "city_history": json.dumps(city_history),
        "geo_consistency": geo_consistency,
        "top_merchants": json.dumps(top_merchants),
        "trusted_devices": json.dumps(trusted_devices),
        "avg_daily_txns": new_daily,
        "avg_hourly_txns": new_hourly,
        "total_txns": profile.get("total_txns", 0) + 1,
        "last_updated": time.time(),
        
        # Preserve other fields, prefer fresh data from features
        "account_age_days": features.get("account_age_days", profile.get("account_age_days", 0)),
        "crypto_exposure": profile.get("crypto_exposure", 0),
        "preferred_hours": json.dumps(profile.get("preferred_hours", [])),
        "merchant_categories": json.dumps(profile.get("merchant_categories", {})),
    }

    # Ensure all values are strings for Redis Hash
    redis_hash_data = {}
    for k, v in updated_profile_data.items():
        if isinstance(v, (dict, list)):
            redis_hash_data[k] = json.dumps(v)
        else:
            redis_hash_data[k] = str(v)
    
    # Store as hash map
    try:
        await redis.hset(
            f"customer:{customer_id}:profile", 
            mapping=redis_hash_data
        )
        # Set expiration (e.g., 90 days of inactivity)
        await redis.expire(f"customer:{customer_id}:profile", 86400 * 90)
    except Exception as e:
        logger.error(f"Failed to update profile for {customer_id}: {e}")
