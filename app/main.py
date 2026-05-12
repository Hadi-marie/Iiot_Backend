from fastapi import FastAPI
from app.db import Base, engine
from app.routes import auth, payment
from app.routes import devices
from app.routes import devices
from app.routes import network
from app.routes import devices
# إنشاء الجداول
Base.metadata.create_all(bind=engine)

app = FastAPI(debug=True)
# 🔥 تشغيل heartbeat checker
threading.Thread(
    target=start_heartbeat_checker,
    daemon=True
).start()
threading.Thread(
    target=start_heartbeat_checker,
    daemon=True
).start()
# routers
app.include_router(auth.router, prefix="/auth")
app.include_router(payment.router, prefix="/payment")
app.include_router(devices.router, prefix="/devices")
app.include_router(network.router, prefix="/networks")
app.include_router(devices.router, prefix="/devices")
@app.get("/")
def root():
    return {"message": "Server running"}



app.include_router(devices.router, prefix="/devices")