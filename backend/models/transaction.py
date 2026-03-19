"""Transaction ORM model."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Numeric, Boolean, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(String(40), nullable=False, index=True)
    amount = Column(Numeric(15, 2), nullable=False)
    merchant_id = Column(String(60))
    merchant_category = Column(String(40))
    lat = Column(Numeric(9, 6))
    lng = Column(Numeric(9, 6))
    device_fingerprint = Column(String(100))
    ip_address = Column(String(45))
    risk_score = Column(Numeric(5, 2))
    risk_level = Column(String(20))
    action_taken = Column(String(30))
    score_breakdown = Column(JSONB)
    triggered_rules = Column(JSONB)
    shap_values = Column(JSONB)
    is_fraud = Column(Boolean, default=None)  # None = unknown
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("ix_txn_customer_created", "customer_id", "created_at"),
        Index("ix_txn_risk_level", "risk_level"),
    )
