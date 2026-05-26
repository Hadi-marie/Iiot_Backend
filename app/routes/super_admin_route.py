from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from datetime import datetime

from app.db import get_db
from app.models.super_admin import SuperAdmin
from app.models.company import Company
from app.models.company_admin import CompanyAdmin
from app.models.subscription import Subscription
from app.models.plan import Plan
from app.coree.security import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_super_admin
)

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class SuperAdminCreate(BaseModel):
    name:     str
    email:    EmailStr
    password: str
    secret:   str  # كلمة سر خاصة للتسجيل — تحمي endpoint الإنشاء


class SuperAdminLogin(BaseModel):
    email:    EmailStr
    password: str


# ── تسجيل super admin جديد ───────────────────────────────────────────────────
# محمي بـ secret key من .env
@router.post("/register", status_code=status.HTTP_201_CREATED)
def register_super_admin(data: SuperAdminCreate, db: Session = Depends(get_db)):
    import os
    SUPER_ADMIN_SECRET = os.getenv("SUPER_ADMIN_SECRET", "")

    if not SUPER_ADMIN_SECRET or data.secret != SUPER_ADMIN_SECRET:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid secret"
        )

    existing = db.query(SuperAdmin).filter(
        SuperAdmin.email == data.email
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )

    new_super_admin = SuperAdmin(
        name          = data.name,
        email         = data.email,
        password_hash = hash_password(data.password),
        is_active     = True
    )
    db.add(new_super_admin)
    db.commit()
    db.refresh(new_super_admin)

    return {
        "message":        "Super admin created successfully",
        "super_admin_id": new_super_admin.super_admin_id
    }


# ── تسجيل الدخول ─────────────────────────────────────────────────────────────
@router.post("/login")
def login_super_admin(data: SuperAdminLogin, db: Session = Depends(get_db)):

    admin = db.query(SuperAdmin).filter(
        SuperAdmin.email     == data.email,
        SuperAdmin.is_active == True
    ).first()

    if not admin or not verify_password(data.password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    token = create_access_token({
        "super_admin_id": admin.super_admin_id,
        "role":           "super_admin"
    })

    return {
        "access_token": token,
        "token_type":   "bearer"
    }


# ── بيانات super admin الحالي ─────────────────────────────────────────────────
@router.get("/me")
def get_me(current_super_admin=Depends(get_current_super_admin)):
    return {
        "super_admin_id": current_super_admin.super_admin_id,
        "name":           current_super_admin.name,
        "email":          current_super_admin.email
    }


# ── Dashboard المطورين ────────────────────────────────────────────────────────
@router.get("/dashboard")
def super_admin_dashboard(
    current_super_admin=Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    # إجمالي الشركات
    total_companies = db.query(Company).count()

    # الاشتراكات النشطة
    active_subscriptions = db.query(Subscription).filter(
        Subscription.status == "active"
    ).count()

    # الاشتراكات المنتهية
    expired_subscriptions = db.query(Subscription).filter(
        Subscription.status == "expired"
    ).count()

    # توزيع الخطط
    pro_count = db.query(Subscription).join(Plan).filter(
        Subscription.status == "active",
        Plan.name            == "pro"
    ).count()

    premium_count = db.query(Subscription).join(Plan).filter(
        Subscription.status == "active",
        Plan.name            == "premium"
    ).count()

    # آخر 10 شركات مسجلة
    recent_companies = db.query(Company).order_by(
        Company.company_id.desc()
    ).limit(10).all()

    return {
        "stats": {
            "total_companies":      total_companies,
            "active_subscriptions": active_subscriptions,
            "expired_subscriptions": expired_subscriptions,
            "pro_subscribers":      pro_count,
            "premium_subscribers":  premium_count,
        },
        "recent_companies": [
            {
                "company_id": c.company_id,
                "name":       c.name,
                "email":      c.email
            }
            for c in recent_companies
        ]
    }


# ── جلب كل الشركات ───────────────────────────────────────────────────────────
@router.get("/companies")
def get_all_companies(
    current_super_admin=Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    companies = db.query(Company).all()

    result = []
    for c in companies:
        sub = db.query(Subscription).filter(
            Subscription.company_id == c.company_id,
            Subscription.status     == "active"
        ).first()

        plan = db.query(Plan).filter(
            Plan.plan_id == sub.plan_id
        ).first() if sub else None

        result.append({
            "company_id":   c.company_id,
            "name":         c.name,
            "email":        c.email,
            "subscription": {
                "status":   sub.status if sub else "none",
                "plan":     plan.name if plan else "none",
                "end_date": sub.end_date.isoformat() if sub else None
            }
        })

    return result