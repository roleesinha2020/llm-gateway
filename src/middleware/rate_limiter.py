import structlog
from fastapi import HTTPException, status

from src.core.models import Tenant
from src.core.redis_client import redis_client

logger = structlog.get_logger()


async def check_rate_limit(tenant: Tenant):
    is_allowed, remaining = await redis_client.check_rate_limit(
        tenant.id,
        tenant.rate_limit,
    )

    if not is_allowed:
        logger.warning(
            "Rate limit exceeded",
            tenant_id=tenant.id,
            limit=tenant.rate_limit,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Limit: {tenant.rate_limit} requests/minute",
            headers={"Retry-After": "60"},
        )

    return remaining
