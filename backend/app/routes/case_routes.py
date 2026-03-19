"""Case management CRUD API with role-based access control."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.case_model import Case
from app.models.alert_model import Alert
from app.models.transaction_model import Transaction
from app.schemas.case_schema import CaseCreate, CaseUpdate, CaseResponse, SARFiling
from app.utils.auth_handler import get_current_user
from app.models.user_model import User

router = APIRouter()


def _require_role(user: User, allowed_roles: list[str]) -> None:
    if user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{user.role}' not authorized. Required: {allowed_roles}",
        )


@router.post(
    "/",
    response_model=CaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a case from an alert",
)
def create_case(
    body: CaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new investigation case linked to a fraud alert.

    Requires analyst, manager, or admin role.
    """
    _require_role(current_user, ["analyst", "manager", "admin"])

    alert = db.query(Alert).filter(Alert.id == body.alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    case = Case(
        alert_id=body.alert_id,
        assigned_analyst=current_user.email,
        status="OPEN",
        priority=body.priority,
        notes=body.notes,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


@router.get(
    "/",
    response_model=list[CaseResponse],
    summary="List cases with filters",
)
def list_cases(
    status_filter: Optional[str] = Query(None, alias="status"),
    priority: Optional[str] = None,
    analyst: Optional[str] = None,
    sar_required: Optional[bool] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List cases. Analysts see only their own; managers/admins see all."""
    query = db.query(Case)

    # Role-based filtering
    if current_user.role == "analyst":
        query = query.filter(Case.assigned_analyst == current_user.email)

    if status_filter:
        query = query.filter(Case.status == status_filter.upper())
    if priority:
        query = query.filter(Case.priority == priority.upper())
    if analyst and current_user.role in ("manager", "admin"):
        query = query.filter(Case.assigned_analyst == analyst)
    if sar_required is not None:
        query = query.filter(Case.sar_required == sar_required)

    return query.order_by(Case.created_at.desc()).offset(offset).limit(limit).all()


@router.get(
    "/{case_id}",
    response_model=CaseResponse,
    summary="Get case detail with transaction history",
)
def get_case(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get full case detail including linked transaction history."""
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    if current_user.role == "analyst" and case.assigned_analyst != current_user.email:
        raise HTTPException(status_code=403, detail="Not authorized to view this case")

    return case


@router.patch(
    "/{case_id}",
    response_model=CaseResponse,
    summary="Update case status/resolution/notes",
)
def update_case(
    case_id: int,
    body: CaseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update case fields. Analysts can update own cases; managers can assign."""
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    if current_user.role == "analyst" and case.assigned_analyst != current_user.email:
        raise HTTPException(status_code=403, detail="Not authorized to update this case")

    if body.status is not None:
        case.status = body.status.upper()
        if case.status == "RESOLVED":
            case.resolved_at = datetime.utcnow()
    if body.resolution is not None:
        case.resolution = body.resolution
    if body.notes is not None:
        case.notes = body.notes
    if body.priority is not None:
        case.priority = body.priority.upper()
    if body.assigned_analyst is not None:
        _require_role(current_user, ["manager", "admin"])
        case.assigned_analyst = body.assigned_analyst

    db.commit()
    db.refresh(case)
    return case


@router.post(
    "/{case_id}/sar",
    response_model=CaseResponse,
    summary="Mark SAR filed on a case",
)
def file_sar(
    case_id: int,
    body: SARFiling,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a Suspicious Activity Report as filed."""
    _require_role(current_user, ["manager", "admin"])

    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    case.sar_required = True
    case.sar_filed_at = datetime.utcnow()
    if body.notes:
        existing = case.notes or ""
        case.notes = f"{existing}\n[SAR] {body.notes}".strip()

    db.commit()
    db.refresh(case)
    return case
