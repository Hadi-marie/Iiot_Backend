from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric
from datetime import datetime
from app.db import Base


class Subscription(Base):
    __tablename__ = "subscription"  # نفس اسم الجدول بالداتابيز

    subscription_id = Column(Integer, primary_key=True, index=True)

    company_id = Column(Integer, ForeignKey("company.company_id"))

    status = Column(String(50))

    start_date = Column(DateTime)
    end_date = Column(DateTime)

    price = Column(Numeric(10, 2))

    created_at = Column(DateTime, default=datetime.utcnow)