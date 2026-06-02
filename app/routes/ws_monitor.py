from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from datetime import datetime

import time
import hmac
import hashlib

from app.db import SessionLocal
from app.models.device import Device
from app.models.security_alert import SecurityAlert
from app.models.audit_log import AuditLog

from app.utils.broadcaster import broadcast_alert_to_company

router = APIRouter()

company_clients: dict[int, list[WebSocket]] = {}
device_message_tracker: dict[str, list[float]] = {}
used_nonces: dict[str, dict[str, float]] = {}

NONCE_TTL = 60


def _cleanup_nonces(device_id: str, current_time: float):
    if device_id in used_nonces:
        used_nonces[device_id] = {
            n: exp
            for n, exp in used_nonces[device_id].items()
            if exp > current_time
        }


def _get_company_id(device: Device) -> int:
    return device.network.company_id


async def _broadcast_to_company(company_id: int, message: dict):
    if company_id not in company_clients:
        return

    dead_clients = []

    for client in company_clients[company_id]:
        try:
            await client.send_json(message)
        except Exception:
            dead_clients.append(client)

    for dead in dead_clients:
        company_clients[company_id].remove(dead)


@router.websocket("/monitor")
async def websocket_monitor(websocket: WebSocket):

    await websocket.accept()
    print("✅ Device connected")

    db: Session = SessionLocal()
    authenticated_company_id: int | None = None

    try:

        while True:

            data = await websocket.receive_json()

            device_id    = data.get("device_id")
            device_token = data.get("device_token")
            new_status   = data.get("status")
            timestamp    = data.get("timestamp")
            signature    = data.get("signature")
            nonce        = data.get("nonce")

            if not all([device_id, device_token, new_status,
                        timestamp, signature, nonce]):
                await websocket.send_json({
                    "type":    "validation_error",
                    "message": "Missing required fields"
                })
                continue

            current_time = time.time()

            try:
                timestamp = float(timestamp)
            except (TypeError, ValueError):
                await websocket.send_json({
                    "type":    "validation_error",
                    "message": "Invalid timestamp"
                })
                continue

            if abs(current_time - timestamp) > 30:
                await websocket.send_json({
                    "type":    "replay_attack",
                    "message": "Expired packet"
                })
                continue

            device = db.query(Device).filter(
                Device.public_id    == device_id,
                Device.device_token == device_token
            ).first()

            if not device:
                db.add(AuditLog(
                    company_id  = None,
                    event_type  = "DEVICE_AUTH_FAILED",
                    severity    = "high",
                    description = f"Failed auth for device_id: {device_id}"
                ))
                db.commit()

                await websocket.send_json({
                    "type":    "auth_error",
                    "message": "Invalid device or token"
                })
                continue

            # ✅ رفض الجهاز المحظور فوراً — لا يقدر يتصل أبداً
            if device.status == "blocked":
                await websocket.send_json({
                    "type":    "auth_error",
                    "message": "Device is blocked — connection refused"
                })
                await websocket.close()
                return

            _cleanup_nonces(device_id, current_time)

            if device_id not in used_nonces:
                used_nonces[device_id] = {}

            if nonce in used_nonces[device_id]:
                await websocket.send_json({
                    "type":    "nonce_error",
                    "message": "Replay packet detected"
                })
                continue

            used_nonces[device_id][nonce] = current_time + NONCE_TTL

            payload = f"{device_id}:{new_status}:{timestamp}:{nonce}"

            expected_signature = hmac.new(
                device.secret_key.encode(),
                payload.encode(),
                hashlib.sha256
            ).hexdigest()

            if not hmac.compare_digest(signature, expected_signature):
                await websocket.send_json({
                    "type":    "signature_error",
                    "message": "Invalid HMAC signature"
                })
                continue

            if device_id not in device_message_tracker:
                device_message_tracker[device_id] = []

            device_message_tracker[device_id] = [
                ts for ts in device_message_tracker[device_id]
                if current_time - ts < 5
            ]

            device_message_tracker[device_id].append(current_time)

            if len(device_message_tracker[device_id]) > 10:
                db.add(AuditLog(
                    company_id  = _get_company_id(device),
                    event_type  = "RATE_LIMIT_EXCEEDED",
                    severity    = "high",
                    description = f"{device.device_name} exceeded WS rate limit"
                ))
                db.commit()

                await websocket.send_json({
                    "type":    "rate_limit",
                    "message": "Too many requests"
                })
                await websocket.close()
                break

            company_id = _get_company_id(device)
            authenticated_company_id = company_id

            if company_id not in company_clients:
                company_clients[company_id] = []

            if websocket not in company_clients[company_id]:
                company_clients[company_id].append(websocket)

            allowed_statuses = {"active", "blocked", "offline", "warning", "maintenance"}

            if new_status not in allowed_statuses:
                await websocket.send_json({
                    "type":    "validation_error",
                    "message": "Invalid status"
                })
                continue

            # ✅ الجهاز blocked لا يتغير إلا عبر /unblock/
            # بقية الحالات تتغير بحرية
            if new_status == "active" and device.status == "blocked":
                await websocket.send_json({
                    "type":    "auth_error",
                    "message": "Device is blocked — cannot change status"
                })
                continue

            device.status    = new_status
            device.last_seen = datetime.utcnow()
            db.commit()

            db.add(AuditLog(
                company_id  = company_id,
                event_type  = "DEVICE_STATUS_UPDATE",
                severity    = "low",
                description = f"{device.device_name} updated status to {new_status}"
            ))
            db.commit()

            await _broadcast_to_company(company_id, {
                "type":       "device_status_update",
                "device_id":  device_id,
                "new_status": new_status,
                "timestamp":  datetime.utcnow().isoformat()
            })

            if new_status in ("blocked", "offline", "warning"):

                severity_map = {
                    "blocked": "critical",
                    "offline": "high",
                    "warning": "medium"
                }
                severity = severity_map[new_status]

                alert_data = {
                    "type":        "security_alert",
                    "severity":    severity,
                    "device_id":   device_id,
                    "device_name": device.device_name,
                    "status":      new_status,
                    "message":     f"{device.device_name} changed status to {new_status}",
                    "timestamp":   datetime.utcnow().isoformat()
                }

                db.add(SecurityAlert(
                    company_id = company_id,
                    device_id  = device.device_id,
                    alert_type = "device_status",
                    severity   = severity,
                    message    = f"{device.device_name} changed status to {new_status}",
                    source     = "websocket_monitor",
                    status     = "open"
                ))

                db.add(AuditLog(
                    company_id  = company_id,
                    event_type  = "SECURITY_ALERT_CREATED",
                    severity    = severity,
                    description = f"Alert created for {device.device_name}"
                ))
                db.commit()

                await _broadcast_to_company(company_id, alert_data)
                await broadcast_alert_to_company(company_id, alert_data)

    except WebSocketDisconnect:
        print("❌ Device disconnected")

    except Exception as e:
        print(f"💥 Error: {e}")

    finally:
        if authenticated_company_id and authenticated_company_id in company_clients:
            if websocket in company_clients[authenticated_company_id]:
                company_clients[authenticated_company_id].remove(websocket)

        db.close()