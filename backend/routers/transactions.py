from __future__ import annotations

"""
Transactions router — CRUD + scoring pipeline for transactions.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from database import get_db
from models.transaction import Transaction
from schemas.transaction import TransactionCreate, TransactionResponse, TransactionList
from auth.jwt_handler import get_current_user

router = APIRouter(prefix="/api/transactions", tags=["Transactions"])


@router.post("/", response_model=TransactionResponse, status_code=201)
async def create_transaction(
    payload: TransactionCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Ingest a new transaction and persist it."""
    txn = Transaction(
        id=uuid.uuid4(),
        customer_id=payload.customer_id,
        amount=payload.amount,
        merchant_id=payload.merchant_id,
        merchant_category=payload.merchant_category,
        lat=payload.lat,
        lng=payload.lng,
        device_fingerprint=payload.device_fingerprint,
        ip_address=payload.ip_address,
        risk_score=0.0,
        risk_level="low",
        is_fraud=False,
        created_at=datetime.now(timezone.utc),
    )
    db.add(txn)
    await db.commit()
    await db.refresh(txn)
    return txn


@router.get("/")
async def list_transactions(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    risk_level: Optional[str] = None,
    customer_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """List transactions with pagination and optional filters."""
    q = select(Transaction)
    count_q = select(func.count(Transaction.id))

    if risk_level:
        q = q.where(Transaction.risk_level == risk_level)
        count_q = count_q.where(Transaction.risk_level == risk_level)
    if customer_id:
        q = q.where(Transaction.customer_id == customer_id)
        count_q = count_q.where(Transaction.customer_id == customer_id)

    total = (await db.execute(count_q)).scalar() or 0

    q = q.order_by(desc(Transaction.created_at)).offset((page - 1) * size).limit(size)
    rows = (await db.execute(q)).scalars().all()

    # Convert UUIDs to strings manually because Pydantic gets mad if we don't return the exact schema type
    items = []
    for row in rows:
        item = {
            "id": str(row.id),
            "customer_id": row.customer_id,
            "amount": float(row.amount) if row.amount else 0.0,
            "merchant_id": row.merchant_id,
            "merchant_category": row.merchant_category,
            "lat": float(row.lat) if row.lat else None,
            "lng": float(row.lng) if row.lng else None,
            "device_fingerprint": row.device_fingerprint,
            "ip_address": row.ip_address,
            "risk_score": float(row.risk_score) if row.risk_score else 0.0,
            "risk_level": row.risk_level,
            "is_fraud": row.is_fraud,
            "action_taken": row.action_taken,
            "created_at": row.created_at.isoformat() if row.created_at else None
        }
        items.append(item)

    return {"transactions": items, "total": total, "page": page, "size": size}


@router.get("/{txn_id}")
async def get_transaction(
    txn_id: str, 
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    from fastapi import HTTPException
    
    # Needs to match uuid
    try:
        import uuid
        uuid_obj = uuid.UUID(txn_id)
    except ValueError:
        raise HTTPException(400, "Invalid transaction ID format")

    row = await db.get(Transaction, uuid_obj)
    if not row:
        raise HTTPException(404, "Transaction not found")
        
    return {
        "id": str(row.id),
        "customer_id": row.customer_id,
        "amount": float(row.amount) if row.amount else 0.0,
        "merchant_id": row.merchant_id,
        "merchant_category": row.merchant_category,
        "lat": float(row.lat) if row.lat else None,
        "lng": float(row.lng) if row.lng else None,
        "device_fingerprint": row.device_fingerprint,
        "ip_address": row.ip_address,
        "risk_score": float(row.risk_score) if row.risk_score else 0.0,
        "risk_level": row.risk_level,
        "is_fraud": row.is_fraud,
        "action_taken": row.action_taken,
        "score_breakdown": row.score_breakdown,
        "triggered_rules": row.triggered_rules,
        "shap_values": row.shap_values,
        "created_at": row.created_at.isoformat() if row.created_at else None
    }
