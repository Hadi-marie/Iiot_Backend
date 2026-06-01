from sqlalchemy import Column, Integer, String, ForeignKey
from app.db import Base
from sqlalchemy.orm import relationship
import uuid


class Network(Base):
    __tablename__ = "network"

    network_id = Column(Integer, primary_key=True, index=True)

    public_id = Column(
        String(100),
        unique=True,
        default=lambda: str(uuid.uuid4())
    )

    company_id = Column(Integer, ForeignKey("company.company_id"))
    network_name = Column(String(255), nullable=True)
    ip_range = Column(String(100))

    devices = relationship("Device", back_populates="network")