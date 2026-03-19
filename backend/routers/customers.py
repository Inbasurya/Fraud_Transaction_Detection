from __future__ import annotations

"""
Customers router — customer profiles and transaction history.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from database import get_db
from models.customer import Customer
from models.transaction import Transaction
from schemas.customer import CustomerProfile, CustomerListResponse
from auth.jwt_handler import get_current_user

router = APIRouter(prefix="/api/customers", tags=["Customers"])


@router.get("/{customer_id}", response_model=CustomerProfile)
async def get_customer_profile(
    customer_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    customer = await db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(404, "Customer not found")

    # Aggregate stats
    stats_q = select(
        func.count(Transaction.id).label("count"),
        func.avg(Transaction.risk_score).label("avg_risk"),
        func.sum(Transaction.amount).label("total_amount"),
    ).where(Transaction.customer_id == customer_id)
    stats = (await db.execute(stats_q)).one_or_none()

    # Recent transactions
    recent_q = (
        select(Transaction)
        .where(Transaction.customer_id == customer_id)
        .order_by(desc(Transaction.created_at))
        .limit(10)
    )
    recent = (await db.execute(recent_q)).scalars().all()

    return CustomerProfile(
        customer_id=customer.id,
        name=customer.name or "",
        segment=customer.segment or "",
        risk_tier=customer.risk_tier or "low",
        total_transactions=stats.count if stats else 0,
        avg_risk_score=round(float(stats.avg_risk or 0), 4),
        total_amount=round(float(stats.total_amount or 0), 2),
        home_city=customer.home_city or "",
        registered_devices=customer.registered_devices or [],
        recent_transactions=[
            {
                "id": str(t.id),
                "amount": float(t.amount),
                "risk_score": float(t.risk_score or 0),
                "merchant_category": t.merchant_category or "",
                "created_at": t.created_at.isoformat() if t.created_at else "",
            }
            for t in recent
        ],
    )


@router.get("/")
async def list_customers(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Aggregate customer statistics directly from transactions."""
    q = select(
        Transaction.customer_id,
        func.count(Transaction.id).label("txn_count"),
        func.avg(Transaction.risk_score).label("avg_risk"),
        func.sum(
            func.cast(Transaction.risk_level == "fraudulent", sqlalchemy.Integer)
        ).label("fraud_count"),
        func.sum(Transaction.amount).label("total_volume"),
        func.max(Transaction.created_at).label("last_seen"),
    ).group_by(Transaction.customer_id).order_by(desc("fraud_count")).limit(100)
    
    import sqlalchemy
    rows = (await db.execute(q)).all()

    items = []
    for row in rows:
        items.append({
            "customer_id": row.customer_id,
            "txn_count": row.txn_count,
            "avg_risk": float(row.avg_risk) if row.avg_risk is not None else 0.0,
            "fraud_count": int(row.fraud_count) if row.fraud_count is not None else 0,
            "total_volume": float(row.total_volume) if row.total_volume is not None else 0.0,
            "last_seen": row.last_seen.isoformat() if row.last_seen else None
        })

    return items
