"""Audit log model for compliance and explainability."""

import uuid
from datetime import datetime
from sqlalchemy import Column, Float, String, DateTime, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    transaction_id = Column(UUID(as_uuid=True), index=True, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    risk_score = Column(Float, nullable=False)
    score_breakdown = Column(JSON, nullable=True)  # {"ml": 0.4, "anomaly": 0.25, ...}
    rules_triggered = Column(JSON, nullable=True)  # ["velocity_check", "amount_spike"]
    model_version = Column(String, nullable=True)
    action_taken = Column(String, nullable=False)  # APPROVE / BLOCK / STEP_UP / REVIEW
    analyst_override = Column(String, nullable=True)
    shap_values = Column(JSON, nullable=True)  # SHAP explanations for ML prediction
    behavioral_signals = Column(JSON, nullable=True)
    graph_features = Column(JSON, nullable=True)
    feature_values = Column(JSON, nullable=True)
    explanation_text = Column(Text, nullable=True)
