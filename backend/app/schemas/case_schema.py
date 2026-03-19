"""Pydantic schemas for case management."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CaseCreate(BaseModel):
    alert_id: int
    priority: str = "MEDIUM"
    notes: Optional[str] = None

    model_config = {"json_schema_extra": {
        "example": {"alert_id": 1, "priority": "HIGH", "notes": "Suspicious transaction pattern"}
    }}


class CaseUpdate(BaseModel):
    status: Optional[str] = None
    resolution: Optional[str] = None
    notes: Optional[str] = None
    assigned_analyst: Optional[str] = None
    priority: Optional[str] = None


class CaseResponse(BaseModel):
    id: int
    alert_id: Optional[int] = None
    assigned_analyst: Optional[str] = None
    status: str
    priority: str
    created_at: datetime
    resolved_at: Optional[datetime] = None
    resolution: Optional[str] = None
    notes: Optional[str] = None
    sar_required: bool
    sar_filed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class SARFiling(BaseModel):
    sar_reference: Optional[str] = None
    notes: Optional[str] = None


class AuditLogResponse(BaseModel):
    id: int
    transaction_id: str
    timestamp: datetime
    risk_score: float
    score_breakdown: Optional[dict] = None
    rules_triggered: Optional[list] = None
    model_version: Optional[str] = None
    action_taken: str
    analyst_override: Optional[str] = None
    shap_values: Optional[dict] = None
    behavioral_signals: Optional[dict] = None
    graph_features: Optional[dict] = None
    feature_values: Optional[dict] = None
    explanation_text: Optional[str] = None

    model_config = {"from_attributes": True}


class OTPRequest(BaseModel):
    transaction_id: str
    customer_id: str
    channel: str = "sms"  # sms or email


class OTPVerify(BaseModel):
    otp_code: str
