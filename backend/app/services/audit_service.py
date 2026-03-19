"""Audit Service for RBI Compliance.

Logs every fraud decision with full context for algorithmic accountability.
Includes dual-write to Redis Streams (real-time) and file logs (persistence).
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from app.config import settings
from redis import asyncio as aioredis # Use async redis client from aioredis in previous files

logger = logging.getLogger(__name__)

# Initialize Redis (will reuse connection pool if possible or create new)
redis = None

async def get_redis():
    global redis
    if redis is None:
        redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return redis

async def log_audit_event(event: Dict[str, Any]):
    """
    Log every scoring decision to both Redis stream and persistent file for RBI compliance audit trail.
    """
    redis_client = await get_redis()
    
    audit_entry = {
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat(),
        "transaction_id": event.get("txn_id"),
        "customer_id": event.get("customer_id"),
        "amount": event.get("amount"),
        "merchant": event.get("merchant"),
        "risk_score": event.get("risk_score"),
        "decision": event.get("decision"),
        "model_version": "XGBoost_v2.0",
        
        # Explainability (RBI requirement)
        "top_features": json.dumps(event.get("top_features", [])),
        "explanation": event.get("explanation", ""),
        "component_scores": json.dumps(event.get("component_scores", {})),
        
        # Operational context
        "processing_time_ms": event.get("processing_ms", 0),
        "rules_triggered": json.dumps(event.get("rules_triggered", [])),
        "behavioral_anomaly": event.get("behavioral_score", 0),
        
        # Session context
        "ip_address": event.get("ip_address", ""),
        "device_id": event.get("device_id", ""),
        "city": event.get("city", ""),
    }
    
    try:
        # 1. Write to Redis stream (real-time, 7-day retention)
        # We need to ensure values are strings for streams if using standard redis commands, 
        # but modern clients handle basic types. We stringified complex dicts above.
        # Check for None values and convert to empty string or suitable default
        stream_entry = {k: str(v) if v is not None else "" for k, v in audit_entry.items()}
        
        await redis_client.xadd(
            "stream:audit_log",
            stream_entry,
            maxlen=50000  # Keep last 50K events
        )
        
        # 2. Write to rotating file log (30-day retention)
        # In a real setup, this logger would be configured to rotate files
        logger.info(json.dumps(audit_entry))
        
        # 3. For HIGH/CRITICAL decisions, also store in Redis hash for fast lookup
        if event.get("decision") in ["BLOCK", "FLAG_REVIEW"]:
            # Hash keys must be strings
            await redis_client.hset(
                f"audit:fraud:{event.get('txn_id')}",
                mapping=stream_entry
            )
            await redis_client.expire(
                f"audit:fraud:{event.get('txn_id')}", 
                86400 * 30)  # 30-day retention
                
    except Exception as e:
        logger.error(f"Failed to log audit event: {e}")
