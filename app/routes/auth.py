from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from datetime import datetime
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.db import get_db
from app.models.company import Company
from app.models.company_admin import CompanyAdmin
from app.models.user import User
from app.models.verification_code import VerificationCode
from app.schemas.user import UserLogin, CompanyAdminLogin
from app.coree.security import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    get_current_admin,
)

router  = APIRouter()
limiter = Limiter(key_func=get_remote_address)


# ── Schemas ───────────────────────────────────────────────────────────────────

class CompanyAdminRegister(BaseModel):
    company_name: str
    name:         str
    email:        EmailStr
    password:     str


# ── تسجيل شركة جديدة — خطوة واحدة ───────────────────────────────────────────
@router.post("/register-company", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def register_company(request: Request, data: CompanyAdminRegister, db: Session = Depends(get_db)):

    existing = db.query(CompanyAdmin).filter(
        CompanyAdmin.email == data.email
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    new_company = Company(name=data.company_name, email=data.email)
    db.add(new_company)
    db.commit()
    db.refresh(new_company)

    new_admin = CompanyAdmin(
        name          = data.name,
        email         = data.email,
        password_hash = hash_password(data.password),
        company_id    = new_company.company_id
    )
    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)

    return {
        "message":    "Company and admin created successfully",
        "company_id": new_company.company_id,
        "admin_id":   new_admin.admin_id
    }


# ── Login مستخدم عادي ─────────────────────────────────────────────────────────
@router.post("/login")
@limiter.limit("10/minute")
def login(request: Request, user: UserLogin, db: Session = Depends(get_db)):

    db_user = db.query(User).filter(User.email == user.email).first()

    if not db_user or not verify_password(user.password, db_user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token({"user_id": db_user.user_id})
    return {"access_token": token, "token_type": "bearer"}


# ── بيانات المستخدم الحالي ────────────────────────────────────────────────────
@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "user_id": current_user.user_id,
        "email":   current_user.email,
        "name":    current_user.name
    }


# ── Login admin الشركة ────────────────────────────────────────────────────────
@router.post("/login-company")
@limiter.limit("10/minute")
def login_company(request: Request, data: CompanyAdminLogin, db: Session = Depends(get_db)):

    admin = db.query(CompanyAdmin).filter(
        CompanyAdmin.email == data.email
    ).first()

    if not admin or not verify_password(data.password, admin.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token({
        "admin_id":   admin.admin_id,
        "company_id": admin.company_id
    })
    return {"access_token": token, "token_type": "bearer"}


# ── بيانات admin الحالي ───────────────────────────────────────────────────────
@router.get("/admin/me")
def get_admin_me(current_admin=Depends(get_current_admin)):
    return {
        "admin_id":   current_admin.admin_id,
        "name":       current_admin.name,
        "email":      current_admin.email,
        "company_id": current_admin.company_id
    }


# ── email-change accept ───────────────────────────────────────────────────────
@router.get("/email-change/accept")
def accept_email_change_redirect(token: str, db: Session = Depends(get_db)):
    record = db.query(VerificationCode).filter(
        VerificationCode.code       == token,
        VerificationCode.purpose    == "email_change_old",
        VerificationCode.is_used    == False,
        VerificationCode.expires_at > datetime.utcnow()
    ).first()

    if not record:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    record.is_used = True
    db.commit()
    return {"message": "Email change accepted"}


# ── email-change reject ───────────────────────────────────────────────────────
@router.get("/email-change/reject")
def reject_email_change_redirect(token: str, db: Session = Depends(get_db)):
    record = db.query(VerificationCode).filter(
        VerificationCode.token      == token,
        VerificationCode.purpose    == "email_change_old",
        VerificationCode.is_used    == False,
        VerificationCode.expires_at > datetime.utcnow()
    ).first()

    if not record:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    db.query(VerificationCode).filter(
        VerificationCode.company_id == record.company_id,
        VerificationCode.purpose.in_(["email_change", "email_change_old"]),
        VerificationCode.is_used    == False
    ).delete()
    db.commit()
    return {"message": "Email change rejected"}