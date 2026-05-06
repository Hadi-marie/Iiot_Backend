from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db

from app.models.device import Device
from app.models.network import Network

from app.coree.security import get_current_admin
from app.utils.subscription import check_subscription

router = APIRouter()


# 🎯 إضافة جهاز
@router.post("/")
def create_device(
    ip_address: str,
    device_name: str,
    device_type: str,

    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):

    # 🔥 تحقق الاشتراك
    check_subscription(db, current_admin.company_id)

    # 🔥 جلب شبكة الشركة
    network = db.query(Network).filter(
        Network.company_id == current_admin.company_id
    ).first()

    # ❌ إذا ما عنده شبكة
    if not network:
        raise HTTPException(
            status_code=400,
            detail="Please create a network first"
        )

    # 🔥 إنشاء الجهاز
    new_device = Device(
        network_id=network.network_id,
        ip_address=ip_address,
        device_name=device_name,
        device_type=device_type,
        status="active"
    )

    db.add(new_device)
    db.commit()
    db.refresh(new_device)

    return {
        "message": "Device created successfully"
    }


# 🎯 جلب أجهزة الشركة فقط
@router.get("/")
def get_devices(
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):

    # 🔥 تحقق الاشتراك
    check_subscription(db, current_admin.company_id)

    # 🔥 جلب الشبكة
    network = db.query(Network).filter(
        Network.company_id == current_admin.company_id
    ).first()

    if not network:
        raise HTTPException(
            status_code=400,
            detail="No network found"
        )

    # 🔥 جلب الأجهزة التابعة للشركة فقط
    devices = db.query(Device).filter(
        Device.network_id == network.network_id
    ).all()

    result = []

    for device in devices:
     result.append({
        "device_public_id": device.public_id,
        "ip_address": device.ip_address,
        "device_name": device.device_name,
        "device_type": device.device_type,
        "status": device.status
     })

    return result  

# 🎯 حذف جهاز
@router.delete("/{public_id}")
def delete_device(
    public_id: str,

    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):

    # 🔥 تحقق الاشتراك
    check_subscription(db, current_admin.company_id)

    # 🔥 جلب شبكة الشركة
    network = db.query(Network).filter(
        Network.company_id == current_admin.company_id
    ).first()

    # ❌ لا يوجد شبكة
    if not network:
        raise HTTPException(
            status_code=404,
            detail="Network not found"
        )

    # 🔥 جلب الجهاز
    device = db.query(Device).filter(
        Device.public_id == public_id,
        Device.network_id == network.network_id
    ).first()

    # ❌ الجهاز غير موجود
    if not device:
        raise HTTPException(
            status_code=404,
            detail="Device not found"
        )

    # 🔥 حذف الجهاز
    db.delete(device)

    db.commit()

    return {
        "message": "Device deleted successfully"
    }


# 🎯 تغيير حالة الجهاز
@router.patch("/{public_id}/status")
def update_device_status(
    public_id: str,
    status: str,

    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):

    # 🔥 تحقق الاشتراك
    check_subscription(db, current_admin.company_id)

    # 🔥 الحالات المسموحة
    allowed_statuses = [
        "active",
        "blocked",
        "offline",
        "warning",
        "maintenance"
    ]

    # ❌ حالة غير مسموحة
    if status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail="Invalid status"
        )

    # 🔥 جلب شبكة الشركة
    network = db.query(Network).filter(
        Network.company_id == current_admin.company_id
    ).first()

    if not network:
        raise HTTPException(
            status_code=404,
            detail="Network not found"
        )

    # 🔥 جلب الجهاز
    device = db.query(Device).filter(
        Device.public_id == public_id,
        Device.network_id == network.network_id
    ).first()

    # ❌ الجهاز غير موجود
    if not device:
        raise HTTPException(
            status_code=404,
            detail="Device not found"
        )

    # 🔥 تحديث الحالة
    device.status = status

    db.commit()

    return {
        "message": "Device status updated successfully",
        "device_name": device.device_name,
        "new_status": device.status
    }