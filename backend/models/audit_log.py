"""Audit log ORM model."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Numeric, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from database import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    risk_score = Column(Numeric(5, 2))
    action_taken = Column(String(30))
    model_version = Column(String(50))
    score_breakdown = Column(JSONB)
    triggered_rules = Column(JSONB)
    shap_values = Column(JSONB)
    analyst_override = Column(Boolean, default=False)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
