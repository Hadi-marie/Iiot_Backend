from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey

from sqlalchemy.orm import relationship

from datetime import datetime

import uuid
import secrets

from app.db import Base


class Device(Base):

    __tablename__ = "device"

    # 🔥 Primary Key
    device_id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    # 🔥 Public UUID
    public_id = Column(
        String,
        unique=True,
        default=lambda: str(uuid.uuid4())
    )

    # 🔥 الشركة / الشبكة
    network_id = Column(
        Integer,
        ForeignKey("network.network_id")
    )

    # 🔥 اسم الجهاز
    device_name = Column(
        String(255)
    )

    # 🔥 نوع الجهاز
    device_type = Column(
        String(255)
    )

    # 🔥 IP Address
    ip_address = Column(
        String(255)
    )

    # 🔥 حالة الجهاز
    status = Column(
        String(50),
        default="active"
    )

    # ❤️ آخر heartbeat
    last_seen = Column(
        DateTime,
        default=datetime.utcnow
    )

    # 🔐 Device Token
    device_token = Column(
        String(255),
        unique=True,
        default=lambda: secrets.token_hex(32)
    )

    # 🔐 Secret Key
    secret_key = Column(
        String(255),
        default=lambda: secrets.token_hex(32)
    )

    # 🔥 ORM Relationship
    network = relationship(
        "Network",
        back_populates="devices"
    )