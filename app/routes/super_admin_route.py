import os

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

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
from app.utils.email_service import send_notification_email

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class SuperAdminCreate(BaseModel):
    name:     str
    email:    EmailStr
    password: str
    secret:   str


class SuperAdminLogin(BaseModel):
    email:    EmailStr
    password: str


class ExtendSubscriptionRequest(BaseModel):
    days: int


class UpdatePlanRequest(BaseModel):
    price:     float | None = None
    duration_days: int | None = None
    threshold: float | None = None


class NotifyCompanyRequest(BaseModel):
    subject: str
    message: str


# ── تسجيل super admin جديد ───────────────────────────────────────────────────
@router.post("/register", status_code=status.HTTP_201_CREATED)
def register_super_admin(data: SuperAdminCreate, db: Session = Depends(get_db)):
    SUPER_ADMIN_SECRET = os.getenv("SUPER_ADMIN_SECRET", "")

    if not SUPER_ADMIN_SECRET or data.secret != SUPER_ADMIN_SECRET:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid secret")

    existing = db.query(SuperAdmin).filter(SuperAdmin.email == data.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

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
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token({
        "super_admin_id": admin.super_admin_id,
        "role":           "super_admin"
    })

    return {"access_token": token, "token_type": "bearer"}


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
    total_companies      = db.query(Company).count()
    active_subscriptions = db.query(Subscription).filter(Subscription.status == "active").count()
    expired_subscriptions = db.query(Subscription).filter(Subscription.status == "expired").count()

    pro_count = db.query(Subscription).join(Plan).filter(
        Subscription.status == "active", Plan.name == "pro"
    ).count()

    premium_count = db.query(Subscription).join(Plan).filter(
        Subscription.status == "active", Plan.name == "premium"
    ).count()

    recent_companies = db.query(Company).order_by(Company.company_id.desc()).limit(10).all()

    return {
        "stats": {
            "total_companies":       total_companies,
            "active_subscriptions":  active_subscriptions,
            "expired_subscriptions": expired_subscriptions,
            "pro_subscribers":       pro_count,
            "premium_subscribers":   premium_count,
        },
        "recent_companies": [
            {"company_id": c.company_id, "name": c.name, "email": c.email}
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
        sub  = db.query(Subscription).filter(
            Subscription.company_id == c.company_id,
            Subscription.status     == "active"
        ).first()

        plan = db.query(Plan).filter(Plan.plan_id == sub.plan_id).first() if sub else None

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


# ── إيقاف / تفعيل اشتراك شركة ───────────────────────────────────────────────
@router.patch("/companies/{company_id}/subscription/toggle")
def toggle_subscription(
    company_id: int,
    current_super_admin=Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    sub = db.query(Subscription).filter(
        Subscription.company_id == company_id
    ).order_by(Subscription.subscription_id.desc()).first()

    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    if sub.status == "active":
        sub.status = "suspended"
        message = "Subscription suspended"
    elif sub.status == "suspended":
        sub.status = "active"
        message = "Subscription reactivated"
    else:
        raise HTTPException(status_code=400, detail=f"Cannot toggle subscription with status: {sub.status}")

    db.commit()

    return {
        "message":    message,
        "company_id": company_id,
        "status":     sub.status
    }


# ── تمديد اشتراك شركة ────────────────────────────────────────────────────────
@router.patch("/companies/{company_id}/subscription/extend")
def extend_subscription(
    company_id: int,
    data: ExtendSubscriptionRequest,
    current_super_admin=Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    if data.days <= 0:
        raise HTTPException(status_code=400, detail="Days must be greater than 0")

    sub = db.query(Subscription).filter(
        Subscription.company_id == company_id,
        Subscription.status.in_(["active", "suspended"])
    ).order_by(Subscription.subscription_id.desc()).first()

    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    sub.end_date = sub.end_date + timedelta(days=data.days)
    db.commit()

    return {
        "message":     f"Subscription extended by {data.days} days",
        "company_id":  company_id,
        "new_end_date": sub.end_date.isoformat()
    }


# ── حذف شركة ─────────────────────────────────────────────────────────────────
@router.delete("/companies/{company_id}")
def delete_company(
    company_id: int,
    current_super_admin=Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    company = db.query(Company).filter(Company.company_id == company_id).first()

    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    db.delete(company)
    db.commit()

    return {
        "message":    "Company deleted successfully",
        "company_id": company_id
    }


# ── إرسال إشعار لشركة ────────────────────────────────────────────────────────
@router.post("/companies/{company_id}/notify")
def notify_company(
    company_id: int,
    data: NotifyCompanyRequest,
    current_super_admin=Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    admin = db.query(CompanyAdmin).filter(
        CompanyAdmin.company_id == company_id
    ).first()

    if not admin:
        raise HTTPException(status_code=404, detail="Company admin not found")

    send_notification_email(admin.email, admin.name, data.subject, data.message)

    return {
        "message": f"Notification sent to {admin.email}"
    }


# ── تعديل خطة موجودة ─────────────────────────────────────────────────────────
@router.patch("/plans/{plan_id}")
def update_plan(
    plan_id: int,
    data: UpdatePlanRequest,
    current_super_admin=Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    plan = db.query(Plan).filter(Plan.plan_id == plan_id).first()

    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    if data.price is not None:
        plan.price = data.price

    if data.duration_days is not None:
        plan.duration_days = data.duration_days

    if data.threshold is not None:
        plan.threshold = data.threshold

    db.commit()

    return {
        "message":       "Plan updated successfully",
        "plan_id":       plan.plan_id,
        "name":          plan.name,
        "price":         float(plan.price),
        "duration_days": plan.duration_days,
        "threshold":     float(plan.threshold)
    }


# ── جلب كل الخطط ─────────────────────────────────────────────────────────────
@router.get("/plans")
def get_plans(
    current_super_admin=Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    plans = db.query(Plan).all()

    return [
        {
            "plan_id":       p.plan_id,
            "name":          p.name,
            "price":         float(p.price),
            "duration_days": p.duration_days,
            "threshold":     float(p.threshold),
            "is_active":     p.is_active
        }
        for p in plans
    ]