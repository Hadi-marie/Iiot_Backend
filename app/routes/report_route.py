from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.db import get_db
from app.models.report import Report
from app.models.detection_result import DetectionResult
from app.models.security_alert import SecurityAlert
from app.models.device import Device
from app.models.network import Network
from app.coree.security import get_current_admin, get_current_super_admin
from app.utils.subscription import check_subscription

router = APIRouter()


# ── توليد تقرير جديد ─────────────────────────────────────────────────────────
@router.post("/generate", status_code=201)
def generate_report(
    report_type: str = Query("security", description="security | summary"),
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    check_subscription(db, current_admin.company_id)

    if report_type not in ("security", "summary"):
        raise HTTPException(status_code=400, detail="Invalid report type")

    # جلب آخر 30 يوم
    since = datetime.utcnow() - timedelta(days=30)

    # إحصائيات الكشف
    total_detections = db.query(DetectionResult).filter(
        DetectionResult.company_id == current_admin.company_id,
        DetectionResult.detected_at >= since
    ).count()

    attacks_detected = db.query(DetectionResult).filter(
        DetectionResult.company_id == current_admin.company_id,
        DetectionResult.is_attack  == True,
        DetectionResult.detected_at >= since
    ).count()

    blocked = db.query(DetectionResult).filter(
        DetectionResult.company_id  == current_admin.company_id,
        DetectionResult.action_taken == "block",
        DetectionResult.detected_at  >= since
    ).count()

    # إحصائيات الأجهزة
    network = db.query(Network).filter(
        Network.company_id == current_admin.company_id
    ).first()

    total_devices  = 0
    blocked_devices = 0

    if network:
        total_devices = db.query(Device).filter(
            Device.network_id == network.network_id
        ).count()

        blocked_devices = db.query(Device).filter(
            Device.network_id == network.network_id,
            Device.status     == "blocked"
        ).count()

    # إحصائيات الـ alerts
    open_alerts = db.query(SecurityAlert).filter(
        SecurityAlert.company_id == current_admin.company_id,
        SecurityAlert.status     == "open"
    ).count()

    critical_alerts = db.query(SecurityAlert).filter(
        SecurityAlert.company_id == current_admin.company_id,
        SecurityAlert.severity   == "critical",
        SecurityAlert.status     == "open"
    ).count()

    # حفظ التقرير
    new_report = Report(
        company_id   = current_admin.company_id,
        type         = report_type,
        generated_at = datetime.utcnow()
    )
    db.add(new_report)
    db.commit()
    db.refresh(new_report)

    return {
        "report_id":    new_report.report_id,
        "type":         report_type,
        "period":       "Last 30 days",
        "generated_at": new_report.generated_at.isoformat(),
        "detections": {
            "total":    total_detections,
            "attacks":  attacks_detected,
            "blocked":  blocked,
            "safe":     total_detections - attacks_detected
        },
        "devices": {
            "total":   total_devices,
            "blocked": blocked_devices,
            "active":  total_devices - blocked_devices
        },
        "alerts": {
            "open":     open_alerts,
            "critical": critical_alerts
        }
    }


# ── جلب تقارير الشركة ────────────────────────────────────────────────────────
@router.get("/")
def get_reports(
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    check_subscription(db, current_admin.company_id)

    reports = db.query(Report).filter(
        Report.company_id == current_admin.company_id
    ).order_by(Report.generated_at.desc()).all()

    return [
        {
            "report_id":    r.report_id,
            "type":         r.type,
            "generated_at": r.generated_at.isoformat()
        }
        for r in reports
    ]


# ── جلب كل التقارير (Super Admin) ────────────────────────────────────────────
@router.get("/all")
def get_all_reports(
    current_super_admin=Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    reports = db.query(Report).order_by(Report.generated_at.desc()).all()

    return [
        {
            "report_id":    r.report_id,
            "company_id":   r.company_id,
            "type":         r.type,
            "generated_at": r.generated_at.isoformat()
        }
        for r in reports
    ]