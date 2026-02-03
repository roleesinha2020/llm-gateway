import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.core.models import Request as RequestLog
from src.core.models import Tenant

router = APIRouter(prefix="/admin")


class CreateTenantRequest(BaseModel):
    name: str
    rate_limit: int = 100
    monthly_budget: Optional[float] = None


@router.post("/tenants")
async def create_tenant(
    body: CreateTenantRequest,
    db: Session = Depends(get_db),
):
    api_key = f"llm-gw-{secrets.token_urlsafe(32)}"

    tenant = Tenant(
        name=body.name,
        api_key=api_key,
        rate_limit=body.rate_limit,
        monthly_budget=body.monthly_budget,
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)

    return {
        "tenant_id": tenant.id,
        "name": tenant.name,
        "api_key": api_key,
        "rate_limit": tenant.rate_limit,
    }


@router.get("/tenants/{tenant_id}/usage")
async def get_tenant_usage(
    tenant_id: str,
    days: int = 30,
    db: Session = Depends(get_db),
):
    start_date = datetime.utcnow() - timedelta(days=days)

    usage = (
        db.query(
            func.count(RequestLog.id).label("total_requests"),
            func.sum(RequestLog.total_tokens).label("total_tokens"),
            func.sum(RequestLog.cost).label("total_cost"),
            func.avg(RequestLog.latency_ms).label("avg_latency_ms"),
            RequestLog.provider,
        )
        .filter(
            RequestLog.tenant_id == tenant_id,
            RequestLog.created_at >= start_date,
        )
        .group_by(RequestLog.provider)
        .all()
    )

    return {
        "tenant_id": tenant_id,
        "period_days": days,
        "usage_by_provider": [
            {
                "provider": row.provider,
                "requests": row.total_requests,
                "tokens": row.total_tokens or 0,
                "cost": float(row.total_cost or 0),
                "avg_latency_ms": float(row.avg_latency_ms or 0),
            }
            for row in usage
        ],
    }
