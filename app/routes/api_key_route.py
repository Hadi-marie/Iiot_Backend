from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.db import get_db
from app.models.api_key import ApiKey
from app.coree.security import get_current_admin
from app.utils.subscription import check_subscription

router = APIRouter()


# ── إنشاء API Key جديد ────────────────────────────────────────────────────────
@router.post("/", status_code=201)
def create_api_key(
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    check_subscription(db, current_admin.company_id)

    # إلغاء الـ keys القديمة النشطة
    old_keys = db.query(ApiKey).filter(
        ApiKey.company_id == current_admin.company_id,
        ApiKey.status     == "active"
    ).all()

    for key in old_keys:
        key.status = "revoked"

    # إنشاء key جديد صالح لسنة
    new_key = ApiKey(
        company_id = current_admin.company_id,
        status     = "active",
        expires_at = datetime.utcnow() + timedelta(days=365)
    )
    db.add(new_key)
    db.commit()
    db.refresh(new_key)

    return {
        "message":    "API Key created successfully",
        "api_key_id": new_key.api_key_id,
        "key_value":  new_key.key_value,   # يظهر مرة واحدة فقط
        "expires_at": new_key.expires_at.isoformat()
    }


# ── جلب الـ keys النشطة ───────────────────────────────────────────────────────
@router.get("/")
def get_api_keys(
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    check_subscription(db, current_admin.company_id)

    keys = db.query(ApiKey).filter(
        ApiKey.company_id == current_admin.company_id
    ).order_by(ApiKey.created_at.desc()).all()

    return [
        {
            "api_key_id": k.api_key_id,
            "status":     k.status,
            "created_at": k.created_at.isoformat(),
            "expires_at": k.expires_at.isoformat() if k.expires_at else None
        }
        for k in keys
    ]


# ── إلغاء API Key ─────────────────────────────────────────────────────────────
@router.patch("/{api_key_id}/revoke")
def revoke_api_key(
    api_key_id: int,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    check_subscription(db, current_admin.company_id)

    key = db.query(ApiKey).filter(
        ApiKey.api_key_id == api_key_id,
        ApiKey.company_id == current_admin.company_id
    ).first()

    if not key:
        raise HTTPException(status_code=404, detail="API Key not found")

    if key.status == "revoked":
        raise HTTPException(status_code=400, detail="API Key already revoked")

    key.status = "revoked"
    db.commit()

    return {
        "message":    "API Key revoked",
        "api_key_id": api_key_id
    }