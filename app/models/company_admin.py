from sqlalchemy import Column, Integer, String, ForeignKey
from app.db import Base

class CompanyAdmin(Base):
    __tablename__ = "company_admin"

    admin_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255))
    email = Column(String(255), unique=True)
    password_hash = Column(String(255))

    company_id = Column(Integer, ForeignKey("company.company_id"))