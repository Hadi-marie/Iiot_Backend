import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime

from app.db import get_db
from app.models.device import Device
from app.models.network import Network
from app.models.audit_log import AuditLog
from app.coree.security import get_current_admin
from app.utils.subscription import check_subscription

router = APIRouter()


class UnblockRequest(BaseModel):
    device_public_id: str


# ── رفع حظر جهاز مباشرة ──────────────────────────────────────────────────────
@router.post("/", status_code=200)
def unblock_device(
    data: UnblockRequest,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    check_subscription(db, current_admin.company_id)

    network = db.query(Network).filter(
        Network.company_id == current_admin.company_id
    ).first()

    if not network:
        raise HTTPException(status_code=404, detail="Network not found")

    device = db.query(Device).filter(
        Device.public_id  == data.device_public_id,
        Device.network_id == network.network_id
    ).first()

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    if device.status != "blocked":
        raise HTTPException(status_code=400, detail="Device is not blocked")

    # رفع الحظر
    device.status    = "active"
    device.last_seen = datetime.utcnow()

    # تسجيل في audit_log — نحفظ البيانات بشكل منظم
    db.add(AuditLog(
        company_id  = current_admin.company_id,
        event_type  = "DEVICE_UNBLOCKED",
        severity    = "low",
        description = f"device:{device.device_name}|ip:{device.ip_address}|admin:{current_admin.name}|admin_id:{current_admin.admin_id}"
    ))

    db.commit()

    return {
        "message":     "Device unblocked successfully",
        "device_name": device.device_name,
        "status":      device.status
    }


# ── سجل عمليات فك الحظر ──────────────────────────────────────────────────────
@router.get("/history")
def get_unblock_history(
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    check_subscription(db, current_admin.company_id)

    logs = db.query(AuditLog).filter(
        AuditLog.company_id == current_admin.company_id,
        AuditLog.event_type == "DEVICE_UNBLOCKED"
    ).order_by(AuditLog.created_at.desc()).all()

    result = []
    for l in logs:
        # استخرج البيانات من الـ description
        try:
            parts = dict(item.split(":") for item in l.description.split("|"))
            result.append({
                "log_id":      l.log_id,
                "device_name": parts.get("device", "—"),
                "ip_address":  parts.get("ip", "—"),
                "admin_name":  parts.get("admin", "—"),
                "unblocked_at": l.created_at.isoformat()
            })
        except Exception:
            # fallback للسجلات القديمة
            result.append({
                "log_id":      l.log_id,
                "device_name": "—",
                "ip_address":  "—",
                "admin_name":  "—",
                "description": l.description,
                "unblocked_at": l.created_at.isoformat()
            })

    return result