from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.routes.analytics_routes import account_risk

router = APIRouter()


@router.get("/account-risk")
def account_risk_alias(limit: int = 50, db: Session = Depends(get_db)):
    return account_risk(limit=limit, db=db)
