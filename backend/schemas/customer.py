from pydantic import BaseModel
from typing import List, Optional

class CustomerProfile(BaseModel):
    customer_id: str
    name: str
    segment: str
    risk_tier: str
    total_transactions: int
    avg_risk_score: float
    total_amount: float
    home_city: str
    registered_devices: List[str]
    recent_transactions: List[dict]

class CustomerListItem(BaseModel):
    customer_id: str
    txn_count: int
    avg_risk: float
    fraud_count: int
    total_volume: float
    last_seen: Optional[str] = None

class CustomerListResponse(BaseModel):
    data: List[CustomerListItem]
