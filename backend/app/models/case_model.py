"""Case management model for fraud investigation workflow."""

from datetime import datetime
from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class Case(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(UUID(as_uuid=True), ForeignKey("alerts.id"), nullable=True, index=True)
    assigned_analyst = Column(String, nullable=True, index=True)
    status = Column(String, default="OPEN", index=True)  # OPEN / INVESTIGATING / RESOLVED
    priority = Column(String, default="MEDIUM")  # LOW / MEDIUM / HIGH / CRITICAL
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    resolution = Column(String, nullable=True)  # confirmed_fraud / false_positive / inconclusive
    notes = Column(Text, nullable=True)
    sar_required = Column(Boolean, default=False)
    sar_filed_at = Column(DateTime, nullable=True)

    alert = relationship("Alert", backref="case")
