import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.orm import relationship

from src.core.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    api_key = Column(String, unique=True, nullable=False)
    rate_limit = Column(Integer, default=100)
    monthly_budget = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Integer, default=1)

    requests = relationship("Request", back_populates="tenant")
    usage = relationship("UsageLog", back_populates="tenant")


class Request(Base):
    __tablename__ = "requests"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    provider = Column(String, nullable=False)
    model = Column(String, nullable=False)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    cost = Column(Float, default=0.0)
    latency_ms = Column(Integer)
    status = Column(String)
    error_message = Column(String, nullable=True)
    cache_hit = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="requests")

    __table_args__ = (
        Index("idx_tenant_created", "tenant_id", "created_at"),
        Index("idx_provider_status", "provider", "status"),
    )


class UsageLog(Base):
    __tablename__ = "usage_logs"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    date = Column(DateTime, default=datetime.utcnow)
    total_requests = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    total_cost = Column(Float, default=0.0)
    provider_breakdown = Column(JSON)

    tenant = relationship("Tenant", back_populates="usage")

    __table_args__ = (
        Index("idx_tenant_date", "tenant_id", "date"),
    )
