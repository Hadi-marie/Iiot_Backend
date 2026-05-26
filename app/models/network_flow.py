from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float
from datetime import datetime
from app.db import Base


class NetworkFlow(Base):

    __tablename__ = "network_flow"

    flow_id    = Column(Integer, primary_key=True, index=True)
    device_id  = Column(Integer, ForeignKey("device.device_id"))
    company_id = Column(Integer, ForeignKey("company.company_id"))

    # Network features — نفس الـ 28 feature للموديل
    src_port   = Column(Float)  # Sport
    dst_port   = Column(Float)  # Dport
    protocol   = Column(Float)  # Proto
    duration   = Column(Float)  # Dur
    src_bytes  = Column(Float)  # SrcBytes
    src_pkts   = Column(Float)  # SrcPkts
    tot_pkts   = Column(Float)  # TotPkts
    load       = Column(Float)  # Load
    rate       = Column(Float)  # Rate
    src_rate   = Column(Float)  # SrcRate
    src_load   = Column(Float)  # SrcLoad
    mean       = Column(Float)  # Mean
    min_val    = Column(Float)  # Min
    max_val    = Column(Float)  # Max
    sum_val    = Column(Float)  # Sum
    run_time   = Column(Float)  # RunTime
    idle_time  = Column(Float)  # IdleTime
    s_ttl      = Column(Float)  # sTtl
    d_ttl      = Column(Float)  # dTtl
    s_int_pkt  = Column(Float)  # SIntPkt
    d_int_pkt  = Column(Float)  # DIntPkt
    syn_ack    = Column(Float)  # SynAck
    tcp_rtt    = Column(Float)  # TcpRtt
    p_loss     = Column(Float)  # pLoss
    s_app_bytes= Column(Float)  # SAppBytes
    src_jitter = Column(Float)  # SrcJitter
    dst_jitter = Column(Float)  # DstJitter
    src_jit_act= Column(Float)  # SrcJitAct

    captured_at = Column(DateTime, default=datetime.utcnow)