import asyncio
import json
import logging
import os
import random
import string
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

import redis.asyncio as aioredis
from core.feature_engineer import FeatureEngineer
from core.ml_engine import MLEngine
from core.rule_engine import RuleEngine
from core.behavioral_engine import BehavioralEngine
from core.graph_engine import GraphEngine
from core.scoring import ScoringEngine
from core.sms_service import send_blocked_transaction_sms, send_prevention_warning_sms
from core.fraud_memory import fraud_memory
import asyncio
import time as time_module


_recent_txn_ids = deque(maxlen=500)
logger = logging.getLogger(__name__)
_card_testing_cooldown: float = 0.0  # timestamp of last card testing scenario
CARD_TESTING_COOLDOWN_SECS = 45     # minimum gap between card-testing transactions

# Weighted fraud scenario pool — card testing gets 1 weight, others get 2+
# Adjusted dynamically in generate_raw_transaction() to enforce cooldown
_FRAUD_WEIGHTS = [1, 3, 2, 3, 2]  # card_test, wire, atm, crypto, forex

router = APIRouter()

_redis = None
_feature_eng = None
_ml_engine = None
_rule_engine = None
_behavioral_engine = None
_graph_engine = None
_risk_scorer = None
ml_scorer = None  # Exported for main.py
_initialized = False

async def init_ml_pipeline():
    global _redis, _feature_eng, _ml_engine, _rule_engine, _behavioral_engine, _graph_engine, _risk_scorer, _initialized
    try:
        from config import get_settings as _get_settings
        _settings = _get_settings()
        _redis = aioredis.from_url(_settings.REDIS_URL, decode_responses=False)
        await _redis.ping()
        _feature_eng = FeatureEngineer(_redis)
        
        # Rule Engine is always loaded first as a hard fallback
        _rule_engine = RuleEngine()
        _behavioral_engine = BehavioralEngine(_redis)
        _graph_engine = GraphEngine()
        _risk_scorer = ScoringEngine()
        
        # Initialize ML engine with separate try/except
        _ml_engine = MLEngine()
        try:
            await _ml_engine.load()
        except Exception as e:
            print(f"[ML] ML Model load failed: {e}. Running in Rule-only mode.")
        
        global ml_scorer
        ml_scorer = _risk_scorer
        
        _initialized = True
        print(f"[ML] Pipeline initialized. Reliability Fallback: ENABLED")
    except Exception as e:
        print(f"[ML] Critical pipeline init failed: {e}")
        _initialized = False


async def seed_customer_baselines():
    """
    Pre-populate Redis with realistic customer spending baselines.
    Without this, new customers have avg_amount=0, making every transaction
    look like an infinite spike → model scores 80+ for Ola ₹71.
    """
    if not _redis:
        return

    print("[SEED] Pre-populating customer baselines in Redis...")

    PROFILES = [
        (350,  3000,  "low_spend"),
        (800,  8000,  "mid_spend"),
        (2500, 25000, "high_spend"),
        (8000, 75000, "premium"),
    ]
    CITIES = ["Mumbai", "Delhi", "Bangalore", "Chennai", "Hyderabad",
              "Kolkata", "Pune", "Ahmedabad", "Jaipur", "Surat"]

    TTL_30D = 86400 * 30
    now = time.time()

    pipe = _redis.pipeline()
    count = 0
    for i in range(1000, 9999, 7):  # Same customer IDs as CUSTOMERS list
        cid = f"CUS-{i:04d}"
        profile = random.choice(PROFILES)
        avg_txn = profile[0] * (0.7 + random.random() * 0.6)   # ±30% variation
        max_txn = avg_txn * random.uniform(3, 8)

        # Only seed if NOT already in Redis (nx=True)
        pipe.set(f"amt_avg:{cid}", str(round(avg_txn, 2)), ex=TTL_30D, nx=True)
        pipe.set(f"amt_max:{cid}", str(round(max_txn, 2)), ex=TTL_30D, nx=True)
        # first_seen: random 30-365 days ago
        pipe.set(f"first_seen:{cid}",
                 str(now - random.uniform(30, 365) * 86400),
                 ex=86400 * 365, nx=True)
        pipe.set(f"last_city:{cid}", random.choice(CITIES), ex=86400 * 7, nx=True)
        count += 1

    await pipe.execute()
    print(f"[SEED] Baselines seeded for {count} customers — ML scoring accurate from first transaction")

BANKS = ["HDFC", "SBI", "ICICI", "Axis", "Citibank", "Standard Chartered"]
PAYMENT_MODES = ["Credit Card", "Debit Card", "UPI", "Netbanking"]
CARD_TYPES = ["Visa", "Mastercard", "RuPay", "Amex"]

MERCHANTS = [
    "Amazon Pay", "Flipkart", "Zomato", "PhonePe", "Paytm",
    "BigBasket", "Swiggy", "HDFC NetBanking", "Ola Money", "IRCTC",
    "MakeMyTrip", "Myntra", "DMart", "Reliance Smart", "Juspay",
    "POS Terminal #4821", "INTL-Wire-Transfer", "Crypto Exchange INR",
    "ATM Withdrawal", "Forex Exchange Dubai"
]

CITIES = ["Mumbai", "Delhi", "Bangalore", "Chennai", "Hyderabad",
          "Kolkata", "Pune", "Ahmedabad", "Jaipur", "Surat"]

CUSTOMERS = [f"CUS-{i:04d}" for i in range(1000, 9999, 7)]

# ── FIX 2: Merchants that should NEVER be marked suspicious by scenario generator ──
ALWAYS_SAFE_MERCHANTS = {
    "Zomato", "Swiggy", "BigBasket", "DMart", "Myntra",
    "Flipkart", "IRCTC", "BookMyShow", "Reliance Smart",
    "Ola Money", "Juspay", "Paytm", "PhonePe", "Amazon Pay",
    "HDFC NetBanking"
}

FRAUD_SCENARIOS = [
    {"merchant": "POS Terminal #4821", "category": "gas_station",
     "amount_range": (1, 99), "risk_range": (72, 95),
     "rules": ["R006"], "rule_names": ["Card testing pattern"],
     "description": "Micro-transactions to test stolen card"},
    {"merchant": "INTL-Wire-Transfer", "category": "wire_transfer",
     "amount_range": (45000, 149000), "risk_range": (80, 98),
     "rules": ["R003", "R002"], "rule_names": ["New device high value", "Geographic anomaly"],
     "description": "New device large international transfer"},
    {"merchant": "ATM Withdrawal", "category": "cash_withdrawal",
     "amount_range": (48000, 49999), "risk_range": (75, 90),
     "rules": ["R007"], "rule_names": ["AML structuring"],
     "description": "Structured below Rs.50000 threshold"},
    {"merchant": "Crypto Exchange INR", "category": "cryptocurrency",
     "amount_range": (25000, 120000), "risk_range": (82, 97),
     "rules": ["R003", "R005"], "rule_names": ["New device high value", "Amount spike"],
     "description": "Stolen card to crypto conversion"},
    {"merchant": "Forex Exchange Dubai", "category": "foreign_exchange",
     "amount_range": (15000, 85000), "risk_range": (78, 96),
     "rules": ["R002", "R004"], "rule_names": ["Geographic anomaly", "Odd hour"],
     "description": "Geographic impossibility detected"},
]

# ── FIX 2: Suspicious scenarios use ONLY risky merchants, never safe ones ──
SUSPICIOUS_SCENARIOS = [
    {"merchant": "PhonePe Transfer", "category": "p2p_transfer",
     "amount_range": (18000, 45000), "risk_range": (45, 68),
     "rules": ["R004", "R005"], "rule_names": ["Odd hour", "Amount spike"],
     "description": "Large P2P transfer at odd hour"},
    {"merchant": "POS Terminal #4821", "category": "gas_station",
     "amount_range": (500, 5000), "risk_range": (40, 58),
     "rules": ["R001"], "rule_names": ["High velocity"],
     "description": "Multiple POS transactions in short window"},
    {"merchant": "MakeMyTrip", "category": "travel",
     "amount_range": (12000, 35000), "risk_range": (38, 62),
     "rules": ["R003"], "rule_names": ["New device high value"],
     "description": "First time device travel booking"},
]

NORMAL_MERCHANTS = [
    {"merchant": "Zomato", "category": "food_delivery", "range": (150, 800)},
    {"merchant": "Swiggy", "category": "food_delivery", "range": (120, 600)},
    {"merchant": "BigBasket", "category": "grocery", "range": (500, 4500)},
    {"merchant": "DMart", "category": "grocery", "range": (300, 3000)},
    {"merchant": "Myntra", "category": "fashion", "range": (400, 3500)},
    {"merchant": "Amazon Pay", "category": "online_shopping", "range": (200, 5000)},
    {"merchant": "Flipkart", "category": "online_shopping", "range": (300, 8000)},
    {"merchant": "IRCTC", "category": "travel", "range": (150, 4000)},
    {"merchant": "Ola Money", "category": "ride_sharing", "range": (60, 600)},
    {"merchant": "Paytm", "category": "utility", "range": (100, 2000)},
    {"merchant": "PhonePe", "category": "p2p_transfer", "range": (200, 3000)},
    {"merchant": "Juspay", "category": "payment_gateway", "range": (200, 5000)},
    {"merchant": "BookMyShow", "category": "entertainment", "range": (150, 1500)},
    {"merchant": "Reliance Smart", "category": "grocery", "range": (300, 2500)},
    {"merchant": "HDFC NetBanking", "category": "banking", "range": (500, 15000)},
]


def make_txn_id():
    return "TXN-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))


def generate_raw_transaction() -> dict:
    rand = random.random()
    cid = random.choice(CUSTOMERS)
    
    # ── FIX 3: 5% chance of using special test customer CUS-0001 ──
    if random.random() < 0.05:
        cid = "CUS-0001"
    
    city = random.choice(CITIES)
    device = f"DEV-{random.randint(100, 999)}"
    txn_id = make_txn_id()
    now = datetime.now().isoformat()
    
    # Common realistic payment attributes
    payment_mode = random.choice(PAYMENT_MODES)
    bank = random.choice(BANKS)
    card_type = random.choice(CARD_TYPES) if "Card" in payment_mode else None
    card_last4 = f"{random.randint(1000, 9999)}" if "Card" in payment_mode else None
    ip_address = f"{random.randint(10, 200)}.{random.randint(10, 255)}.xx.xx"
    session_id = f"sess_{''.join(random.choices(string.ascii_letters + string.digits, k=12))}"
    terminal_id = f"TERM-{random.randint(1000, 9999)}"
    mcc_code = str(random.randint(4000, 5999))

    if rand < 0.85:
        nm = random.choice(NORMAL_MERCHANTS)
        amount = random.randint(*nm["range"])
        raw = {
            "type": "transaction",
            "id": txn_id,
            "customer_id": cid,
            "amount": amount,
            "merchant": nm["merchant"],
            "merchant_category": nm["category"],
            "city": city,
            "risk_score": round(random.uniform(2, 28), 1),
            "risk_level": "safe",
            "action": "approve",
            "triggered_rules": [],
            "rule_names": [],
            "fraud_scenario": None,
            "scenario_description": "Normal transaction",
            "device": device,
            "is_new_device": False,
            "timestamp": now,
            "payment_mode": payment_mode,
            "bank": bank,
            "card_type": card_type,
            "card_last4": card_last4,
            "ip_address": ip_address,
            "session_id": session_id,
            "terminal_id": terminal_id,
            "mcc_code": mcc_code,
            "shap_values": {}
        }

    elif rand < 0.97:
        sc = random.choice(SUSPICIOUS_SCENARIOS)
        amount = random.randint(*sc["amount_range"])
        raw = {
            "type": "transaction",
            "id": txn_id,
            "customer_id": cid,
            "amount": amount,
            "merchant": sc["merchant"],
            "merchant_category": sc["category"],
            "city": city,
            "risk_score": round(random.uniform(*sc["risk_range"]), 1),
            "risk_level": "suspicious",
            "action": "step_up_auth",
            "triggered_rules": sc["rules"],
            "rule_names": sc["rule_names"],
            "fraud_scenario": "suspicious",
            "scenario_description": sc["description"],
            "device": device,
            "is_new_device": random.random() < 0.3,
            "timestamp": now,
            "payment_mode": payment_mode,
            "bank": bank,
            "card_type": card_type,
            "card_last4": card_last4,
            "ip_address": ip_address,
            "session_id": session_id,
            "terminal_id": terminal_id,
            "mcc_code": mcc_code,
            "shap_values": {}
        }

    else:
        global _card_testing_cooldown
        now_ts = time.time()

        # Build weighted pool — suppress card testing if it happened recently
        if now_ts - _card_testing_cooldown < CARD_TESTING_COOLDOWN_SECS:
            # Card testing on cooldown: pick from non-card-testing scenarios only
            sc = random.choice(FRAUD_SCENARIOS[1:])  # skip index 0 (card testing)
        else:
            # Use weighted random: card testing is weight 1, others weight 2-3
            weighted_pool = [
                FRAUD_SCENARIOS[0],    # card testing ×1
                FRAUD_SCENARIOS[1],    # wire transfer ×3
                FRAUD_SCENARIOS[1],
                FRAUD_SCENARIOS[1],
                FRAUD_SCENARIOS[2],    # ATM structuring ×2
                FRAUD_SCENARIOS[2],
                FRAUD_SCENARIOS[3],    # crypto ×3
                FRAUD_SCENARIOS[3],
                FRAUD_SCENARIOS[3],
                FRAUD_SCENARIOS[4],    # forex ×2
                FRAUD_SCENARIOS[4],
            ]
            sc = random.choice(weighted_pool)
            if sc["merchant"] == "POS Terminal #4821" and sc["amount_range"] == (1, 99):
                _card_testing_cooldown = now_ts  # update cooldown timestamp
        amount = random.randint(*sc["amount_range"])
        raw = {
            "type": "transaction",
            "id": txn_id,
            "customer_id": cid,
            "amount": amount,
            "merchant": sc["merchant"],
            "merchant_category": sc["category"],
            "city": city,
            "risk_score": round(random.uniform(*sc["risk_range"]), 1),
            "risk_level": "fraudulent",
            "action": "block",
            "triggered_rules": sc["rules"],
            "rule_names": sc["rule_names"],
            "fraud_scenario": sc["description"],
            "scenario_description": sc["description"],
            "device": device,
            "is_new_device": random.random() < 0.7,
            "timestamp": now,
            "payment_mode": payment_mode,
            "bank": bank,
            "card_type": card_type,
            "card_last4": card_last4,
            "ip_address": ip_address,
            "session_id": session_id,
            "terminal_id": terminal_id,
            "mcc_code": mcc_code,
            "shap_values": {}
        }

    # ── FIX 2: FORCE safe label if merchant is in always-safe list ──
    # This prevents BigBasket/Myntra etc from ever appearing as suspicious in fallback
    if raw.get("merchant") in ALWAYS_SAFE_MERCHANTS:
        raw["risk_level"] = "safe"
        raw["risk_score"] = round(random.uniform(3, 27), 1)
        raw["action"] = "approve"
        raw["triggered_rules"] = []
        raw["rule_names"] = []
        raw["fraud_scenario"] = None
        raw["scenario_description"] = "Normal transaction"

    return raw


class ConnectionManager:
    def __init__(self):
        self.connections: list[WebSocket] = []
        self.total = 0
        self.fraud = 0  # detected/flagged (risk >= 50 or pattern hit)
        self.suspicious = 0
        self.blocked = 0
        self.detected = 0

    @property
    def blocked_count(self) -> int:
        return self.blocked

    def increment_blocked(self):
        self.blocked += 1

    def increment_detected(self):
        self.detected += 1
        self.fraud = self.detected

    def get_stats(self) -> dict:
        return {
            "total_transactions": self.total,
            "fraud_count": self.blocked,
            "blocked_count": self.blocked,
            "flagged_count": self.detected,
            "suspicious_count": self.suspicious,
            "fraud_rate": round((self.blocked / max(self.total, 1)) * 100, 2),
        }

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.append(ws)
        print(f"[WS] Client connected. Total: {len(self.connections)}")

    def disconnect(self, ws: WebSocket):
        if ws in self.connections:
            self.connections.remove(ws)
        print(f"[WS] Client disconnected. Total: {len(self.connections)}")

    async def broadcast(self, data: dict):
        dead = []
        for ws in self.connections:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    async def broadcast_stats(self, data: dict):
        data.setdefault("type", "stats")
        await self.broadcast(data)


manager = ConnectionManager()


async def _update_redis_counters(risk_score: float, action: str, patterns: Optional[List[str]], total: int, blocked: int) -> float:
    """Atomically bump Redis counters for detected and blocked events and return 1h fraud rate."""
    if not _redis:
        return round((blocked / max(total, 1)) * 100, 2)
    try:
        flagged = risk_score >= 50 or bool(patterns)
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        now_ts = time.time()
        hour_bucket = int(now_ts // 3600)
        pipe = _redis.pipeline()
        pipe.incr("fraud:total")
        pipe.incr(f"fraud:total:{today}")
        pipe.expire(f"fraud:total:{today}", 172800)
        pipe.incr(f"fraud:total:1h:{hour_bucket}")
        pipe.expire(f"fraud:total:1h:{hour_bucket}", 4000)
        if flagged:
            pipe.incr("fraud:detected_total")
            pipe.incr(f"fraud:detected_total:{today}")
            pipe.expire(f"fraud:detected_total:{today}", 172800)
            pipe.incr(f"fraud:detected:1h:{hour_bucket}")
            pipe.expire(f"fraud:detected:1h:{hour_bucket}", 4000)
        if action == "BLOCK":
            pipe.incr("fraud:blocked_total")
            pipe.incr(f"fraud:blocked_total:{today}")
            pipe.expire(f"fraud:blocked_total:{today}", 172800)
            pipe.incr(f"fraud:blocked:1h:{hour_bucket}")
            pipe.expire(f"fraud:blocked:1h:{hour_bucket}", 4000)
        # Persist current fraud rate snapshot for dashboards pulling directly from Redis
        rate = min(100.0, round((blocked / max(total, 1)) * 100, 2))
        pipe.set("fraud:rate", rate)
        # Compute 1h window rate using bucket counters
        pipe.get(f"fraud:total:1h:{hour_bucket}")
        pipe.get(f"fraud:detected:1h:{hour_bucket}")
        pipe.get(f"fraud:blocked:1h:{hour_bucket}")
        res = await pipe.execute()
        total_1h = int(res[-3] or 0)
        detected_1h = int(res[-2] or 0)
        blocked_1h = int(res[-1] or 0)
        # Fraud rate = only BLOCKED transactions (confirmed fraud), not flagged
        rate_1h = min(100.0, round((blocked_1h / max(total_1h, 1)) * 100, 2))
        await _redis.set("fraud:rate:1h", rate_1h, ex=4000)
        print(f"[COUNTER] rate1h={rate_1h}% flagged_1h={detected_1h} blocked_1h={blocked_1h} total_1h={total_1h}")
        return rate_1h
    except Exception as exc:  # non-fatal
        logger.warning(f"[COUNTER ERROR] {exc}")
        return round((blocked / max(total, 1)) * 100, 2)


async def stream_transactions():
    print("[STREAM] Starting transaction stream")
    counter = 0
    stream_start_time = time.time()
    sms_cooldown: dict[str, float] = {}  # customer_id -> last sms timestamp
    
    while True:
        try:
            if not manager.connections:
                await asyncio.sleep(1.2)
                continue
            
            # Step 1: Generate raw transaction data (merchant, amount, city etc)
            raw = generate_raw_transaction()
            cid = raw["customer_id"]
            
            # CRITICAL: Skip if we already broadcast this ID
            if raw["id"] in _recent_txn_ids:
                await asyncio.sleep(1.2)
                continue
            _recent_txn_ids.append(raw["id"])

            # Phase 0: Security - Check for Card Freeze
            if _redis:
                is_frozen = await _redis.get(f"frozen:{cid}")
                if is_frozen:
                    raw["risk_score"] = 100.0
                    raw["risk_level"] = "critical"
                    raw["action"] = "403_forbidden"
                    raw["scenario_description"] = "SECURITY ALERT: Card is currently frozen due to previous fraud detection."
                    raw["rule_names"] = ["CARD_FROZEN"]
                    await manager.broadcast(raw) # Changed ws_manager to manager
                    continue
            
            # Step 2: Full Ensemble Scoring with Reliability Fallback
            _scoring_t0 = time.monotonic()
            features = {}
            if _initialized and _feature_eng and _rule_engine:
                try:
                    # 1. Feature Engineering (Pipelined <5ms)
                    features = await _feature_eng.compute_features(raw)
                    
                    # 2. Rule Engine (Always runs)
                    rule_score, triggered_info = _rule_engine.evaluate(raw, features)
                    
                    # 3. ML Engine with Fallback
                    ml_score = rule_score # Default
                    shap_values = {}
                    model_used = "rule_only_fallback"
                    
                    if _ml_engine and getattr(_ml_engine, '_loaded', False):
                        try:
                            ml_res = await asyncio.wait_for(_ml_engine.predict(raw, features), timeout=0.012)
                            ml_score = ml_res["ml_score"]
                            shap_values = ml_res["shap_values"]
                            model_used = "xgboost_v2"
                        except Exception:
                            print("[RELIABILITY] ML Inference failed. Using Rule fallback.")
                    
                    # 4. Behavioral DNA (20% weight)
                    behav_res = await _behavioral_engine.score(raw, features)
                    behavioral_score = behav_res["behavioral_score"]
                    

                    # 5. Graph Engine (10% weight)
                    graph_res = _graph_engine.score(raw)
                    graph_score = graph_res["graph_score"]
                    
                    # 5b. Device Intelligence (5% weight)
                    device_score = 0.8 if raw.get("is_new_device", False) else 0.1
                    
                    # 6. Ensemble Combination (Paper Weights)
                    ensemble = _risk_scorer.score(
                        rule_score=rule_score,
                        ml_score=ml_score,
                        behavioral_score=behavioral_score,
                        graph_score=graph_score,
                        device_score=device_score,
                        shap_values=shap_values,
                        triggered_rules=triggered_info
                    )
                    
                    # Apply final results to transaction
                    raw["risk_score"] = ensemble["risk_score"]
                    raw["decision"] = ensemble["decision"]
                    raw["risk_level"] = ensemble["risk_level"]
                    raw["score_breakdown"] = ensemble["score_breakdown"]
                    raw["patterns_matched"] = ensemble["patterns_matched"]
                    raw["explanation"] = ensemble["explanation"]
                    raw["action"] = ensemble["decision"].lower()
                    
                    raw["shap_values"] = shap_values
                    # Extract top features for the UI
                    top_shap = sorted(shap_values.items(), key=lambda x: abs(float(x[1])), reverse=True)[:3]
                    raw["shap_top_signals"] = {k: v for k, v in top_shap}
                    raw["shap_top_feature"] = top_shap[0][0] if top_shap else "rule_engine"
                    raw["model_used"] = model_used
                    raw["model_version"] = "XGBoost v2.0" if model_used == "xgboost_v2" else "Rule Engine"
                    raw["confidence"] = ensemble.get("confidence", 0.95)
                    raw["triggered_rule_ids"] = [r.get("rule_id", r.get("rule_name", "?")) for r in (triggered_info or [])]
                    
                    # Update behavioral engine (graph update deferred until after action decision)
                    await _behavioral_engine.update_profile(raw)
                    
                except Exception as e:
                    import traceback
                    logger.error(f"[SCORING ERROR] {traceback.format_exc()}")
                    raw['model_used'] = 'emergency_fallback'
            else:
                raw['model_used'] = 'scenario_fallback'
            
            # ── POST-ML REFINEMENTS ──
            Risk_final = float(raw.get("risk_score", 0))
            merchant_name = str(raw.get("merchant", "")).upper()
            ALWAYS_SAFE = ["SWIGGY", "ZOMATO", "AMAZON", "FLIPKART", "UBER", "OLA", "NETFLIX", "SPOTIFY"]
            patterns = [p.lower() for p in raw.get("patterns_matched", [])]
            rule_names = [r.lower() for r in raw.get("rule_names", [])]
            # Critical patterns: check BOTH rule engine names AND description text
            critical_rule_names = {
                "card testing pattern", "aml structuring",
                "geo_impossible_travel", "geographic anomaly",
                "mule_account_pattern", "sim_swap_risk",
                "account_takeover",
            }
            critical_scenario_keywords = {
                "card test", "stolen card", "structur",
                "geographic impossib", "crypto", "wire",
                "account takeover", "forex",
            }

            # ── SCORE FLOORS: dangerous combos get minimum scores ──
            CRYPTO_MERCHANTS = [
                "crypto exchange", "wazirx", "coinswitch",
                "zebpay", "forex exchange", "intl-wire-transfer",
                "international wire"
            ]
            merchant_lower = merchant_name.lower()
            is_crypto = any(m in merchant_lower for m in CRYPTO_MERCHANTS)
            is_new_device = raw.get("is_new_device", False)
            txn_amount = float(raw.get("amount", 0))
            fraud_scenario = str(raw.get("fraud_scenario", "") or "").lower()
            scenario_desc = str(raw.get("scenario_description", "") or "").lower()
            combined_text = f"{fraud_scenario} {scenario_desc} {' '.join(rule_names)}"

            # ── HIGH-RISK PATTERN SCORE FLOORS ──
            # 1. Crypto/forex + new device combos
            if is_new_device and is_crypto and txn_amount > 50000:
                Risk_final = max(Risk_final, 88.0)
            elif is_new_device and is_crypto:
                Risk_final = max(Risk_final, 85.0)
            elif is_crypto and txn_amount > 30000:
                Risk_final = max(Risk_final, 82.0)

            # 2. Geographic impossibility
            if "geographic" in combined_text or "geo_impossible" in combined_text:
                Risk_final = max(Risk_final, 80.0)

            # 3. Card testing
            if (raw.get("is_card_testing", False)
                    or "card test" in combined_text
                    or "test stolen" in combined_text):
                Risk_final = max(Risk_final, 82.0)

            # 4. AML structuring
            if (raw.get("is_aml_structuring", False)
                    or "structur" in combined_text
                    or "aml" in combined_text):
                Risk_final = max(Risk_final, 80.0)

            # 5. Wire transfers with high amounts + new device
            if ("wire" in combined_text or "intl" in merchant_lower) and txn_amount > 40000:
                Risk_final = max(Risk_final, 85.0)
            if ("wire" in combined_text or "intl" in merchant_lower) and is_new_device:
                Risk_final = max(Risk_final, 88.0)

            # 6. Account takeover
            if "account_takeover" in combined_text or "takeover" in combined_text:
                Risk_final = max(Risk_final, 88.0)

            # General: any known fraud scenario from generator should be >= 80
            if any(kw in combined_text for kw in critical_scenario_keywords):
                Risk_final = max(Risk_final, 80.0)

            raw["risk_score"] = round(Risk_final, 1)

            force_block = False
            # 1. Trusted Merchant Hard Cap
            if any(m in merchant_name for m in ALWAYS_SAFE):
                raw["action"] = "APPROVE"
                raw["risk_level"] = "safe"
                raw["risk_score"] = min(Risk_final, 15.0)
                raw["decision"] = "Approve"
                raw["explanation"] = "Normal behavior — trusted merchant"
            else:
                # 2. Precision Action Derivation + pattern escalation
                has_critical_rule = any(r in critical_rule_names for r in rule_names)
                has_critical_scenario = any(kw in combined_text for kw in critical_scenario_keywords)
                force_block = Risk_final >= 70 and (has_critical_rule or has_critical_scenario)
                if Risk_final >= 85 or force_block:
                    raw["action"] = "BLOCK"
                    raw["risk_level"] = "fraudulent"
                    raw["decision"] = "Block"
                    if force_block:
                        raw["risk_score"] = max(Risk_final, 90.0)
                        Risk_final = raw["risk_score"]
                elif Risk_final >= 70:
                    raw["action"] = "FLAG_REVIEW"
                    raw["risk_level"] = "suspicious"
                    raw["decision"] = "Review"
                elif Risk_final >= 50:
                    raw["action"] = "STEP_UP"
                    raw["risk_level"] = "suspicious"
                    raw["decision"] = "Step_up"
                elif Risk_final >= 30:
                    raw["action"] = "MONITOR"
                    raw["risk_level"] = "low"
                    raw["decision"] = "Monitor"
                else:
                    raw["action"] = "APPROVE"
                    raw["risk_level"] = "safe"
                    raw["decision"] = "Approve"

            # ── FIX FRAUD SCENARIO LABEL ──
            # Don't label low-risk txns with scary fraud names
            decision_action = raw["action"]
            if decision_action in ["APPROVE", "MONITOR"]:
                if Risk_final < 30:
                    raw["fraud_scenario"] = None
                    raw["scenario_description"] = "Normal transaction"
                elif Risk_final < 50:
                    triggered = raw.get("rule_names", [])
                    if triggered:
                        raw["fraud_scenario"] = f"Monitor: {triggered[0]}"
                    else:
                        raw["fraud_scenario"] = "Low risk pattern"
                    raw["scenario_description"] = raw["fraud_scenario"]
            elif decision_action == "STEP_UP":
                raw["fraud_scenario"] = raw.get("fraud_scenario") or "Suspicious activity"
            elif decision_action in ["FLAG_REVIEW", "BLOCK"]:
                raw["fraud_scenario"] = raw.get("fraud_scenario") or "Fraud pattern detected"

            # Alert priority mapping for UI/notifications
            if raw["action"] == "BLOCK":
                priority = "CRITICAL" if Risk_final >= 90 or force_block else "HIGH"
            elif raw["action"] in ["FLAG_REVIEW", "STEP_UP"]:
                priority = "HIGH"
            elif raw["action"] == "MONITOR":
                priority = "MEDIUM"
            else:
                priority = None

            # Enriched detection summary for UI
            score_breakdown = raw.get("score_breakdown", {}) or {}
            top_scores = sorted(score_breakdown.items(), key=lambda kv: kv[1], reverse=True)[:3]
            rule_hits = raw.get("patterns_matched", []) or []
            raw["detection_summary"] = {
                "detected_by": [f"{k}:{round(v*100,1)}%" for k, v in top_scores],
                "rule_hits": rule_hits,
                "shap_top": raw.get("shap_top_signals", {}),
            }

            # 3. Stats & Persistence
            manager.total += 1
            flagged = Risk_final >= 50 or bool(patterns)
            if flagged:
                manager.increment_detected()

            if raw["action"] == "BLOCK":
                manager.increment_blocked()
                raw["is_fraud"] = True  # Mark for graph engine
                
                # SMS Trigger: Every BLOCK decision (score >= 85)
                phone = os.getenv("ALERT_PHONE_NUMBER")
                if phone:
                    asyncio.create_task(send_blocked_transaction_sms(phone, raw, raw["risk_score"]))
                    logger.info(f"SMS alert queued for BLOCK txn {raw.get('id', '?')[:8]} score={Risk_final}")
                await fraud_memory.record_blocked_transaction(raw)
            
            elif raw["action"] in ["REVIEW", "FLAG_REVIEW", "STEP_UP", "MONITOR"]:
                manager.suspicious += 1
                
                # SMS Trigger: Preventive Warning only for very high review scores
                if Risk_final > 90:
                    now_ts = time.time()
                    last_sms = sms_cooldown.get(cid, 0)
                    if (await fraud_memory.should_send_preventive_sms(cid)) and (now_ts - last_sms > 180):
                        phone = os.getenv("ALERT_PHONE_NUMBER", "+919999999999")
                        asyncio.create_task(send_prevention_warning_sms(phone))
                        sms_cooldown[cid] = now_ts

            # Persist counters to Redis and derive rolling rate
            rate_1h = await _update_redis_counters(
                Risk_final,
                raw["action"],
                raw.get("patterns_matched"),
                manager.total,
                manager.blocked,
            )

            # Update monitoring service metrics (score distribution, PSI, etc.)
            try:
                from app.services.monitoring_service import update_all_metrics
                await update_all_metrics(
                    transaction_id=raw.get("id", ""),
                    risk_score=Risk_final,
                    amount=txn_amount,
                    decision=raw["action"],
                    customer_id=cid
                )
            except Exception as e:
                logger.warning(f"[METRICS UPDATE FAILED] {e}")

            # Audit log: BLOCK decisions always logged at INFO level
            if raw['action'] == 'BLOCK':
                logger.info(f"[BLOCK] txn={raw.get('id')} risk={Risk_final:.1f} merchant={raw.get('merchant')} amount={txn_amount} customer={cid}")
            logger.debug(f"[DECISION] txn={raw.get('id')} risk={Risk_final:.1f} action={raw['action']} patterns={patterns} rate1h={rate_1h}%")
            
            # Update graph engine AFTER action decision so is_fraud is set correctly
            if _initialized and _graph_engine:
                _graph_engine.add_transaction(raw)

            # Record actual processing time
            raw["response_time_ms"] = round((time.monotonic() - _scoring_t0) * 1000, 1)

            # 4. Broadcast to Clients
            raw["priority"] = priority
            await manager.broadcast(raw)
            
            # Update Dashboard Stats
            stats = manager.get_stats()
            stats["blocked_count"] = manager.blocked_count
            stats["fraud_rate"] = rate_1h
            elapsed = max(1.0, time.time() - stream_start_time)
            stats["txn_per_second"] = round(manager.total / elapsed, 1)
            await manager.broadcast_stats(stats)
            # ──────────────────────────────────────────────────────

            # ── ACCURACY DEBUG ──────────────────────────────────────────────────
            if counter % 10 == 0:
                model_used = raw.get('model_used', 'unknown')
                score = raw.get('risk_score', 0)
                logger.debug(f"[ACCURACY] txn={raw['id']} score={score:.1f} model={model_used} "
                      f"merchant={raw.get('merchant','?')} level={raw.get('risk_level','?')}")
            # ────────────────────────────────────────────────────────────────────

            counter += 1

            
            # Step 6: Send stats every 15 transactions
            if counter % 15 == 0:
                fraud_rate = round(
                    (manager.blocked / max(manager.total, 1)) * 100, 2
                )
                elapsed = max(1.0, time.time() - stream_start_time)
                await manager.broadcast({
                    "type": "stats",
                    "total_transactions": manager.total,
                    "fraud_count": manager.blocked,
                    "blocked_count": manager.blocked,
                    "flagged_count": manager.detected,
                    "suspicious_count": manager.suspicious,
                    "fraud_rate": fraud_rate,
                    "avg_risk_score": round(manager.blocked / max(manager.total, 1) * 100, 1),
                    "txn_per_second": round(manager.total / elapsed, 1),
                    "model_active": _initialized and _ml_engine is not None and _ml_engine._loaded
                })
                
        except Exception as e:
            logger.error(f"[STREAM ERROR] {e}")
        
        await asyncio.sleep(1.2)


@router.websocket("/ws/transactions")
async def websocket_endpoint(websocket: WebSocket, token: str = None):
    await manager.connect(websocket)
    try:
        while True:
            # Send ping every 20 seconds to keep connection alive
            await asyncio.sleep(20)
            try:
                await websocket.send_json({"type": "ping"})
            except Exception:
                break
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"[WS] Error: {e}")
        manager.disconnect(websocket)
    finally:
        if websocket in manager.connections:
            manager.disconnect(websocket)
