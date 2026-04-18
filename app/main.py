from fastapi import FastAPI
from app.db import Base, engine
from app.routes import auth
app = FastAPI()



@app.get("/")
def root():
    return {"message": "Server running"}
app = FastAPI(debug=True)
app.include_router(auth.router, prefix="/auth")