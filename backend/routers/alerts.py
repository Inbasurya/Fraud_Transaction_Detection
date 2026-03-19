from __future__ import annotations

"""
Alerts router — list, update, and manage fraud alerts.
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func, desc, update
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from database import get_db
from auth.jwt_handler import get_current_user
from schemas.alert import AlertResponse, AlertUpdate, AlertList

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])


from models.transaction import Transaction

@router.get("/", response_model=AlertList)
async def list_alerts(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Fetch recent high-risk transactions from DB as alerts."""
    q = (select(Transaction)
         .where(Transaction.risk_score > 60)
         .order_by(desc(Transaction.risk_score))
         .limit(100))
    rows = (await db.execute(q)).scalars().all()

    # Map to Alert response schema format
    items = []
    for row in rows:
        item = {
            "id": str(row.id),
            "transaction_id": str(row.id),
            "customer_id": row.customer_id,
            "merchant_category": row.merchant_category,
            "amount": float(row.amount) if row.amount else 0.0,
            "risk_score": float(row.risk_score) if row.risk_score else 0.0,
            "severity": row.risk_level,
            "status": "new",
            "fraud_scenario": row.triggered_rules,
            "created_at": row.created_at.isoformat() if row.created_at else None
        }
        items.append(item)

    return AlertList(alerts=items, total=len(items), page=1, size=100)


@router.patch("/{alert_id}", response_model=AlertResponse)
async def update_alert(
    alert_id: str,
    payload: AlertUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    alert = await db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(404, "Alert not found")

    update_data = payload.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(alert, k, v)

    await db.commit()
    await db.refresh(alert)
    return alert


@router.get("/stats")
async def alert_stats(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Summary counts by status and severity."""
    status_q = select(Alert.status, func.count()).group_by(Alert.status)
    severity_q = select(Alert.severity, func.count()).group_by(Alert.severity)

    status_rows = (await db.execute(status_q)).all()
    severity_rows = (await db.execute(severity_q)).all()

    return {
        "by_status": {row[0]: row[1] for row in status_rows},
        "by_severity": {row[0]: row[1] for row in severity_rows},
    }
