from fastapi import FastAPI
from app.db import Base, engine
from app.routes import auth
from app.coree.security import create_access_token
app = FastAPI()

print(create_access_token({"user_id": 1}))

@app.get("/")
def root():
    return {"message": "Server running"}
app = FastAPI(debug=True)
app.include_router(auth.router, prefix="/auth")