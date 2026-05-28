import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import Base, engine
from app.models import (
    plan,
    super_admin,
    feedback as feedback_model,
    network_flow,
    detection_result,
    action,
    unblock_request,
    api_key,
    report,
    verification_code
)
from app.routes import auth, payment, devices, network, dashboard
from app.routes import ws_monitor, ws_dashboard, alert, predict
from app.routes import super_admin_route, feedback_route, unblock_route
from app.routes import report_route, api_key_route, settings_route
from app.utils.heartbeat_checker import start_heartbeat_checker


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    threading.Thread(
        target=start_heartbeat_checker,
        daemon=True
    ).start()
    yield


app = FastAPI(
    title="IIoT Security Platform",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,              prefix="/auth",         tags=["Auth"])
app.include_router(payment.router,           prefix="/payment",      tags=["Payment"])
app.include_router(devices.router,           prefix="/devices",      tags=["Devices"])
app.include_router(network.router,           prefix="/networks",     tags=["Network"])
app.include_router(dashboard.router,         prefix="/dashboard",    tags=["Dashboard"])
app.include_router(alert.router,             prefix="/alerts",       tags=["Alerts"])
app.include_router(predict.router,           prefix="/ml",           tags=["ML"])
app.include_router(super_admin_route.router, prefix="/super-admin",  tags=["Super Admin"])
app.include_router(feedback_route.router,    prefix="/feedback",     tags=["Feedback"])
app.include_router(unblock_route.router,     prefix="/unblock",      tags=["Unblock"])
app.include_router(report_route.router,      prefix="/reports",      tags=["Reports"])
app.include_router(api_key_route.router,     prefix="/api-keys",     tags=["API Keys"])
app.include_router(settings_route.router,    prefix="/settings",     tags=["Settings"])
app.include_router(ws_monitor.router)
app.include_router(ws_dashboard.router)


@app.get("/", tags=["Health"])
def root():
    return {"message": "IIoT Security Platform — running ✅"}