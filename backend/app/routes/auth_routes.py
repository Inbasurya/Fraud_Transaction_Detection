from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta

from app.schemas import user_schema
from app.database import get_db
from app.services import auth_service
from app.utils import auth_handler

router = APIRouter()

@router.post("/register", response_model=user_schema.UserResponse)
def register(user: user_schema.UserCreate, db: Session = Depends(get_db)):
    created = auth_service.register_user(db, user)
    if created is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already exists")
    return created

@router.post("/login")
def login(form: user_schema.UserLogin, db: Session = Depends(get_db)):
    user = auth_service.authenticate_user(db, form.email, form.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    access_token = auth_handler.create_access_token(
        data={"sub": user.email}
    )
    return {"access_token": access_token, "token_type": "bearer"}
