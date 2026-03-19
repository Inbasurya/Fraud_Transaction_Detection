from sqlalchemy.orm import Session
from app.models import user_model
from app.schemas import user_schema
from app.utils import security


def register_user(db: Session, user: user_schema.UserCreate):
    # check if existing
    existing = db.query(user_model.User).filter(user_model.User.email == user.email).first()
    if existing:
        return None
    hashed = security.hash_password(user.password)
    db_user = user_model.User(name=user.name, email=user.email, password_hash=hashed)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def authenticate_user(db: Session, email: str, password: str):
    user = db.query(user_model.User).filter(user_model.User.email == email).first()
    if not user:
        return None
    if not security.verify_password(password, user.password_hash):
        return None
    return user
