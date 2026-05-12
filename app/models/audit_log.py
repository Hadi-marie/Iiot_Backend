from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey

from datetime import datetime

from app.db import Base


class AuditLog(Base):

    __tablename__ = "audit_log"

    log_id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    # 🏢 الشركة
    company_id = Column(
        Integer,
        ForeignKey("company.company_id")
    )

    # 📌 نوع الحدث
    event_type = Column(
        String(100)
    )

    # 🔥 مستوى الخطورة
    severity = Column(
        String(50)
    )

    # 📝 الوصف
    description = Column(
        String(500)
    )

    # ⏰ وقت الحدث
    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )