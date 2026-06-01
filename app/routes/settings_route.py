import os
import ipaddress

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.company_admin import CompanyAdmin
from app.models.network import Network
from app.models.device import Device
from app.coree.security import get_current_admin, hash_password, verify_password
from app.utils.subscription import check_subscription

router = APIRouter()


def _is_strong_password(password: str) -> bool:
    if len(password) < 8:
        return False
    if not any(c.isupper() for c in password):
        return False
    if not any(c.islower() for c in password):
        return False
    if not any(c.isdigit() for c in password):
        return False
    if not any(c in "!@#$%^&*()_+-=[]{}|;':\",./<>?" for c in password):
        return False
    return True


# ── Schemas ───────────────────────────────────────────────────────────────────

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class ChangeEmailRequest(BaseModel):
    new_email: EmailStr
    current_password: str


class UpdateNetworkIPRequest(BaseModel):
    ip_range: str


class UpdateDeviceIPRequest(BaseModel):
    ip_address: str


# ── تغيير كلمة المرور ────────────────────────────────────────────────────────
@router.post("/change-password")
def change_password(
    data: ChangePasswordRequest,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    if not verify_password(data.old_password, current_admin.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    if not _is_strong_password(data.new_password):
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters with uppercase, lowercase, number, and special character"
        )

    if verify_password(data.new_password, current_admin.password_hash):
        raise HTTPException(
            status_code=400,
            detail="New password must be different from current password"
        )

    current_admin.password_hash = hash_password(data.new_password)
    db.commit()

    return {"message": "Password changed successfully"}


# ── تغيير الإيميل (خطوة واحدة بالباسورد فقط) ────────────────────────────────
@router.post("/change-email")
def change_email(
    data: ChangeEmailRequest,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    if not verify_password(data.current_password, current_admin.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect password")

    if data.new_email == current_admin.email:
        raise HTTPException(status_code=400, detail="New email must be different")

    existing = db.query(CompanyAdmin).filter(
        CompanyAdmin.email == data.new_email
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already in use")

    current_admin.email = data.new_email
    db.commit()

    return {"message": "Email changed successfully", "new_email": current_admin.email}


# ── تعديل IP الشبكة ───────────────────────────────────────────────────────────
@router.patch("/network/ip")
def update_network_ip(
    data: UpdateNetworkIPRequest,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    check_subscription(db, current_admin.company_id)

    try:
        ipaddress.ip_network(data.ip_range, strict=False)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid IP range format: {data.ip_range}. Example: 192.168.1.0/24"
        )

    network = db.query(Network).filter(
        Network.company_id == current_admin.company_id
    ).first()

    if not network:
        raise HTTPException(status_code=404, detail="Network not found")

    network.ip_range = data.ip_range
    db.commit()

    return {
        "message":  "Network IP range updated",
        "ip_range": network.ip_range
    }


# ── تعديل IP الجهاز ───────────────────────────────────────────────────────────
@router.patch("/device/{public_id}/ip")
def update_device_ip(
    public_id: str,
    data: UpdateDeviceIPRequest,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    check_subscription(db, current_admin.company_id)

    network = db.query(Network).filter(
        Network.company_id == current_admin.company_id
    ).first()

    if not network:
        raise HTTPException(status_code=404, detail="Network not found")

    # تحقق إن IP ضمن نطاق الشبكة
    try:
        net = ipaddress.ip_network(network.ip_range, strict=False)
        if ipaddress.ip_address(data.ip_address) not in net:
            raise HTTPException(
                status_code=400,
                detail=f"IP address {data.ip_address} is outside network range {network.ip_range}"
            )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid IP address format")

    # تحقق من IP مكرر
    existing = db.query(Device).filter(
        Device.network_id == network.network_id,
        Device.ip_address == data.ip_address,
        Device.public_id  != public_id
    ).first()

    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"IP address {data.ip_address} already exists in this network"
        )

    device = db.query(Device).filter(
        Device.public_id  == public_id,
        Device.network_id == network.network_id
    ).first()

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    device.ip_address = data.ip_address
    db.commit()

    return {
        "message":    "Device IP updated",
        "ip_address": device.ip_address
    }