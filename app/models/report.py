from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from datetime import datetime
from app.db import Base


class Report(Base):

    __tablename__ = "report"

    report_id  = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("company.company_id"))

    type         = Column(String(50))  # "security" | "performance" | "summary"
    generated_at = Column(DateTime, default=datetime.utcnow)