"""Alert ORM model."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID
from database import Base


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    customer_id = Column(String(40), nullable=False, index=True)
    alert_type = Column(String(50))
    severity = Column(String(20))
    title = Column(String(200))
    description = Column(Text)
    status = Column(String(20), default="open")
    assigned_to = Column(String(100))
    resolved_at = Column(DateTime(timezone=True))
    resolution = Column(String(50))
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("ix_alert_status", "status"),
        Index("ix_alert_severity", "severity"),
    )
