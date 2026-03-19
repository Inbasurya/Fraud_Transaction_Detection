#!/usr/bin/env python3
"""
transaction_streamer.py
───────────────────────
Generates realistic synthetic banking transactions on-the-fly using
SyntheticTransactionEngine and streams them to the backend API.
"""

import sys
import time
import requests
import argparse
from pathlib import Path
import random

# Adjust path to find backend module
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

try:
    from backend.core.synthetic_engine import SyntheticTransactionEngine
except ImportError as e:
    print(f"Error importing SyntheticTransactionEngine: {e}")
    print(f"Make sure {ROOT_DIR} is in PYTHONPATH")
    sys.exit(1)

API_URL = "http://localhost:8000/transaction/simulate"
HEADERS = {"Content-Type": "application/json"}

def _get_status_icon(tx_data: dict, resp_json: dict) -> str:
    """Returns a status icon based on risk score."""
    risk_score = resp_json.get("risk_score", 0)
    is_fraud = tx_data.get("is_fraud", 0)
    
    if is_fraud:
        # Ground truth was FRAUD
        if risk_score > 80:
            return "✅ BLOCKED (TP)"
        else:
            return "❌ MISSED (FN)"
    else:
        # Ground truth was NORMAL
        if risk_score > 80:
            return "❌ FALSE POS (FP)"
        elif risk_score > 50:
            return "⚠️ WARN"
        else:
            return "✅ OK"

def stream_transactions(tps: float = 1.0):
    print(f"🚀 Starting Real-Time Transaction Stream at {tps} tx/sec")
    print(f"📡 API Endpoint: {API_URL}")
    print("-" * 70)
    
    engine = SyntheticTransactionEngine()
    delay = 1.0 / max(tps, 0.1)
    
    tx_count = 0
    fraud_count = 0
    
    try:
        while True:
            # 1. Generate Transaction
            tx_data = engine.generate_transaction()
            is_fraud = tx_data.get("is_fraud", 0)
            
            # 2. Send to Backend
            start_ts = time.time()
            try:
                resp = requests.post(API_URL, json=tx_data, headers=HEADERS, timeout=2.0)
                latency_ms = (time.time() - start_ts) * 1000
                
                if resp.status_code == 200:
                    res = resp.json()
                    status_msg = _get_status_icon(tx_data, res)
                    score = res.get("risk_score", 0)
                    tid = str(res.get("transaction_id", "?"))[-6:]
                    
                    # Color coding for terminal output
                    color_code = "\033[92m" # Green
                    if score > 80: color_code = "\033[91m" # Red
                    elif score > 50: color_code = "\033[93m" # Yellow
                    
                    reset_code = "\033[0m"
                    
                    print(f"TX:{tid} | Amt:₹{tx_data['amount']:<8} | Risk:{color_code}{score:<5.1f}{reset_code} | {status_msg:<15} | {latency_ms:.0f}ms")
                    
                    tx_count += 1
                    if is_fraud: fraud_count += 1
                    
                    # AFTER FIXING — VERIFY STATS
                    if tx_count % 100 == 0:
                        rate = (fraud_count / tx_count) * 100
                        print(f"📊 STATS | Total: {tx_count} | Fraud: {fraud_count} | Rate: {rate:.2f}%")

                    
                else:
                    print(f"❌ API Error: {resp.status_code} - {resp.text[:50]}")
            
            except requests.RequestException as e:
                print(f"❌ Connection Error: {e}")
                time.sleep(2)
            
            time.sleep(delay)
            
    except KeyboardInterrupt:
        print("\n" + "=" * 60)
        print(f"🛑 Stream Stopped. Total: {tx_count}, Frauds: {fraud_count}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rate", type=float, default=2.0, help="Transactions per second")
    args = parser.parse_args()
    
    stream_transactions(tps=args.rate)
