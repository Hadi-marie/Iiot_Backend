from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime

from app.db import get_db
from app.models.security_alert import SecurityAlert
from app.models.device import Device
from app.models.network import Network
from app.coree.security import get_current_admin
from app.utils.subscription import check_subscription

router = APIRouter()


# ── جلب كل alerts الشركة ──────────────────────────────────────────────────────
@router.get("/")
def get_alerts(
    status:   str | None = Query(None, description="open / resolved"),
    severity: str | None = Query(None, description="low / medium / high / critical"),
    limit:    int        = Query(50, ge=1, le=200),
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    check_subscription(db, current_admin.company_id)

    query = db.query(SecurityAlert).filter(
        SecurityAlert.company_id == current_admin.company_id
    )

    if status:
        query = query.filter(SecurityAlert.status == status)

    if severity:
        query = query.filter(SecurityAlert.severity == severity)

    alerts = query.order_by(SecurityAlert.created_at.desc()).limit(limit).all()

    return [
        {
            "alert_id":   a.alert_id,
            "device_id":  a.device_id,
            "alert_type": a.alert_type,
            "severity":   a.severity,
            "message":    a.message,
            "source":     a.source,
            "status":     a.status,
            "created_at": a.created_at.isoformat(),
            "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None
        }
        for a in alerts
    ]


# ── إحصائيات الـ alerts ────────────────────────────────────────────────────────
@router.get("/stats")
def get_alerts_stats(
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    check_subscription(db, current_admin.company_id)

    base = db.query(SecurityAlert).filter(
        SecurityAlert.company_id == current_admin.company_id
    )

    return {
        "total":    base.count(),
        "open":     base.filter(SecurityAlert.status == "open").count(),
        "resolved": base.filter(SecurityAlert.status == "resolved").count(),
        "critical": base.filter(SecurityAlert.severity == "critical", SecurityAlert.status == "open").count(),
        "high":     base.filter(SecurityAlert.severity == "high",     SecurityAlert.status == "open").count(),
        "medium":   base.filter(SecurityAlert.severity == "medium",   SecurityAlert.status == "open").count(),
    }


# ── إغلاق alert ───────────────────────────────────────────────────────────────
@router.patch("/{alert_id}/resolve")
def resolve_alert(
    alert_id: int,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    check_subscription(db, current_admin.company_id)

    alert = db.query(SecurityAlert).filter(
        SecurityAlert.alert_id   == alert_id,
        SecurityAlert.company_id == current_admin.company_id
    ).first()

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    if alert.status == "resolved":
        raise HTTPException(status_code=400, detail="Alert already resolved")

    alert.status      = "resolved"
    alert.resolved_at = datetime.utcnow()
    db.commit()

    return {
        "message":     "Alert resolved",
        "alert_id":    alert.alert_id,
        "resolved_at": alert.resolved_at.isoformat()
    }