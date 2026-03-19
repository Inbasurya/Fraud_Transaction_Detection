"""Customer ORM model."""

from datetime import datetime, timezone
from sqlalchemy import Column, String, Numeric, Integer, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from database import Base


class Customer(Base):
    __tablename__ = "customers"

    id = Column(String(40), primary_key=True)
    segment = Column(String(30))
    home_city = Column(String(50))
    avg_txn_amount = Column(Numeric(12, 2))
    monthly_txn_count = Column(Integer, default=0)
    risk_tier = Column(String(10), default="low")
    total_transactions = Column(Integer, default=0)
    fraud_count = Column(Integer, default=0)
    last_seen_at = Column(DateTime(timezone=True))
    registered_devices = Column(JSONB)
    behavioral_profile = Column(JSONB)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
