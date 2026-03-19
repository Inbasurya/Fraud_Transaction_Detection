from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class TransactionCreate(BaseModel):
    transaction_id: str
    user_id: int
    amount: float
    merchant: Optional[str] = None
    location: Optional[str] = None
    device_type: Optional[str] = None
    timestamp: datetime
    is_fraud_label: Optional[bool] = None
    label_source: Optional[str] = None


class TransactionResponse(BaseModel):
    id: int
    transaction_id: str
    user_id: int
    amount: float
    merchant: Optional[str] = None
    location: Optional[str] = None
    device_type: Optional[str] = None
    timestamp: datetime
    created_at: Optional[datetime] = None
    # ML scores
    fraud_probability: Optional[float] = None
    anomaly_score: Optional[float] = None
    behavior_score: Optional[float] = None
    rule_score: Optional[float] = None
    graph_risk_score: Optional[float] = None
    graph_cluster_risk: Optional[float] = None
    risk_score: Optional[float] = None
    risk_category: Optional[str] = None
    reasons: Optional[List[str]] = None
    features: Optional[dict] = None
    behavior_profile: Optional[dict] = None
    anomaly_models: Optional[dict] = None
    alert_id: Optional[int] = None
    # legacy compat
    ml_probability: Optional[float] = None
    final_fraud_score: Optional[float] = None

    class Config:
        from_attributes = True
