from sqlalchemy import Column, Integer, String, DateTime, Boolean
from datetime import datetime
from app.db import Base


class SuperAdmin(Base):

    __tablename__ = "super_admin"

    super_admin_id = Column(Integer, primary_key=True, index=True)

    name          = Column(String(255))
    email         = Column(String(255), unique=True)
    password_hash = Column(String(255))

    is_active  = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)