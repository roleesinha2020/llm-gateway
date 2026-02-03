import time
from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from src.core.config import get_settings
from src.core.database import get_db
from src.core.models import Request as RequestLog
from src.core.models import Tenant
from src.core.redis_client import redis_client
from src.middleware.auth import get_current_tenant
from src.middleware.rate_limiter import check_rate_limit
from src.providers.base import LLMRequest
from src.providers.provider_factory import ProviderFactory

router = APIRouter()
logger = structlog.get_logger()
settings = get_settings()


@router.post("/completions")
async def create_completion(
    llm_request: LLMRequest,
    request: Request,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    # Check rate limit
    remaining = await check_rate_limit(tenant)

    # Generate cache key
    cache_key = redis_client.generate_cache_key(
        tenant.id,
        "any",
        llm_request.model,
        str(llm_request.messages),
    )

    # Check cache
    cached_response = await redis_client.get_cache(cache_key)
    if cached_response:
        logger.info("Cache hit", tenant_id=tenant.id, cache_key=cache_key)

        request_log = RequestLog(
            tenant_id=tenant.id,
            provider="cached",
            model=llm_request.model,
            status="success",
            cache_hit=1,
            created_at=datetime.utcnow(),
        )
        db.add(request_log)
        db.commit()

        return {
            "cached": True,
            "response": cached_response,
            "rate_limit_remaining": remaining,
        }

    # Try providers in fallback order
    start_time = time.time()
    response = None
    cost = 0.0
    error_message = None

    for provider_name in settings.PROVIDER_FALLBACK_ORDER:
        try:
            provider = ProviderFactory.get_provider(provider_name)
            if not provider:
                continue

            logger.info(
                "Attempting provider",
                provider=provider_name,
                tenant_id=tenant.id,
            )

            response = await provider.complete(llm_request)

            cost = provider.calculate_cost(
                response.prompt_tokens,
                response.completion_tokens,
            )

            await redis_client.set_cache(
                cache_key,
                {
                    "content": response.content,
                    "model": response.model,
                    "provider": response.provider,
                },
            )

            break

        except Exception as e:
            logger.error(
                "Provider failed",
                provider=provider_name,
                error=str(e),
                tenant_id=tenant.id,
            )
            error_message = str(e)
            continue

    if not response:
        raise HTTPException(
            status_code=503,
            detail=f"All providers failed. Last error: {error_message}",
        )

    latency_ms = int((time.time() - start_time) * 1000)

    request_log = RequestLog(
        tenant_id=tenant.id,
        provider=response.provider,
        model=response.model,
        prompt_tokens=response.prompt_tokens,
        completion_tokens=response.completion_tokens,
        total_tokens=response.total_tokens,
        cost=cost,
        latency_ms=latency_ms,
        status="success",
        cache_hit=0,
        created_at=datetime.utcnow(),
    )
    db.add(request_log)
    db.commit()

    logger.info(
        "Completion successful",
        tenant_id=tenant.id,
        provider=response.provider,
        tokens=response.total_tokens,
        cost=cost,
        latency_ms=latency_ms,
    )

    return {
        "cached": False,
        "response": response.model_dump(),
        "cost": cost,
        "latency_ms": latency_ms,
        "rate_limit_remaining": remaining,
    }
