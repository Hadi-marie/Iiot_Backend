from sqlalchemy import Column, Integer, String, ForeignKey
from app.db import Base

import uuid


class Device(Base):
    __tablename__ = "device"

    device_id = Column(Integer, primary_key=True, index=True)
    device_name = Column(String(100))
    device_type = Column(String(50))
    # 🔥 UUID خارجي
    public_id = Column(
        String(100),
        unique=True,
        default=lambda: str(uuid.uuid4())
    )

    network_id = Column(
        Integer,
        ForeignKey("network.network_id")
    )
    
    ip_address = Column(String(50))

    status = Column(String(50))