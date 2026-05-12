import time

from datetime import datetime, timedelta

from app.db import SessionLocal
from app.models.device import Device
from app.models.security_alert import SecurityAlert

HEARTBEAT_TIMEOUT = 30   # ثانية — جهاز لم يرسل heartbeat منذ 30 ثانية → offline
CHECK_INTERVAL    = 10   # ثانية — فترة الفحص


def start_heartbeat_checker():
    """
    يعمل في background thread.
    يفحص كل جهاز — إذا last_seen قديم أكثر من HEARTBEAT_TIMEOUT يحوّله offline
    وينشئ SecurityAlert.
    """

    while True:

        db = SessionLocal()

        try:

            cutoff = datetime.utcnow() - timedelta(seconds=HEARTBEAT_TIMEOUT)

            # ✅ نضيف شرط last_seen != None لتجنب كسر الـ filter
            timeout_devices = db.query(Device).filter(
                Device.last_seen != None,
                Device.last_seen  < cutoff,
                Device.status    != "offline"
            ).all()

            for device in timeout_devices:

                print(f"🚨 Heartbeat timeout: {device.device_name}")

                # تحويل الجهاز offline
                device.status = "offline"

                # ✅ company_id من الـ relationship وليس network_id مباشرة
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