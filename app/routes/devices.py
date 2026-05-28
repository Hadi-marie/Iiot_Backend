from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.device import Device
from app.models.network import Network
from app.models.security_alert import SecurityAlert
from app.coree.security import get_current_admin
from app.utils.subscription import check_subscription

router = APIRouter()

ALLOWED_STATUSES = {"active", "blocked", "offline", "warning", "maintenance"}

SEVERITY_MAP = {
    "blocked":     "critical",
    "offline":     "high",
    "warning":     "medium",
    "maintenance": "low",
}


class DeviceCreate(BaseModel):
    device_name: str
    device_type: str
    ip_address:  str


class DeviceStatusUpdate(BaseModel):
    status: str


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_device(
    data: DeviceCreate,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    check_subscription(db, current_admin.company_id)

    network = db.query(Network).filter(
        Network.company_id == current_admin.company_id
    ).first()

    if not network:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please create a network first"
        )

    # ✅ تحقق من IP مكرر في نفس الشبكة
    existing_ip = db.query(Device).filter(
        Device.network_id == network.network_id,
        Device.ip_address == data.ip_address
    ).first()

    if existing_ip:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"IP address {data.ip_address} already exists in this network"
        )

    new_device = Device(
        network_id=network.network_id,
        ip_address=data.ip_address,
        device_name=data.device_name,
        device_type=data.device_type,
        status="active"
    )
    db.add(new_device)
    db.commit()
    db.refresh(new_device)

    return {
        "message": "Device created successfully",
        "device": {
            "public_id":    new_device.public_id,
            "device_name":  new_device.device_name,
            "device_type":  new_device.device_type,
            "ip_address":   new_device.ip_address,
            "status":       new_device.status,
            "device_token": new_device.device_token,
            "secret_key":   new_device.secret_key
        }
    }


@router.get("/")
def get_devices(
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    check_subscription(db, current_admin.company_id)

    network = db.query(Network).filter(
        Network.company_id == current_admin.company_id
    ).first()

    if not network:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No network found"
        )

    devices = db.query(Device).filter(
        Device.network_id == network.network_id
    ).all()

    return [
        {
            "public_id":   d.public_id,
            "device_name": d.device_name,
            "device_type": d.device_type,
            "ip_address":  d.ip_address,
            "status":      d.status,
            "last_seen":   d.last_seen.isoformat() if d.last_seen else None
        }
        for d in devices
    ]


@router.get("/{public_id}")
def get_device(
    public_id: str,
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
        Device.public_id   == public_id,
        Device.network_id  == network.network_id
    ).first()

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    return {
        "public_id":   device.public_id,
        "device_name": device.device_name,
        "device_type": device.device_type,
        "ip_address":  device.ip_address,
        "status":      device.status,
        "last_seen":   device.last_seen.isoformat() if device.last_seen else None
    }


@router.patch("/{public_id}/status")
def update_device_status(
    public_id: str,
    data: DeviceStatusUpdate,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    check_subscription(db, current_admin.company_id)

    if data.status not in ALLOWED_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Allowed: {ALLOWED_STATUSES}"
        )

    network = db.query(Network).filter(
        Network.company_id == current_admin.company_id
    ).first()

    if not network:
        raise HTTPException(status_code=404, detail="Network not found")

    device = db.query(Device).filter(
        Device.public_id  == public_id,
        Device.network_id == network.network_id
    ).first()

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    device.status = data.status
    db.commit()

    if data.status in SEVERITY_MAP:
        db.add(SecurityAlert(
            company_id = current_admin.company_id,
            device_id  = device.device_id,
            alert_type = "manual_status_change",
            severity   = SEVERITY_MAP[data.status],
            message    = f"{device.device_name} manually set to {data.status}",
            source     = "admin_panel",
            status     = "open"
        ))
        db.commit()

    return {
        "message":     "Device status updated",
        "device_name": device.device_name,
        "new_status":  device.status
    }


@router.delete("/{public_id}")
def delete_device(
    public_id: str,
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
        Device.public_id  == public_id,
        Device.network_id == network.network_id
    ).first()

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    db.delete(device)
    db.commit()

    return {"message": "Device deleted successfully"}