from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from datetime import datetime
from app.db import Base


class UnblockRequest(Base):

    __tablename__ = "unblock_request"

    request_id = Column(Integer, primary_key=True, index=True)
    device_id  = Column(Integer, ForeignKey("device.device_id"))
    company_id = Column(Integer, ForeignKey("company.company_id"))
    admin_id   = Column(Integer, ForeignKey("company_admin.admin_id"))

    reason     = Column(Text)
    status     = Column(String(50), default="pending")  # "pending" | "approved" | "rejected"

    requested_at = Column(DateTime, default=datetime.utcnow)
    resolved_at  = Column(DateTime, nullable=True)