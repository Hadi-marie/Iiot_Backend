from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, Boolean
from datetime import datetime
from app.db import Base


class DetectionResult(Base):

    __tablename__ = "detection_result"

    detection_id = Column(Integer, primary_key=True, index=True)
    flow_id      = Column(Integer, ForeignKey("network_flow.flow_id"))
    device_id    = Column(Integer, ForeignKey("device.device_id"))
    company_id   = Column(Integer, ForeignKey("company.company_id"))

    # نتيجة الموديل
    is_attack        = Column(Boolean)
    confidence_score = Column(Float)      # 0.0 - 1.0
    plan_used        = Column(String(50)) # "pro" | "premium"
    action_taken     = Column(String(50)) # "block" | "alert" | "normal"

    detected_at = Column(DateTime, default=datetime.utcnow)