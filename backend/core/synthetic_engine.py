from __future__ import annotations

"""
Synthetic Transaction Engine — generates realistic banking transaction streams 24/7.
Based on PaySim paper patterns and IEEE-CIS fraud typologies.
All amounts in INR. Uses Indian cities, names, and merchant names.
"""

import hashlib
import math
import random
import string
import time
import uuid
from datetime import datetime, timezone, timedelta

INDIAN_CITIES = [
    {"name": "Mumbai", "lat": 19.0760, "lng": 72.8777},
    {"name": "Delhi", "lat": 28.6139, "lng": 77.2090},
    {"name": "Bangalore", "lat": 12.9716, "lng": 77.5946},
    {"name": "Chennai", "lat": 13.0827, "lng": 80.2707},
    {"name": "Hyderabad", "lat": 17.3850, "lng": 78.4867},
    {"name": "Kolkata", "lat": 22.5726, "lng": 88.3639},
    {"name": "Pune", "lat": 18.5204, "lng": 73.8567},
    {"name": "Ahmedabad", "lat": 23.0225, "lng": 72.5714},
]

INDIAN_FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai",
    "Reyansh", "Ayaan", "Krishna", "Ishaan", "Priya", "Ananya",
    "Diya", "Aisha", "Aadhya", "Riya", "Saanvi", "Kavya",
    "Meera", "Nisha", "Rohan", "Amit", "Suresh", "Rajesh",
]

INDIAN_LAST_NAMES = [
    "Sharma", "Patel", "Singh", "Kumar", "Gupta", "Shah",
    "Reddy", "Nair", "Iyer", "Joshi", "Verma", "Rao",
    "Mehta", "Bhat", "Desai", "Chopra", "Malhotra", "Kapoor",
]

MERCHANT_NAMES = {
    "UPI/Wallets": ["PhonePe", "GPay", "Paytm", "BharatPe", "Cred"],
    "E-commerce": ["Flipkart", "Amazon.in", "Meesho", "Myntra", "Ajio"],
    "Food": ["Swiggy", "Zomato", "Domino's", "Pizza Hut", "KFC"],
    "Banking": ["HDFC Transfer", "SBI IMPS", "ICICI NEFT", "Axis Transfer", "Kotak Wire"],
    "Travel": ["IRCTC", "MakeMyTrip", "Uber", "Ola", "Indigo"],
    "Grocery": ["BigBasket", "Blinkit", "Zepto", "DMart", "Reliance Fresh"],
    "Crypto": ["CoinDCX", "WazirX", "Binance", "ZebPay", "Bitbns"],
    "International": ["PayPal Intl", "AliExpress", "Apple US", "Netflix US", "AWS"],
    "Retail": ["Shoppers Stop", "Lifestyle", "Croma", "Titan", "Tanishq"],
}

class SyntheticTransactionEngine:
    """
    Generates realistic transaction streams that mirror real bank data.
    Based on PaySim paper patterns and IEEE-CIS fraud typologies.
    """

    FRAUD_ATTACK_PATTERNS = {
        "card_testing": {
            "description": "Fraudster tests stolen card with tiny amounts",
            "amount_range": (1, 50),
            "merchants": ["Retail", "Food"],
            "probability": 0.30, 
        },
        "account_takeover": {
            "description": "New device, large amount, unusual hour",
            "amount_range": (15000, 95000),
            "triggers": ["new_device", "odd_hour", "new_merchant"],
            "probability": 0.25, 
        },
        "mule_network": {
            "description": "Money moves through chain of accounts",
            "amount_range": (5000, 50000),
            "probability": 0.05, 
        },
        "aml_structuring": {
            "description": "Just under reporting threshold",
            "amount_range": (45000, 49999),
            "probability": 0.20, 
        },
        "geo_impossibility": {
            "description": "Impossible travel time",
            "amount_range": (2000, 20000),
            "probability": 0.15, 
        },
        "crypto_conversion": {
             "description": "Immediate crypto buy",
             "amount_range": (50000, 200000),
             "probability": 0.05, 
        }
    }

    MERCHANT_CATEGORY_WEIGHTS = {
        "UPI/Wallets": 0.35,
        "E-commerce": 0.20,
        "Food": 0.10,
        "Banking": 0.15,
        "Travel": 0.08,
        "Grocery": 0.07,
        "Crypto": 0.03,
        "International": 0.02
    }

    AMOUNT_DISTRIBUTION = [
        (50, 2000, 60),
        (2000, 15000, 25),
        (15000, 75000, 10),
        (75000, 500000, 5),
    ]

    CUSTOMER_SEGMENTS = [
        {"segment": "student", "avg_txn": 800, "freq": 25},
        {"segment": "professional", "avg_txn": 5000, "freq": 45},
        {"segment": "senior", "avg_txn": 3000, "freq": 15},
        {"segment": "business", "avg_txn": 15000, "freq": 120},
    ]

    def __init__(self, num_customers: int = 500):
        self.customers: dict[str, dict] = {}
        self._init_customers(num_customers)

    def _init_customers(self, n: int) -> None:
        for i in range(1, n + 1):
            cid = f"C{i:05d}"
            self.customers[cid] = self.generate_customer_profile(cid)

    def generate_customer_profile(self, customer_id: str) -> dict:
        segment = random.choice(self.CUSTOMER_SEGMENTS)
        city = random.choice(INDIAN_CITIES)
        first = random.choice(INDIAN_FIRST_NAMES)
        last = random.choice(INDIAN_LAST_NAMES)
        return {
            "customer_id": customer_id,
            "name": f"{first} {last}",
            "segment": segment["segment"],
            "avg_txn_amount": segment["avg_txn"] * random.uniform(0.7, 1.3),
            "home_city": city["name"],
            "home_lat": city["lat"] + random.uniform(-0.1, 0.1),
            "home_lng": city["lng"] + random.uniform(-0.1, 0.1),
            "registered_devices": [
                self._generate_device_fingerprint()
                for _ in range(random.randint(1, 3))
            ],
            "active_hours": sorted(random.sample(range(7, 23), 10)),
        }

    @staticmethod
    def _generate_device_fingerprint() -> str:
        raw = "".join(random.choices(string.ascii_lowercase + string.digits, k=24))
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    @staticmethod
    def _generate_ip() -> str:
        return f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"

    def _pick_amount(self) -> float:
        ranges = self.AMOUNT_DISTRIBUTION
        r = random.choices(ranges, weights=[x[2] for x in ranges], k=1)[0]
        return round(random.uniform(r[0], r[1]), 2)

    def _pick_merchant_category(self) -> str:
        cats = list(self.MERCHANT_CATEGORY_WEIGHTS.keys())
        wts = list(self.MERCHANT_CATEGORY_WEIGHTS.values())
        return random.choices(cats, weights=wts, k=1)[0]

    def generate_transaction(self) -> dict:
        # 1. Select a customer
        customer_id = random.choice(list(self.customers.keys()))
        customer = self.customers[customer_id]

        # 2. Determine if fraud (0.8% chance)
        if random.random() < 0.008:
            return self.generate_fraud_transaction(customer)
        else:
            return self.generate_normal_transaction(customer)

    def generate_normal_transaction(self, customer: dict) -> dict:
        category = self._pick_merchant_category()
        amount = self._pick_amount()
        
        # Clamp amount based on category logic
        if category == "Grocery" and amount > 15000: amount = random.uniform(500, 5000)
        if category == "Food" and amount > 5000: amount = random.uniform(100, 1500)

        merchant_name = random.choice(MERCHANT_NAMES.get(category, ["Unknown Store"]))
        merchant_id = f"{merchant_name.replace(' ', '_').lower()}_{random.randint(1, 50):03d}"

        lat = customer["home_lat"] + random.uniform(-0.02, 0.02)
        lng = customer["home_lng"] + random.uniform(-0.02, 0.02)

        return {
            "transaction_id": f"TXN-{uuid.uuid4().hex[:12].upper()}",
            "user_id": customer["customer_id"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "amount": amount,
            "currency": "INR",
            "merchant_category": category,
            "merchant_id": merchant_id,
            "ip_address": self._generate_ip(),
            "device_id": random.choice(customer["registered_devices"]),
            "location": f"{lat:.4f},{lng:.4f}",
            "city": customer["home_city"],
            "is_fraud": 0,
            "payment_method": "UPI" if amount < 5000 else "Card"
        }

    def generate_fraud_transaction(self, customer: dict) -> dict:
        # Pick attack type
        patterns = list(self.FRAUD_ATTACK_PATTERNS.keys())
        probs = [self.FRAUD_ATTACK_PATTERNS[p]["probability"] for p in patterns]
        attack_type = random.choices(patterns, weights=probs, k=1)[0]
        
        # Start with normal base
        txn = self.generate_normal_transaction(customer)
        txn["is_fraud"] = 1
        txn["fraud_type"] = attack_type

        # Customize for fraud
        if attack_type == "card_testing":
            txn["amount"] = round(random.uniform(1, 50), 2)
            txn["merchant_category"] = random.choice(["Food", "Retail"])
        
        elif attack_type == "account_takeover":
             txn["amount"] = round(random.uniform(15000, 95000), 2)
             txn["device_id"] = self._generate_device_fingerprint() # New device
             txn["merchant_category"] = random.choice(["Crypto", "International", "Retail"])

        elif attack_type == "mule_network":
             txn["amount"] = round(random.uniform(5000, 50000), 2)
             txn["merchant_category"] = "Banking"

        elif attack_type == "aml_structuring":
             txn["amount"] = round(random.uniform(45000, 49999), 2)
             txn["merchant_category"] = "Banking"

        elif attack_type == "geo_impossibility":
             other_city = random.choice([c for c in INDIAN_CITIES if c["name"] != customer["home_city"]])
             txn["city"] = other_city["name"]
             txn["location"] = f"{other_city['lat']:.4f},{other_city['lng']:.4f}"
             txn["amount"] = round(random.uniform(2000, 20000), 2)

        elif attack_type == "crypto_conversion":
             txn["merchant_category"] = "Crypto"
             txn["amount"] = round(random.uniform(50000, 200000), 2)
             txn["device_id"] = self._generate_device_fingerprint()

        return txn
