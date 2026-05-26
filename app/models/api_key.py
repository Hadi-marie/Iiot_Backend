from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from datetime import datetime
import secrets
from app.db import Base


class ApiKey(Base):

    __tablename__ = "api_key"

    api_key_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("company.company_id"))

    key_value  = Column(String(255), unique=True, default=lambda: secrets.token_hex(32))
    status     = Column(String(50), default="active")  # "active" | "revoked"

    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)