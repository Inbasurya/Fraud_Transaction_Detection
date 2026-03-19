"""Locust load testing script for fraud detection system.

Simulates 1000 concurrent users submitting transactions.
Mix: 95% legitimate, 5% fraudulent.
Target: <200ms p95 latency for fraud decision.

Run: locust -f load_test.py --host=http://localhost:8000
"""

from __future__ import annotations

import json
import random
import time
import uuid

from locust import HttpUser, between, task

MERCHANTS = [
    "Amazon", "Walmart", "Target", "Best Buy", "Starbucks",
    "McDonald's", "Shell", "Costco", "Home Depot", "Nike",
    "Apple Store", "Uber", "Netflix", "Spotify", "Steam",
    "Whole Foods", "CVS", "Walgreens", "7-Eleven", "Subway",
]

LOCATIONS = [
    "New York", "Los Angeles", "Chicago", "Houston", "Phoenix",
    "San Francisco", "Miami", "Dallas", "Seattle", "Boston",
    "London", "Tokyo", "Paris", "Sydney", "Singapore",
    "Toronto", "Berlin", "Mumbai", "Dubai", "Seoul",
]

DEVICES = ["mobile", "desktop", "tablet", "pos_terminal"]


def _generate_legit_transaction(user_id: int) -> dict:
    return {
        "transaction_id": f"LD-{uuid.uuid4().hex[:12]}",
        "user_id": user_id,
        "amount": round(random.uniform(5, 500), 2),
        "merchant": random.choice(MERCHANTS),
        "location": random.choice(LOCATIONS[:10]),
        "device_type": random.choice(DEVICES),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def _generate_fraud_transaction(user_id: int) -> dict:
    fraud_type = random.choice(["high_amount", "velocity", "location_jump", "odd_time"])

    tx = {
        "transaction_id": f"FR-{uuid.uuid4().hex[:12]}",
        "user_id": user_id,
        "merchant": random.choice(MERCHANTS),
        "device_type": random.choice(DEVICES),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    if fraud_type == "high_amount":
        tx["amount"] = round(random.uniform(5000, 50000), 2)
        tx["location"] = random.choice(LOCATIONS)
    elif fraud_type == "velocity":
        tx["amount"] = round(random.uniform(100, 1000), 2)
        tx["location"] = random.choice(LOCATIONS[:5])
    elif fraud_type == "location_jump":
        tx["amount"] = round(random.uniform(200, 3000), 2)
        tx["location"] = random.choice(LOCATIONS[10:])  # Foreign locations
    else:
        tx["amount"] = round(random.uniform(500, 5000), 2)
        tx["location"] = random.choice(LOCATIONS)

    return tx


class FraudDetectionUser(HttpUser):
    """Simulates a user submitting transactions to the fraud detection system."""

    wait_time = between(0.5, 2.0)

    def on_start(self):
        self.user_id = random.randint(1, 750)
        # Register user (ignore if exists)
        self.client.post(
            "/api/auth/register",
            json={
                "email": f"loadtest_{self.user_id}@test.com",
                "password": "testpassword123",
                "name": f"Load Test User {self.user_id}",
            },
            catch_response=True,
        )
        # Login
        resp = self.client.post(
            "/api/auth/login",
            json={
                "email": f"loadtest_{self.user_id}@test.com",
                "password": "testpassword123",
            },
            catch_response=True,
        )
        if resp.status_code == 200:
            data = resp.json()
            self.token = data.get("access_token", "")
        else:
            self.token = ""

    @property
    def _headers(self):
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {}

    @task(19)  # 95% legitimate
    def submit_legit_transaction(self):
        tx = _generate_legit_transaction(self.user_id)
        with self.client.post(
            "/api/transaction/simulate",
            json=tx,
            headers=self._headers,
            catch_response=True,
            name="/api/transaction/simulate [legit]",
        ) as resp:
            if resp.status_code in (200, 201):
                resp.success()
            else:
                resp.failure(f"Status {resp.status_code}")

    @task(1)  # 5% fraudulent
    def submit_fraud_transaction(self):
        tx = _generate_fraud_transaction(self.user_id)
        with self.client.post(
            "/api/transaction/simulate",
            json=tx,
            headers=self._headers,
            catch_response=True,
            name="/api/transaction/simulate [fraud]",
        ) as resp:
            if resp.status_code in (200, 201):
                resp.success()
            else:
                resp.failure(f"Status {resp.status_code}")

    @task(3)
    def check_alerts(self):
        self.client.get("/api/alerts/live?limit=10", headers=self._headers, name="/api/alerts/live")

    @task(2)
    def check_stats(self):
        self.client.get("/api/fraud/stats", headers=self._headers, name="/api/fraud/stats")

    @task(1)
    def check_system_health(self):
        self.client.get("/api/system/health", name="/api/system/health")

    @task(1)
    def check_metrics(self):
        self.client.get("/metrics", name="/metrics")
