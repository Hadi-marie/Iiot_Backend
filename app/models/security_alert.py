from sqlalchemy import Column, Integer, String
from sqlalchemy import ForeignKey
from sqlalchemy import DateTime

from datetime import datetime

from app.db import Base


class SecurityAlert(Base):

    __tablename__ = "security_alert"

    alert_id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    # 🔥 الشركة
    company_id = Column(
        Integer,
        ForeignKey("company.company_id")
    )

    # 🔥 الجهاز
    device_id = Column(
        Integer,
        ForeignKey("device.device_id")
    )

    # 🚨 نوع التنبيه
    alert_type = Column(
        String(100)
    )

    # 🔥 شدة التنبيه
    severity = Column(
        String(50)
    )

    # 📝 الرسالة
    message = Column(
        String(500)
    )

    # 📡 مصدر التنبيه
    source = Column(
        String(100)
    )

    # 🔥 حالة التنبيه
    status = Column(
        String(50),
        default="open"
    )

    # ⏰ وقت الإنشاء
    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    # ⏰ وقت الإغلاق
    resolved_at = Column(
        DateTime,
        nullable=True
    )