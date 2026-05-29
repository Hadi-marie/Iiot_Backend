import ipaddress

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.network import Network
from app.models.device import Device
from app.models.security_alert import SecurityAlert
from app.models.detection_result import DetectionResult
from app.models.network_flow import NetworkFlow
from app.models.action import Action
from app.models.unblock_request import UnblockRequest
from app.coree.security import get_current_admin
from app.utils.subscription import check_subscription

router = APIRouter()


class NetworkCreate(BaseModel):
    network_name: str
    ip_range:     str


# ── إنشاء شبكة ────────────────────────────────────────────────────────────────
@router.post("/")
def create_network(
    data: NetworkCreate,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    check_subscription(db, current_admin.company_id)

    # ممنوع أكثر من شبكة واحدة
    existing = db.query(Network).filter(
        Network.company_id == current_admin.company_id
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Network already exists")

    # تحقق من صحة الـ IP range
    try:
        ipaddress.ip_network(data.ip_range, strict=False)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid IP range format: {data.ip_range}. Example: 192.168.1.0/24"
        )

    new_network = Network(
        company_id   = current_admin.company_id,
        network_name = data.network_name,
        ip_range     = data.ip_range
    )
    db.add(new_network)
    db.commit()
    db.refresh(new_network)

    return {
        "message":           "Network created successfully",
        "network_public_id": new_network.public_id,
        "network_name":      new_network.network_name,
        "ip_range":          new_network.ip_range
    }


# ── جلب شبكة الشركة ───────────────────────────────────────────────────────────
@router.get("/")
def get_network(
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    check_subscription(db, current_admin.company_id)

    network = db.query(Network).filter(
        Network.company_id == current_admin.company_id
    ).first()

    if not network:
        raise HTTPException(status_code=404, detail="No network found")

    return {
        "network_id":   network.network_id,
        "public_id":    network.public_id,
        "network_name": network.network_name,
        "ip_range":     network.ip_range
    }


# ── حذف الشبكة (مع حذف كل الأجهزة والبيانات المرتبطة) ───────────────────────
@router.delete("/")
def delete_network(
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    check_subscription(db, current_admin.company_id)

    network = db.query(Network).filter(
        Network.company_id == current_admin.company_id
    ).first()

    if not network:
        raise HTTPException(status_code=404, detail="No network found")

    # جلب كل الأجهزة
    devices = db.query(Device).filter(
        Device.network_id == network.network_id
    ).all()

    for device in devices:
        device_id = device.device_id

        # حذف البيانات المرتبطة بكل جهاز
        db.query(SecurityAlert).filter(SecurityAlert.device_id == device_id).delete()
        db.query(UnblockRequest).filter(UnblockRequest.device_id == device_id).delete()

        detections = db.query(DetectionResult).filter(
            DetectionResult.device_id == device_id
        ).all()
        for det in detections:
            db.query(Action).filter(Action.detection_id == det.detection_id).delete()
        db.query(DetectionResult).filter(DetectionResult.device_id == device_id).delete()
        db.query(NetworkFlow).filter(NetworkFlow.device_id == device_id).delete()
        db.query(Action).filter(Action.device_id == device_id).delete()

        db.delete(device)

    # حذف الشبكة
    db.delete(network)
    db.commit()

    return {"message": "Network and all devices deleted successfully"}