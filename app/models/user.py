from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from app.db import Base

class User(Base):
    __tablename__ = "system_users"

    user_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255))
    email = Column(String(255), unique=True, index=True)
    password_hash = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)