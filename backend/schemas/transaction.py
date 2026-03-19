"""Pydantic schemas for transactions."""

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class TransactionCreate(BaseModel):
    customer_id: str
    amount: float = Field(gt=0)
    merchant_id: str
    merchant_category: str
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    device_fingerprint: str
    ip_address: Optional[str] = None
    timestamp: Optional[float] = None  # epoch seconds


class TransactionResponse(BaseModel):
    id: UUID
    customer_id: str
    amount: float
    merchant_id: str
    merchant_category: str
    lat: float
    lng: float
    device_fingerprint: str
    ip_address: Optional[str]
    risk_score: Optional[float]
    risk_level: Optional[str]
    action_taken: Optional[str]
    score_breakdown: Optional[Dict]
    triggered_rules: Optional[List]
    shap_values: Optional[Dict]
    is_fraud: Optional[bool]
    created_at: datetime

    model_config = {"from_attributes": True}


class TransactionList(BaseModel):
    transactions: List[TransactionResponse]
    total: int
    page: int
    page_size: int
