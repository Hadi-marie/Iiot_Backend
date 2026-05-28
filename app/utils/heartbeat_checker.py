import time

from datetime import datetime, timedelta

from app.db import SessionLocal
from app.models.device import Device
from app.models.security_alert import SecurityAlert

HEARTBEAT_TIMEOUT = 30   # ثانية
CHECK_INTERVAL    = 10   # ثانية


def start_heartbeat_checker():

    while True:

        db = SessionLocal()

        try:

            cutoff = datetime.utcnow() - timedelta(seconds=HEARTBEAT_TIMEOUT)

            # ✅ لا نحول الأجهزة المحظورة أو المحجوبة يدوياً إلى offline
            # فقط الأجهزة active أو warning أو maintenance
            timeout_devices = db.query(Device).filter(
                Device.last_seen != None,
                Device.last_seen  < cutoff,
                Device.status.in_(["active", "warning", "maintenance"])
            ).all()

            for device in timeout_devices:

                print(f"🚨 Heartbeat timeout: {device.device_name}")

                device.status = "offline"

                try:
                    company_id = device.network.company_id
                except Exception:
                    company_id = None

                db.add(SecurityAlert(
                    company_id = company_id,
                    device_id  = device.device_id,
                    alert_type = "heartbeat_timeout",
                    severity   = "high",
                    message    = f"{device.device_name} is offline — heartbeat timeout",
                    source     = "heartbeat_checker",
                    status     = "open"
                ))

            if timeout_devices:
                db.commit()
                print(f"✅ Marked {len(timeout_devices)} device(s) offline")

        except Exception as e:
            print(f"💥 Heartbeat checker error: {e}")

        finally:
            db.close()

        time.sleep(CHECK_INTERVAL)