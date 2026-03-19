from __future__ import annotations

"""Pydantic schemas for dashboard stats."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class DashboardStats(BaseModel):
    total_transactions: int = 0
    total_fraud: int = 0
    total_suspicious: int = 0
    fraud_rate: float = 0.0
    amount_blocked: float = 0.0
    avg_risk_score: float = 0.0
    model_accuracy: float = 0.0
    transactions_per_second: float = 0.0
    active_alerts: int = 0


class CustomerProfile(BaseModel):
    customer_id: str
    segment: Optional[str]
    home_city: Optional[str]
    avg_txn_amount: float
    monthly_txn_count: int
    risk_tier: str
    total_transactions: int
    fraud_count: int
    recent_transactions: List[Dict[str, Any]]
    behavioral_profile: Optional[Dict[str, Any]]
