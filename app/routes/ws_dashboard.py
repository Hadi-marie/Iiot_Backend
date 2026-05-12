from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from datetime import datetime

from app.db import SessionLocal
from app.coree.security import decode_access_token
from app.models.security_alert import SecurityAlert

# ✅ من broadcaster بدل circular import
from app.utils.broadcaster import dashboard_clients

router = APIRouter()


@router.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):

    await websocket.accept()

    db: Session = SessionLocal()
    company_id: int | None = None

    try:

        # ── الخطوة 1: استقبال التوكن في أول رسالة ─────────────────────
        auth_data  = await websocket.receive_json()
        token      = auth_data.get("token")

        if not token:
            await websocket.send_json({
                "type":    "auth_error",
                "message": "Token required"
            })
            await websocket.close()
            return

        # ── الخطوة 2: التحقق من التوكن ───────────────────────────────
        try:
            payload    = decode_access_token(token)
            company_id = payload.get("company_id")
            admin_id   = payload.get("admin_id")
        except Exception:
            await websocket.send_json({
                "type":    "auth_error",
                "message": "Invalid or expired token"
            })
            await websocket.close()
            return

        if not company_id or not admin_id:
            await websocket.send_json({
                "type":    "auth_error",
                "message": "Invalid token payload"
            })
            await websocket.close()
            return

        # ── الخطوة 3: تسجيل الاتصال في غرفة الشركة ──────────────────
        if company_id not in dashboard_clients:
            dashboard_clients[company_id] = []

        dashboard_clients[company_id].append(websocket)

        # ── الخطوة 4: إرسال تأكيد + آخر 10 alerts مفتوحة ────────────
        recent_alerts = db.query(SecurityAlert).filter(
            SecurityAlert.company_id == company_id,
            SecurityAlert.status     == "open"
        ).order_by(SecurityAlert.created_at.desc()).limit(10).all()

        await websocket.send_json({
            "type":    "connected",
            "message": "Dashboard connected successfully",
            "recent_alerts": [
                {
                    "alert_id":   a.alert_id,
                    "alert_type": a.alert_type,
                    "severity":   a.severity,
                    "message":    a.message,
                    "source":     a.source,
                    "created_at": a.created_at.isoformat()
                }
                for a in recent_alerts
            ]
        })

        print(f"✅ Dashboard connected — company_id: {company_id}")

        # ── الخطوة 5: انتظار رسائل الفرونت ───────────────────────────
        while True:

            data     = await websocket.receive_json()
            msg_type = data.get("type")

            # ping للحفاظ على الاتصال
            if msg_type == "ping":
                await websocket.send_json({
                    "type":      "pong",
                    "timestamp": datetime.utcnow().isoformat()
                })

            # إغلاق alert من الفرونت
            elif msg_type == "resolve_alert":
                alert_id = data.get("alert_id")

                if alert_id:
                    alert = db.query(SecurityAlert).filter(
                        SecurityAlert.alert_id   == alert_id,
                        SecurityAlert.company_id == company_id
                    ).first()

                    if alert and alert.status == "open":
                        alert.status      = "resolved"
                        alert.resolved_at = datetime.utcnow()
                        db.commit()

                        await websocket.send_json({
                            "type":      "alert_resolved",
                            "alert_id":  alert_id,
                            "timestamp": datetime.utcnow().isoformat()
                        })

    except WebSocketDisconnect:
        print(f"❌ Dashboard disconnected — company_id: {company_id}")

    except Exception as e:
        print(f"💥 Dashboard WS error: {e}")

    finally:
        if company_id and company_id in dashboard_clients:
            if websocket in dashboard_clients[company_id]:
                dashboard_clients[company_id].remove(websocket)

        db.close()