from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db import get_db

from app.models.device import Device
from app.models.network import Network
from app.models.company import Company

from app.coree.security import get_current_admin

from app.utils.subscription import check_subscription

router = APIRouter()


@router.get("/summary")
def dashboard_summary(
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):

    # 🔥 تحقق الاشتراك
    check_subscription(db, current_admin.company_id)

    # 🔥 جلب الشركة
    company = db.query(Company).filter(
        Company.company_id == current_admin.company_id
    ).first()

    # 🔥 جلب الشبكة
    network = db.query(Network).filter(
        Network.company_id == current_admin.company_id
    ).first()

    if not network:
        raise HTTPException(
            status_code=404,
            detail="Network not found"
        )

    # 🔥 إجمالي الأجهزة
    total_devices = db.query(Device).filter(
        Device.network_id == network.network_id
    ).count()

    # 🔥 active
    active_devices = db.query(Device).filter(
        Device.network_id == network.network_id,
        Device.status == "active"
    ).count()

    # 🔥 blocked
    blocked_devices = db.query(Device).filter(
        Device.network_id == network.network_id,
        Device.status == "blocked"
    ).count()

    # 🔥 offline
    offline_devices = db.query(Device).filter(
        Device.network_id == network.network_id,
        Device.status == "offline"
    ).count()

    # 🔥 warning
    warning_devices = db.query(Device).filter(
        Device.network_id == network.network_id,
        Device.status == "warning"
    ).count()

    # 🔥 network health logic
    network_status = "healthy"

    if blocked_devices > 0:
        network_status = "critical"

    elif warning_devices > 0:
        network_status = "warning"

    elif offline_devices > 0:
        network_status = "unstable"

    return {
        "company": company.name,

        "network_public_id": network.public_id,

        "summary": {
            "total_devices": total_devices,
            "active_devices": active_devices,
            "blocked_devices": blocked_devices,
            "offline_devices": offline_devices,
            "warning_devices": warning_devices,
        },

        "network_status": network_status
    }

@router.get("/topology")
def dashboard_topology(
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):

    # 🔥 تحقق الاشتراك
    check_subscription(db, current_admin.company_id)

    # 🔥 جلب الشبكة
    network = db.query(Network).filter(
        Network.company_id == current_admin.company_id
    ).first()

    # ❌ لا يوجد شبكة
    if not network:
        raise HTTPException(
            status_code=404,
            detail="Network not found"
        )

    # 🔥 جلب الأجهزة
    devices = db.query(Device).filter(
        Device.network_id == network.network_id
    ).all()

    # 🌐 إنشاء nodes
    nodes = []

    # 🔗 إنشاء edges
    edges = []

    # 🔥 الشبكة الرئيسية كـ node
    network_node_id = network.public_id

    nodes.append({
        "id": network_node_id,

        "type": "network",

        "label": "Industrial Network",

        "status": "healthy"
    })

    # 🔥 بناء Nodes + Edges
    for device in devices:

        # 🟢 device node
        nodes.append({

            "id": device.public_id,

            "type": "device",

            "label": device.device_name,

            "device_type": device.device_type,

            "status": device.status,

            "ip_address": device.ip_address
        })

        # 🔗 ربط الجهاز بالشبكة
        edges.append({

            "source": network_node_id,

            "target": device.public_id
        })

    return {

        "network": {
            "public_id": network.public_id,
            "ip_range": network.ip_range
        },

        "nodes": nodes,

        "edges": edges
    }