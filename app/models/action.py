from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from datetime import datetime
from app.db import Base


class Action(Base):

    __tablename__ = "action"

    action_id    = Column(Integer, primary_key=True, index=True)
    detection_id = Column(Integer, ForeignKey("detection_result.detection_id"))
    device_id    = Column(Integer, ForeignKey("device.device_id"))
    company_id   = Column(Integer, ForeignKey("company.company_id"))

    # نوع الإجراء
    action_type  = Column(String(50))  # "block" | "alert" | "unblock" | "monitor"

    # من نفّذ الإجراء
    executed_by  = Column(String(50))  # "system" | "admin"

    executed_at  = Column(DateTime, default=datetime.utcnow)