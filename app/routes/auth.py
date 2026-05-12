from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.company import Company
from app.models.company_admin import CompanyAdmin
from app.models.user import User
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

router = APIRouter()


# ── Login مستخدم عادي ─────────────────────────────────────────────────────────
@router.post("/login")
def login(user: UserLogin, db: Session = Depends(get_db)):

    db_user = db.query(User).filter(User.email == user.email).first()

    # ✅ HTTPException بدل dict عادي — الفرونت يعرف إنه خطأ
    if not db_user or not verify_password(user.password, db_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    token = create_access_token({"user_id": db_user.user_id})

    return {
        "access_token": token,
        "token_type": "bearer"
    }


# ── بيانات المستخدم الحالي ────────────────────────────────────────────────────
@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "user_id": current_user.user_id,
        "email":   current_user.email,
        "name":    current_user.name
    }


# ── تسجيل شركة جديدة + admin ─────────────────────────────────────────────────
@router.post("/register-company", status_code=status.HTTP_201_CREATED)
def register_company(data: CompanyAdminRegister, db: Session = Depends(get_db)):

    # تحقق: الإيميل غير مستخدم مسبقاً
    existing = db.query(CompanyAdmin).filter(
        CompanyAdmin.email == data.email
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )

    # إنشاء الشركة
    new_company = Company(
        name=data.company_name,
        email=data.email
    )
    db.add(new_company)
    db.commit()
    db.refresh(new_company)

    # إنشاء admin وربطه بالشركة
    new_admin = CompanyAdmin(
        name=data.name,
        email=data.email,
        password_hash=hash_password(data.password),
        company_id=new_company.company_id
    )
    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)

    return {
        "message":    "Company and admin created successfully",
        "company_id": new_company.company_id,
        "admin_id":   new_admin.admin_id
    }


# ── Login admin الشركة ────────────────────────────────────────────────────────
@router.post("/login-company")
def login_company(data: CompanyAdminLogin, db: Session = Depends(get_db)):

    admin = db.query(CompanyAdmin).filter(
        CompanyAdmin.email == data.email
    ).first()

    # ✅ HTTPException بدل dict عادي
    if not admin or not verify_password(data.password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    token = create_access_token({
        "admin_id":   admin.admin_id,
        "company_id": admin.company_id
    })

    return {
        "access_token": token,
        "token_type":   "bearer"
    }


# ── بيانات admin الحالي ───────────────────────────────────────────────────────
@router.get("/admin/me")
def get_admin_me(current_admin=Depends(get_current_admin)):
    return {
        "admin_id":   current_admin.admin_id,
        "name":       current_admin.name,
        "email":      current_admin.email,
        "company_id": current_admin.company_id
    }