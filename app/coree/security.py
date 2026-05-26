import os

from datetime import datetime, timedelta

from dotenv import load_dotenv
from jose import jwt, JWTError
from passlib.context import CryptContext

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.company_admin import CompanyAdmin
from app.models.super_admin import SuperAdmin
from app.models.subscription import Subscription
from app.models.user import User

load_dotenv()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security    = HTTPBearer()

SECRET_KEY                  = os.getenv("SECRET_KEY", "fallback_dev_only")
ALGORITHM                   = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


# ── Password ──────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


# ── JWT ───────────────────────────────────────────────────────────────────────

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    to_encode["exp"] = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )


# ── Current User ──────────────────────────────────────────────────────────────

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    payload = decode_access_token(credentials.credentials)
    user_id = payload.get("user_id")

    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(User).filter(User.user_id == user_id).first()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user


# ── Current Company Admin ─────────────────────────────────────────────────────

def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> CompanyAdmin:
    payload  = decode_access_token(credentials.credentials)
    admin_id = payload.get("admin_id")

    if not admin_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    admin = db.query(CompanyAdmin).filter(
        CompanyAdmin.admin_id == admin_id
    ).first()

    if not admin:
        raise HTTPException(status_code=401, detail="Admin not found")

    return admin


# ── Current Super Admin (المطورين) ────────────────────────────────────────────

def get_current_super_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> SuperAdmin:
    payload        = decode_access_token(credentials.credentials)
    super_admin_id = payload.get("super_admin_id")

    if not super_admin_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required"
        )

    super_admin = db.query(SuperAdmin).filter(
        SuperAdmin.super_admin_id == super_admin_id,
        SuperAdmin.is_active      == True
    ).first()

    if not super_admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Super admin not found or inactive"
        )

    return super_admin


# ── Subscription check ────────────────────────────────────────────────────────

def check_subscription(db: Session, company_id: int) -> Subscription:
    subscription = db.query(Subscription).filter(
        Subscription.company_id == company_id,
        Subscription.status     == "active"
    ).order_by(Subscription.end_date.desc()).first()

    if not subscription:
        raise HTTPException(status_code=403, detail="No active subscription")

    if subscription.end_date < datetime.utcnow():
        subscription.status = "expired"
        db.commit()
        raise HTTPException(status_code=403, detail="Subscription expired")

    return subscription