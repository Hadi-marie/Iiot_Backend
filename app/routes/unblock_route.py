from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime

from app.db import get_db
from app.models.unblock_request import UnblockRequest
from app.models.device import Device
from app.models.network import Network
from app.coree.security import get_current_admin, get_current_super_admin
from app.utils.subscription import check_subscription

router = APIRouter()


class UnblockRequestCreate(BaseModel):
    device_public_id: str
    reason: str


# ── طلب رفع حظر (من admin الشركة) ───────────────────────────────────────────
@router.post("/", status_code=201)
def request_unblock(
    data: UnblockRequestCreate,
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

    existing = db.query(UnblockRequest).filter(
        UnblockRequest.device_id == device.device_id,
        UnblockRequest.status    == "pending"
    ).first()

    if existing:
        raise HTTPException(status_code=409, detail="Unblock request already pending")

    new_request = UnblockRequest(
        device_id  = device.device_id,
        company_id = current_admin.company_id,
        admin_id   = current_admin.admin_id,
        reason     = data.reason,
        status     = "pending"
    )
    db.add(new_request)
    db.commit()
    db.refresh(new_request)

    return {
        "message":    "Unblock request submitted",
        "request_id": new_request.request_id,
        "status":     new_request.status
    }


# ── جلب طلبات الشركة ─────────────────────────────────────────────────────────
@router.get("/my")
def get_my_requests(
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    requests = db.query(UnblockRequest).filter(
        UnblockRequest.company_id == current_admin.company_id
    ).order_by(UnblockRequest.requested_at.desc()).all()

    return [
        {
            "request_id":   r.request_id,
            "device_id":    r.device_id,
            "reason":       r.reason,
            "status":       r.status,
            "requested_at": r.requested_at.isoformat(),
            "resolved_at":  r.resolved_at.isoformat() if r.resolved_at else None
        }
        for r in requests
    ]


# ── جلب كل الطلبات (Super Admin) ─────────────────────────────────────────────
@router.get("/all")
def get_all_requests(
    current_super_admin=Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    requests = db.query(UnblockRequest).order_by(
        UnblockRequest.requested_at.desc()
    ).all()

    return [
        {
            "request_id":   r.request_id,
            "company_id":   r.company_id,
            "device_id":    r.device_id,
            "reason":       r.reason,
            "status":       r.status,
            "requested_at": r.requested_at.isoformat(),
            "resolved_at":  r.resolved_at.isoformat() if r.resolved_at else None
        }
        for r in requests
    ]


# ── الموافقة أو الرفض (Super Admin) ──────────────────────────────────────────
@router.patch("/{request_id}/resolve")
def resolve_unblock_request(
    request_id: int,
    action: str,  # "approve" | "reject"
    current_super_admin=Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    if action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="Action must be 'approve' or 'reject'")

    request = db.query(UnblockRequest).filter(
        UnblockRequest.request_id == request_id
    ).first()

    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    if request.status != "pending":
        raise HTTPException(status_code=400, detail="Request already resolved")

    request.status      = "approved" if action == "approve" else "rejected"
    request.resolved_at = datetime.utcnow()

    if action == "approve":
        device = db.query(Device).filter(
            Device.device_id == request.device_id
        ).first()
        if device:
            # ✅ يرجع active ويحدّث last_seen عشان الـ heartbeat ما يحوله offline فوراً
            device.status    = "active"
            device.last_seen = datetime.utcnow()

    db.commit()

    return {
        "message":    f"Request {request.status}",
        "request_id": request_id,
        "status":     request.status
    }