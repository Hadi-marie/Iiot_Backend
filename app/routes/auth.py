import random
import string

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import EmailStr
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.db import get_db
from app.models.company import Company
from app.models.company_admin import CompanyAdmin
from app.models.user import User
from app.models.verification_code import VerificationCode
from app.schemas.user import (
    UserLogin,
    UserResponse,
    CompanyAdminRegister,
    CompanyAdminLogin,
)
from app.coree.security import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    get_current_admin,
)
from app.utils.email_service import send_verification_email

router = APIRouter()


def _generate_code(length=6) -> str:
    return ''.join(random.choices(string.digits, k=length))


# ── تسجيل شركة جديدة — الخطوة 1: إرسال كود التحقق ───────────────────────────
from pydantic import BaseModel

class CompanyAdminRegister(BaseModel):
    company_name: str
    name: str
    email: EmailStr
    password: str


class VerifyAndRegisterRequest(BaseModel):
    email: EmailStr
    code: str


@router.post("/register-company/send-code", status_code=200)
def send_registration_code(data: CompanyAdminRegister, db: Session = Depends(get_db)):

    # تحقق إن الإيميل غير مستخدم
    existing = db.query(CompanyAdmin).filter(
        CompanyAdmin.email == data.email
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    # إلغاء الكودات القديمة
    db.query(VerificationCode).filter(
        VerificationCode.email   == data.email,
        VerificationCode.purpose == "register",
        VerificationCode.is_used == False
    ).delete()
    db.commit()

    code    = _generate_code()
    expires = datetime.utcnow() + timedelta(minutes=10)

    # حفظ البيانات مؤقتاً في extra_data
    import json
    extra = json.dumps({
        "company_name": data.company_name,
        "name":         data.name,
        "password":     hash_password(data.password)
    })

    db.add(VerificationCode(
        email      = data.email,
        code       = code,
        purpose    = "register",
        extra_data = extra,
        expires_at = expires
    ))
    db.commit()

    send_verification_email(data.email, code, data.name)

    return {"message": "Verification code sent to your email"}


# ── تسجيل شركة جديدة — الخطوة 2: تأكيد الكود وإنشاء الحساب ─────────────────
@router.post("/register-company", status_code=status.HTTP_201_CREATED)
def register_company(data: VerifyAndRegisterRequest, db: Session = Depends(get_db)):

    record = db.query(VerificationCode).filter(
        VerificationCode.email      == data.email,
        VerificationCode.code       == data.code,
        VerificationCode.purpose    == "register",
        VerificationCode.is_used    == False,
        VerificationCode.expires_at > datetime.utcnow()
    ).first()

    if not record:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")

    import json
    extra = json.loads(record.extra_data)

    # إنشاء الشركة
    new_company = Company(
        name  = extra["company_name"],
        email = data.email
    )
    db.add(new_company)
    db.commit()
    db.refresh(new_company)

    # إنشاء الـ admin
    new_admin = CompanyAdmin(
        name          = extra["name"],
        email         = data.email,
        password_hash = extra["password"],
        company_id    = new_company.company_id
    )
    db.add(new_admin)

    record.is_used = True
    db.commit()
    db.refresh(new_admin)

    return {
        "message":    "Company and admin created successfully",
        "company_id": new_company.company_id,
        "admin_id":   new_admin.admin_id
    }


# ── Login مستخدم عادي ─────────────────────────────────────────────────────────
@router.post("/login")
def login(user: UserLogin, db: Session = Depends(get_db)):

    db_user = db.query(User).filter(User.email == user.email).first()

    if not db_user or not verify_password(user.password, db_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

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
def login_company(data: CompanyAdminLogin, db: Session = Depends(get_db)):

    admin = db.query(CompanyAdmin).filter(
        CompanyAdmin.email == data.email
    ).first()

    if not admin or not verify_password(data.password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

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


# ── email-change accept/reject redirects ──────────────────────────────────────
@router.get("/email-change/accept")
def accept_email_change_redirect(token: str, db: Session = Depends(get_db)):
    from app.models.verification_code import VerificationCode as VC
    record = db.query(VC).filter(
        VC.code       == token,
        VC.purpose    == "email_change_old",
        VC.is_used    == False,
        VC.expires_at > datetime.utcnow()
    ).first()

    if not record:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    record.is_used = True
    db.commit()

    return {"message": "Email change accepted"}


@router.get("/email-change/reject")
def reject_email_change_redirect(token: str, db: Session = Depends(get_db)):
    from app.models.verification_code import VerificationCode as VC
    record = db.query(VC).filter(
        VC.token      == token,
        VC.purpose    == "email_change_old",
        VC.is_used    == False,
        VC.expires_at > datetime.utcnow()
    ).first()

    if not record:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    db.query(VC).filter(
        VC.company_id == record.company_id,
        VC.purpose.in_(["email_change", "email_change_old"]),
        VC.is_used    == False
    ).delete()
    db.commit()

    return {"message": "Email change rejected"}