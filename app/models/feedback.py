from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Numeric
from datetime import datetime
from app.db import Base


class Feedback(Base):

    __tablename__ = "feedback"

    feedback_id = Column(Integer, primary_key=True, index=True)

    company_id  = Column(Integer, ForeignKey("company.company_id"))

    # نص التعليق
    content     = Column(Text)

    # نتيجة التحليل
    sentiment        = Column(String(20))   # "positive" | "negative" | "neutral"
    sentiment_score  = Column(Numeric(5, 4))  # -1.0 إلى 1.0

    created_at  = Column(DateTime, default=datetime.utcnow)