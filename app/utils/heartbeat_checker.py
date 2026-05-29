import time

from datetime import datetime, timedelta

from app.db import SessionLocal
from app.models.device import Device
from app.models.security_alert import SecurityAlert

HEARTBEAT_TIMEOUT = 60   # ثانية — رُفع من 30 إلى 60
CHECK_INTERVAL    = 20   # ثانية — فحص كل 20 ثانية


def start_heartbeat_checker():

    while True:

        db = SessionLocal()

        try:

            cutoff = datetime.utcnow() - timedelta(seconds=HEARTBEAT_TIMEOUT)

            # ✅ شروط صارمة:
            # 1. last_seen موجود (ليس NULL) — يعني الجهاز اتصل فعلاً من قبل
            # 2. last_seen قديم أكثر من HEARTBEAT_TIMEOUT
            # 3. الحالة active أو warning أو maintenance فقط
            # 4. لا نلمس blocked أو offline أبداً
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