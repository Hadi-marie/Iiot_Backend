from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime

from app.db import get_db
from app.coree.security import get_current_admin
from app.utils.subscription import check_subscription
from app.utils.predictor import predict_attack, REQUIRED_FEATURES
from app.models.device import Device
from app.models.network import Network
from app.models.plan import Plan
from app.models.security_alert import SecurityAlert
from app.models.audit_log import AuditLog
from app.utils.broadcaster import broadcast_alert_to_company

router = APIRouter()


class PredictRequest(BaseModel):
    device_public_id: str
    dTtl:      float = 0
    Sport:     float = 0
    SynAck:    float = 0
    TcpRtt:    float = 0
    pLoss:     float = 0
    Load:      float = 0
    Rate:      float = 0
    SrcRate:   float = 0
    SrcLoad:   float = 0
    Mean:      float = 0
    Min:       float = 0
    Sum:       float = 0
    RunTime:   float = 0
    Dur:       float = 0
    Max:       float = 0
    SrcJitAct: float = 0
    sTtl:      float = 0
    SIntPkt:   float = 0
    IdleTime:  float = 0
    Dport:     float = 0
    DIntPkt:   float = 0
    SAppBytes: float = 0
    SrcJitter: float = 0
    SrcBytes:  float = 0
    SrcPkts:   float = 0
    Proto:     float = 0
    DstJitter: float = 0
    TotPkts:   float = 0


@router.post("/predict")
async def predict(
    data: PredictRequest,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    # ── التحقق من الاشتراك وجلب الخطة ───────────────────────────────
    subscription = check_subscription(db, current_admin.company_id)

    plan = db.query(Plan).filter(
        Plan.plan_id == subscription.plan_id
    ).first()

    plan_name = plan.name if plan else "pro"

    # ── التحقق من الجهاز ─────────────────────────────────────────────
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

    # ── تشغيل الموديل حسب الخطة ──────────────────────────────────────
    network_data = data.model_dump(exclude={"device_public_id"})

    try:
        result = predict_attack(network_data, plan_name=plan_name)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # ── إذا هجوم → إجراء فوري ────────────────────────────────────────
    if result["is_attack"]:

        severity = "critical" if result["action"] == "block" else "high"

        if result["action"] == "block":
            device.status = "blocked"

        new_alert = SecurityAlert(
            company_id = current_admin.company_id,
            device_id  = device.device_id,
            alert_type = "ml_detection",
            severity   = severity,
            message    = (
                f"[{plan_name.upper()}] ML detected attack on {device.device_name} "
                f"(probability: {result['probability']})"
            ),
            source = "ml_model",
            status = "open"
        )
        db.add(new_alert)

        db.add(AuditLog(
            company_id  = current_admin.company_id,
            event_type  = "ML_ATTACK_DETECTED",
            severity    = severity,
            description = (
                f"[{plan_name.upper()}] Attack on {device.device_name} "
                f"— action: {result['action']}"
            )
        ))
        db.commit()
        db.refresh(new_alert)

        await broadcast_alert_to_company(current_admin.company_id, {
            "type":        "security_alert",
            "severity":    severity,
            "device_id":   device.public_id,
            "device_name": device.device_name,
            "status":      device.status,
            "plan":        plan_name,
            "message":     new_alert.message,
            "source":      "ml_model",
            "timestamp":   datetime.utcnow().isoformat()
        })

    return {
        "device_name":   device.device_name,
        "plan":          plan_name,
        "is_attack":     result["is_attack"],
        "probability":   result["probability"],
        "threshold":     result["threshold"],
        "action":        result["action"],
        "device_status": device.status
    }


@router.get("/model-info")
def model_info(
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    subscription = check_subscription(db, current_admin.company_id)

    plan = db.query(Plan).filter(
        Plan.plan_id == subscription.plan_id
    ).first()

    plan_name = plan.name if plan else "pro"

    from app.utils.predictor import PLAN_CONFIG
    config = PLAN_CONFIG.get(plan_name, PLAN_CONFIG["pro"])

    return {
        "model":     "LightGBM + Haar Wavelet",
        "plan":      plan_name,
        "threshold": config["threshold"],
        "features":  REQUIRED_FEATURES,
        "metrics": {
            "f1":        0.9963,
            "recall":    1.0,
            "precision": 0.9927
        }
    }