import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import Base, engine
from app.routes import auth, payment, devices, network, dashboard, ws_monitor
from app.routes import ws_dashboard
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

app.include_router(auth.router,         prefix="/auth",      tags=["Auth"])
app.include_router(payment.router,      prefix="/payment",   tags=["Payment"])
app.include_router(devices.router,      prefix="/devices",   tags=["Devices"])
app.include_router(network.router,      prefix="/networks",  tags=["Network"])
app.include_router(dashboard.router,    prefix="/dashboard", tags=["Dashboard"])
app.include_router(ws_monitor.router)    # ws://..../monitor
app.include_router(ws_dashboard.router)  # ws://..../ws/dashboard


@app.get("/", tags=["Health"])
def root():
    return {"message": "IIoT Security Platform — running ✅"}