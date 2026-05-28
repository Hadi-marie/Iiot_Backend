from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from datetime import datetime
from app.db import Base


class VerificationCode(Base):

    __tablename__ = "verification_code"

    id         = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("company_admin.admin_id"), nullable=True)
    email      = Column(String(255))
    code       = Column(String(10))
    purpose    = Column(String(50))  # "register" | "email_change" | "email_change_old"
    token      = Column(String(255), nullable=True)  # للإيميل القديم accept/reject
    extra_data = Column(String(255), nullable=True)  # إيميل جديد أو بيانات إضافية
    is_used    = Column(Boolean, default=False)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)