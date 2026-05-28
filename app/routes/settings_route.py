import os
import random
import string
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.db import get_db
from app.models.company_admin import CompanyAdmin
from app.models.network import Network
from app.models.device import Device
from app.models.verification_code import VerificationCode
from app.coree.security import get_current_admin, hash_password, verify_password
from app.utils.subscription import check_subscription
from app.utils.email_service import (
    send_email_change_request,
    send_email_change_notification
)

router = APIRouter()

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")


def _generate_code(length=6) -> str:
    return ''.join(random.choices(string.digits, k=length))


def _is_strong_password(password: str) -> bool:
    """تحقق من صعوبة كلمة المرور"""
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


class RequestEmailChangeRequest(BaseModel):
    new_email: EmailStr
    current_password: str


class ConfirmEmailChangeRequest(BaseModel):
    code: str


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
    # تحقق من كلمة المرور القديمة
    if not verify_password(data.old_password, current_admin.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    # تحقق من قوة كلمة المرور الجديدة
    if not _is_strong_password(data.new_password):
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters with uppercase, lowercase, number, and special character"
        )

    # تحقق إن الجديدة مختلفة عن القديمة
    if verify_password(data.new_password, current_admin.password_hash):
        raise HTTPException(
            status_code=400,
            detail="New password must be different from current password"
        )

    current_admin.password_hash = hash_password(data.new_password)
    db.commit()

    return {"message": "Password changed successfully"}


# ── طلب تغيير الإيميل ────────────────────────────────────────────────────────
@router.post("/request-email-change")
def request_email_change(
    data: RequestEmailChangeRequest,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    # تحقق من كلمة المرور
    if not verify_password(data.current_password, current_admin.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect password")

    # تحقق إن الإيميل الجديد مختلف
    if data.new_email == current_admin.email:
        raise HTTPException(status_code=400, detail="New email must be different")

    # تحقق إن الإيميل الجديد غير مستخدم
    existing = db.query(CompanyAdmin).filter(
        CompanyAdmin.email == data.new_email
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already in use")

    # إلغاء الطلبات القديمة
    db.query(VerificationCode).filter(
        VerificationCode.company_id == current_admin.admin_id,
        VerificationCode.purpose.in_(["email_change", "email_change_old"]),
        VerificationCode.is_used == False
    ).delete()
    db.commit()

    expires = datetime.utcnow() + timedelta(minutes=10)

    # كود للإيميل الجديد
    new_code = _generate_code()
    db.add(VerificationCode(
        company_id = current_admin.admin_id,
        email      = data.new_email,
        code       = new_code,
        purpose    = "email_change",
        extra_data = data.new_email,
        expires_at = expires
    ))

    # توكن للإيميل القديم (accept/reject)
    accept_token = secrets.token_urlsafe(32)
    reject_token = secrets.token_urlsafe(32)

    db.add(VerificationCode(
        company_id = current_admin.admin_id,
        email      = current_admin.email,
        code       = accept_token,
        purpose    = "email_change_old",
        token      = reject_token,
        extra_data = data.new_email,
        expires_at = datetime.utcnow() + timedelta(hours=24)
    ))
    db.commit()

    # إرسال الإيميلات
    send_email_change_request(data.new_email, new_code, current_admin.name)
    send_email_change_notification(
        current_admin.email,
        data.new_email,
        current_admin.name,
        accept_token,
        reject_token,
        FRONTEND_URL
    )

    return {"message": "Verification code sent to new email. Notification sent to current email."}


# ── تأكيد تغيير الإيميل بالكود ───────────────────────────────────────────────
@router.post("/confirm-email-change")
def confirm_email_change(
    data: ConfirmEmailChangeRequest,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    record = db.query(VerificationCode).filter(
        VerificationCode.company_id == current_admin.admin_id,
        VerificationCode.code       == data.code,
        VerificationCode.purpose    == "email_change",
        VerificationCode.is_used    == False,
        VerificationCode.expires_at > datetime.utcnow()
    ).first()

    if not record:
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    # تغيير الإيميل
    current_admin.email = record.extra_data
    record.is_used = True
    db.commit()

    return {"message": "Email changed successfully", "new_email": current_admin.email}


# ── قبول تغيير الإيميل من الإيميل القديم ────────────────────────────────────
@router.get("/email-change/accept")
def accept_email_change(
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    record = db.query(VerificationCode).filter(
        VerificationCode.code       == token,
        VerificationCode.purpose    == "email_change_old",
        VerificationCode.is_used    == False,
        VerificationCode.expires_at > datetime.utcnow()
    ).first()

    if not record:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    record.is_used = True
    db.commit()

    return {"message": "Email change accepted"}


# ── رفض تغيير الإيميل من الإيميل القديم ─────────────────────────────────────
@router.get("/email-change/reject")
def reject_email_change(
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    record = db.query(VerificationCode).filter(
        VerificationCode.token      == token,
        VerificationCode.purpose    == "email_change_old",
        VerificationCode.is_used    == False,
        VerificationCode.expires_at > datetime.utcnow()
    ).first()

    if not record:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    # إلغاء طلب التغيير
    db.query(VerificationCode).filter(
        VerificationCode.company_id == record.company_id,
        VerificationCode.purpose.in_(["email_change", "email_change_old"]),
        VerificationCode.is_used    == False
    ).delete()
    db.commit()

    return {"message": "Email change rejected and cancelled"}


# ── تعديل IP الشبكة ───────────────────────────────────────────────────────────
@router.patch("/network/ip")
def update_network_ip(
    data: UpdateNetworkIPRequest,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    check_subscription(db, current_admin.company_id)

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