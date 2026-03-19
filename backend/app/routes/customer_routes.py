"""Customer intelligence API routes.

POST /customers/register  — Register a new customer profile
GET  /customers/{customer_id}  — Get customer profile and risk data
GET  /customers/  — List all customers
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.customer_model import Customer
from app.models.device_model import Device
from app.schemas.customer_schema import CustomerCreate, CustomerResponse, DeviceResponse

router = APIRouter()


@router.post("/register", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def register_customer(payload: CustomerCreate, db: Session = Depends(get_db)):
    """Register a new customer with behavioral profile."""
    existing = db.query(Customer).filter(
        (Customer.customer_id == payload.customer_id) | (Customer.email == payload.email)
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Customer with this ID or email already exists",
        )

    customer = Customer(**payload.model_dump())
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(customer_id: str, db: Session = Depends(get_db)):
    """Get customer profile by customer_id."""
    customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.get("/", response_model=List[CustomerResponse])
def list_customers(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    """List customers ordered by risk level."""
    return (
        db.query(Customer)
        .order_by(Customer.updated_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/{customer_id}/devices", response_model=List[DeviceResponse])
def get_customer_devices(customer_id: str, db: Session = Depends(get_db)):
    """Get all devices registered to a customer."""
    return (
        db.query(Device)
        .filter(Device.customer_id == customer_id)
        .order_by(Device.last_used.desc())
        .all()
    )
