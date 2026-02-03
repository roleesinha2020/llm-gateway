from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from src.core.config import get_settings
from src.core.database import get_db
from src.core.models import Tenant

settings = get_settings()
api_key_header = APIKeyHeader(name=settings.API_KEY_HEADER, auto_error=False)


async def get_current_tenant(
    request: Request,
    db: Session = Depends(get_db),
) -> Tenant:
    api_key = request.headers.get(settings.API_KEY_HEADER)

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key missing",
        )

    tenant = db.query(Tenant).filter(Tenant.api_key == api_key).first()

    if not tenant or not tenant.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    return tenant
