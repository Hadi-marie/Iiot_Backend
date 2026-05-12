from fastapi import WebSocket

# { company_id: [websocket, ...] }
dashboard_clients: dict[int, list[WebSocket]] = {}


async def broadcast_alert_to_company(company_id: int, alert_data: dict):
    """
    تُستدعى من ws_monitor أو ML model —
    تبث الـ alert لكل متصفحات الشركة لحظياً.
    """
    if company_id not in dashboard_clients:
        return

    dead_clients = []

    for client in dashboard_clients[company_id]:
        try:
            await client.send_json(alert_data)
        except Exception:
            dead_clients.append(client)

    for dead in dead_clients:
        dashboard_clients[company_id].remove(dead)