import random
import time
import json
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("HardNegativeInjector")

# High-risk categories and merchants
HIGH_RISK_MERCHANTS = ["CRYPTO_EXCHANGE_INR", "GLOBAL_WIRE_TRANSFER", "PREMIUM_GIFT_CARDS", "VIP_CASINO_PLAY"]
HIGH_RISK_CITIES = ["International", "Unknown", "Cayman Islands", "Zurich"]

def generate_hard_negative(customer_id: str):
    """
    Generates a 'Hard Negative' transaction:
    A high-risk pattern that is technically 'Safe' (e.g., high amount at a risky merchant 
    but consistent with the customer's high-wealth profile).
    """
    return {
        "id": f"TXN-HN-{random.randint(100000, 999999)}",
        "customer_id": customer_id,
        "amount": random.randint(45000, 49999),  # Borders AML structuring
        "merchant": random.choice(HIGH_RISK_MERCHANTS),
        "merchant_category": "cryptocurrency",
        "city": random.choice(HIGH_RISK_CITIES),
        "device": f"DEV-{random.randint(100, 999)}",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "is_hard_negative": True,
        "label": 0  # CRITICAL: This is a NEGATIVE (Safe) sample
    }

def inject():
    data_dir = Path(__file__).parent
    output_file = data_dir / "hard_negatives.json"
    
    # Generate 500 hard negatives for training
    hard_negatives = [generate_hard_negative(f"CUS-{random.randint(1000, 9999)}") for _ in range(500)]
    
    with open(output_file, "w") as f:
        json.dump(hard_negatives, f, indent=2)
    
    logger.info(f"✓ Successfully injected 500 Hard Negative samples to {output_file}")

if __name__ == "__main__":
    inject()
