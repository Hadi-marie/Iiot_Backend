from sqlalchemy import Column, Integer, String, Numeric, Boolean
from app.db import Base


class Plan(Base):

    __tablename__ = "plan"

    plan_id = Column(Integer, primary_key=True, index=True)

    # اسم الخطة
    name = Column(String(100), unique=True)  # "pro" | "premium"

    # السعر الشهري
    price = Column(Numeric(10, 2))

    # مدة الاشتراك بالأيام
    duration_days = Column(Integer, default=30)

    # اسم ملف الموديل على Hugging Face
    model_filename = Column(String(255))

    # الـ threshold للموديل
    threshold = Column(Numeric(5, 4))

    # هل الخطة متاحة؟
    is_active = Column(Boolean, default=True)