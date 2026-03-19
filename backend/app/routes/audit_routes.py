"""Audit trail and compliance routes."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.audit_log_model import AuditLog
from app.schemas.case_schema import AuditLogResponse
from app.config import settings

router = APIRouter()


@router.get(
    "/{transaction_id}",
    response_model=AuditLogResponse,
    summary="Get full decision explanation for a transaction",
)
def get_audit_log(
    transaction_id: str,
    db: Session = Depends(get_db),
):
    """Return full fraud detection decision explanation.

    Includes risk scores, rules triggered, SHAP values,
    behavioral signals, and graph features for the given transaction.
    """
    log = (
        db.query(AuditLog)
        .filter(AuditLog.transaction_id == transaction_id)
        .order_by(AuditLog.timestamp.desc())
        .first()
    )
    if not log:
        raise HTTPException(status_code=404, detail="Audit log not found for this transaction")
    return log


@router.get(
    "/",
    response_model=list[AuditLogResponse],
    summary="List audit logs with filters",
)
def list_audit_logs(
    action: Optional[str] = None,
    min_risk: Optional[float] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List audit log entries with optional filtering."""
    query = db.query(AuditLog)

    if action:
        query = query.filter(AuditLog.action_taken == action.upper())
    if min_risk is not None:
        query = query.filter(AuditLog.risk_score >= min_risk)

    return query.order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit).all()


def create_audit_log(
    db: Session,
    transaction_id: str,
    risk_score: float,
    action_taken: str,
    score_breakdown: dict | None = None,
    rules_triggered: list | None = None,
    model_version: str | None = None,
    shap_values: dict | None = None,
    behavioral_signals: dict | None = None,
    graph_features: dict | None = None,
    feature_values: dict | None = None,
    explanation_text: str | None = None,
) -> AuditLog:
    """Create an audit log entry for a fraud decision."""
    log = AuditLog(
        transaction_id=transaction_id,
        risk_score=risk_score,
        score_breakdown=score_breakdown,
        rules_triggered=rules_triggered,
        model_version=model_version,
        action_taken=action_taken,
        shap_values=shap_values,
        behavioral_signals=behavioral_signals,
        graph_features=graph_features,
        feature_values=feature_values,
        explanation_text=explanation_text,
    )
    db.add(log)
    db.commit()
    return log


def archive_old_records(db: Session) -> int:
    """Auto-archive transactions older than retention period (7 years)."""
    cutoff = datetime.utcnow() - timedelta(days=settings.DATA_RETENTION_YEARS * 365)
    count = (
        db.query(AuditLog)
        .filter(AuditLog.timestamp < cutoff)
        .delete(synchronize_session=False)
    )
    db.commit()
    return count
