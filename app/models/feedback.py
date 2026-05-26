from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Numeric
from datetime import datetime
from app.db import Base


class Feedback(Base):

    __tablename__ = "feedback"

    feedback_id = Column(Integer, primary_key=True, index=True)

    company_id  = Column(Integer, ForeignKey("company.company_id"))
    admin_id    = Column(Integer, ForeignKey("company_admin.admin_id"))

    content = Column(Text)

    sentiment       = Column(String(20))
    sentiment_score = Column(Numeric(5, 4))

    created_at = Column(DateTime, default=datetime.utcnow)