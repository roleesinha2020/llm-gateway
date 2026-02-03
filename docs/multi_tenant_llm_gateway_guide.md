# Multi-Tenant LLM Gateway - Complete Project Guide

## Project Overview

**Goal:** Build a production-ready proxy/gateway that sits between client applications and LLM providers (OpenAI, Anthropic, local models), providing enterprise features like rate limiting, cost tracking, caching, and multi-provider fallback.

**Why This Project Matters:**
- Demonstrates production AI infrastructure skills
- Shows understanding of multi-tenancy and resource management
- Proves you can build systems AI teams actually need
- Combines your HashiCorp infrastructure expertise with AI

**Timeline:** 6-8 weeks (2-3 hours/day)

---

## Architecture Overview

```
┌─────────────┐
│   Client    │
│ Application │
└──────┬──────┘
       │
       ▼
┌──────────────────────────────────────┐
│     LLM Gateway (FastAPI/Go)         │
│  ┌────────────────────────────────┐  │
│  │  Authentication & Tenant ID    │  │
│  └────────────┬───────────────────┘  │
│               ▼                      │
│  ┌────────────────────────────────┐  │
│  │    Rate Limiter (Redis)        │  │
│  └────────────┬───────────────────┘  │
│               ▼                      │
│  ┌────────────────────────────────┐  │
│  │  Prompt Cache Check (Redis)    │  │
│  └────────────┬───────────────────┘  │
│               ▼                      │
│  ┌────────────────────────────────┐  │
│  │   Provider Router & Fallback   │  │
│  └────────────┬───────────────────┘  │
│               ▼                      │
│  ┌────────────────────────────────┐  │
│  │  Cost Tracking & Logging       │  │
│  └────────────────────────────────┘  │
└───────────┬──────────────────────────┘
            │
    ┌───────┴────────┐
    ▼                ▼                ▼
┌────────┐    ┌──────────┐    ┌─────────┐
│ OpenAI │    │Anthropic │    │  Local  │
└────────┘    └──────────┘    │  Model  │
                               └─────────┘
```

---

## Phase 1: Foundation & Local Development (Week 1-2)

### Step 1.1: Project Setup

**Learning Resources:**
- FastAPI Official Docs: https://fastapi.tiangolo.com/
- Python Async Programming: https://realpython.com/async-io-python/

**Action Items:**

1. **Initialize Project Structure**
```bash
mkdir llm-gateway
cd llm-gateway

# Create project structure (includes middleware dir)
mkdir -p src/{api,core,providers,middleware} tests k8s terraform docs

# Create __init__.py in every Python package (required for imports)
touch src/__init__.py src/api/__init__.py src/core/__init__.py \
      src/providers/__init__.py src/middleware/__init__.py \
      tests/__init__.py

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Initialize git
git init
cat > .gitignore << EOF
venv/
.env
__pycache__/
*.pyc
*.pyo
*.egg-info/
dist/
build/
.mypy_cache/
.pytest_cache/
.ruff_cache/
*.egg
.coverage
htmlcov/
EOF
```

2. **Create requirements.txt**
```bash
cat > requirements.txt << EOF
fastapi==0.115.6
uvicorn[standard]==0.34.0
pydantic==2.10.5
pydantic-settings==2.7.1
redis==5.2.1
httpx==0.28.1
openai==1.59.7
anthropic==0.43.0
python-jose[cryptography]==3.3.0
python-multipart==0.0.20
prometheus-client==0.21.1
structlog==24.4.0
sqlalchemy==2.0.36
alembic==1.14.1
psycopg2-binary==2.9.10
tenacity==9.0.0
EOF
```

3. **Create requirements-dev.txt**
```bash
cat > requirements-dev.txt << EOF
pytest==8.3.4
pytest-asyncio==0.25.2
pytest-cov==6.0.0
black==24.10.0
ruff==0.9.4
mypy==1.14.1
httpx==0.28.1
EOF
```

4. **Install Dependencies**
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Step 1.2: Configuration Management

**Learning Resources:**
- Pydantic Settings: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- 12-Factor App Config: https://12factor.net/config

**Create `src/core/config.py`:**

```python
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # API Configuration
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "LLM Gateway"

    # Security
    SECRET_KEY: str = "change-me-in-production"
    API_KEY_HEADER: str = "X-API-Key"

    # Redis Configuration
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None

    # Database Configuration
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "llm_gateway"

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # Provider API Keys
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None

    # Rate Limiting
    DEFAULT_RATE_LIMIT: int = 100  # requests per minute

    # Cache Configuration
    CACHE_TTL: int = 3600  # 1 hour in seconds
    ENABLE_PROMPT_CACHE: bool = True

    # Cost Tracking
    OPENAI_COST_PER_1K_TOKENS: float = 0.002
    ANTHROPIC_COST_PER_1K_TOKENS: float = 0.003

    # Provider Fallback Order
    PROVIDER_FALLBACK_ORDER: list[str] = ["openai", "anthropic", "local"]

    # Monitoring
    ENABLE_METRICS: bool = True
    LOG_LEVEL: str = "INFO"

    # FIX: Use SettingsConfigDict instead of deprecated inner class Config
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)


@lru_cache()
def get_settings() -> Settings:
    return Settings()
```

**Create `.env.example`:**

```bash
# API Configuration
SECRET_KEY=your-secret-key-here
API_V1_STR=/api/v1

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=

# PostgreSQL
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-db-password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=llm_gateway

# Provider API Keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Rate Limiting
DEFAULT_RATE_LIMIT=100

# Cache
CACHE_TTL=3600
ENABLE_PROMPT_CACHE=true

# Logging
LOG_LEVEL=INFO
```

### Step 1.3: Database Models & Schema

**Learning Resources:**
- SQLAlchemy 2.0: https://docs.sqlalchemy.org/en/20/
- Database Design for Multi-tenancy: https://www.citusdata.com/blog/2016/10/03/designing-your-saas-database-for-high-scalability/

**Create `src/core/database.py`:**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from src.core.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# FIX: Use DeclarativeBase class instead of deprecated declarative_base()
class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

**Create `src/core/models.py`:**

```python
from sqlalchemy import Column, String, Integer, Float, DateTime, JSON, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from src.core.database import Base
import uuid

class Tenant(Base):
    __tablename__ = "tenants"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    api_key = Column(String, unique=True, nullable=False)
    rate_limit = Column(Integer, default=100)  # requests per minute
    monthly_budget = Column(Float, nullable=True)  # USD
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Integer, default=1)
    
    # Relationships
    requests = relationship("Request", back_populates="tenant")
    usage = relationship("UsageLog", back_populates="tenant")

class Request(Base):
    __tablename__ = "requests"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    provider = Column(String, nullable=False)  # openai, anthropic, local
    model = Column(String, nullable=False)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    cost = Column(Float, default=0.0)
    latency_ms = Column(Integer)
    status = Column(String)  # success, error, cached
    error_message = Column(String, nullable=True)
    cache_hit = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="requests")
    
    # Indexes for common queries
    __table_args__ = (
        Index('idx_tenant_created', 'tenant_id', 'created_at'),
        Index('idx_provider_status', 'provider', 'status'),
    )

class UsageLog(Base):
    __tablename__ = "usage_logs"
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    date = Column(DateTime, default=datetime.utcnow)
    total_requests = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    total_cost = Column(Float, default=0.0)
    provider_breakdown = Column(JSON)  # {openai: {...}, anthropic: {...}}
    
    # Relationships
    tenant = relationship("Tenant", back_populates="usage")
    
    __table_args__ = (
        Index('idx_tenant_date', 'tenant_id', 'date'),
    )
```

**Create Alembic Migration:**

```bash
# Initialize Alembic
alembic init alembic

# Edit alembic.ini - update sqlalchemy.url or use env var
# Then create initial migration
alembic revision --autogenerate -m "Initial schema"
alembic upgrade head
```

### Step 1.4: Redis Connection & Caching

**Learning Resources:**
- Redis Python Client: https://redis-py.readthedocs.io/
- Caching Strategies: https://redis.io/docs/manual/patterns/

**Create `src/core/redis_client.py`:**

```python
import redis.asyncio as redis
from typing import Optional
import json
import hashlib
from src.core.config import get_settings

settings = get_settings()

class RedisClient:
    def __init__(self):
        self.redis: Optional[redis.Redis] = None
    
    async def connect(self):
        # FIX: redis.Redis() is not awaitable — just construct it directly
        self.redis = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            decode_responses=True,
        )
    
    async def disconnect(self):
        if self.redis:
            await self.redis.close()
    
    async def get_cache(self, key: str) -> Optional[dict]:
        """Get cached response"""
        if not settings.ENABLE_PROMPT_CACHE:
            return None
        
        value = await self.redis.get(key)
        if value:
            return json.loads(value)
        return None
    
    async def set_cache(self, key: str, value: dict, ttl: int = None):
        """Set cached response"""
        if not settings.ENABLE_PROMPT_CACHE:
            return
        
        ttl = ttl or settings.CACHE_TTL
        await self.redis.setex(
            key,
            ttl,
            json.dumps(value)
        )
    
    def generate_cache_key(self, tenant_id: str, provider: str, 
                          model: str, prompt: str) -> str:
        """Generate deterministic cache key"""
        content = f"{tenant_id}:{provider}:{model}:{prompt}"
        return f"cache:{hashlib.sha256(content.encode()).hexdigest()}"
    
    async def check_rate_limit(self, tenant_id: str, limit: int) -> tuple[bool, int]:
        """
        Check rate limit using sliding window
        Returns: (is_allowed, remaining_requests)
        """
        key = f"rate_limit:{tenant_id}"
        current = await self.redis.get(key)
        
        if current is None:
            await self.redis.setex(key, 60, 1)
            return True, limit - 1
        
        current = int(current)
        if current >= limit:
            return False, 0
        
        await self.redis.incr(key)
        return True, limit - current - 1

# Global instance
redis_client = RedisClient()
```

---

## Phase 2: Core API Implementation (Week 2-3)

### Step 2.1: Provider Abstraction Layer

**Learning Resources:**
- OpenAI Python SDK: https://github.com/openai/openai-python
- Anthropic Python SDK: https://github.com/anthropics/anthropic-sdk-python
- Strategy Pattern: https://refactoring.guru/design-patterns/strategy

**Create `src/providers/base.py`:**

```python
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from pydantic import BaseModel

class LLMRequest(BaseModel):
    model: str
    messages: list[Dict[str, str]]
    temperature: float = 0.7
    max_tokens: int = 1000
    stream: bool = False

class LLMResponse(BaseModel):
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    finish_reason: str
    provider: str

class BaseLLMProvider(ABC):
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    @abstractmethod
    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Send completion request to provider"""
        pass
    
    @abstractmethod
    def calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate cost based on token usage"""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if provider is available"""
        pass
```

**Create `src/providers/openai_provider.py`:**

```python
from openai import AsyncOpenAI
from src.providers.base import BaseLLMProvider, LLMRequest, LLMResponse
from src.core.config import get_settings
import structlog

logger = structlog.get_logger()
settings = get_settings()

class OpenAIProvider(BaseLLMProvider):
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.client = AsyncOpenAI(api_key=api_key)
    
    async def complete(self, request: LLMRequest) -> LLMResponse:
        try:
            response = await self.client.chat.completions.create(
                model=request.model,
                messages=request.messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                stream=False
            )
            
            return LLMResponse(
                content=response.choices[0].message.content,
                model=response.model,
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
                finish_reason=response.choices[0].finish_reason,
                provider="openai"
            )
        except Exception as e:
            logger.error("OpenAI API error", error=str(e))
            raise
    
    def calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        # Simplified pricing - adjust based on actual model
        return (prompt_tokens + completion_tokens) / 1000 * settings.OPENAI_COST_PER_1K_TOKENS
    
    async def health_check(self) -> bool:
        try:
            await self.client.models.list()
            return True
        except Exception:  # FIX: never use bare except — it swallows KeyboardInterrupt
            return False
```

**Create `src/providers/anthropic_provider.py`:**

```python
import structlog
from anthropic import AsyncAnthropic

from src.core.config import get_settings
from src.providers.base import BaseLLMProvider, LLMRequest, LLMResponse

logger = structlog.get_logger()
settings = get_settings()


class AnthropicProvider(BaseLLMProvider):
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.client = AsyncAnthropic(api_key=api_key)

    async def complete(self, request: LLMRequest) -> LLMResponse:
        try:
            # FIX: Anthropic API requires system messages passed separately
            system_msg = None
            messages = []
            for msg in request.messages:
                if msg["role"] == "system":
                    system_msg = msg["content"]
                else:
                    messages.append(msg)

            kwargs = dict(
                model=request.model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )
            if system_msg:
                kwargs["system"] = system_msg

            response = await self.client.messages.create(**kwargs)

            return LLMResponse(
                content=response.content[0].text,
                model=response.model,
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
                total_tokens=response.usage.input_tokens + response.usage.output_tokens,
                finish_reason=response.stop_reason,
                provider="anthropic",
            )
        except Exception as e:
            logger.error("Anthropic API error", error=str(e))
            raise

    def calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        return (prompt_tokens + completion_tokens) / 1000 * settings.ANTHROPIC_COST_PER_1K_TOKENS

    async def health_check(self) -> bool:
        try:
            await self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=10,
                messages=[{"role": "user", "content": "test"}],
            )
            return True
        except Exception:  # FIX: never use bare except
            return False
```

**Create `src/providers/provider_factory.py`:**

```python
from typing import Optional
from src.providers.base import BaseLLMProvider
from src.providers.openai_provider import OpenAIProvider
from src.providers.anthropic_provider import AnthropicProvider
from src.core.config import get_settings

settings = get_settings()

class ProviderFactory:
    _providers: dict[str, BaseLLMProvider] = {}
    
    @classmethod
    def get_provider(cls, provider_name: str) -> Optional[BaseLLMProvider]:
        if provider_name in cls._providers:
            return cls._providers[provider_name]
        
        if provider_name == "openai" and settings.OPENAI_API_KEY:
            cls._providers["openai"] = OpenAIProvider(settings.OPENAI_API_KEY)
        elif provider_name == "anthropic" and settings.ANTHROPIC_API_KEY:
            cls._providers["anthropic"] = AnthropicProvider(settings.ANTHROPIC_API_KEY)
        # Add local provider implementation here
        
        return cls._providers.get(provider_name)
    
    @classmethod
    async def get_healthy_provider(cls, preferred_order: list[str]) -> Optional[BaseLLMProvider]:
        """Get first healthy provider from preference list"""
        for provider_name in preferred_order:
            provider = cls.get_provider(provider_name)
            if provider and await provider.health_check():
                return provider
        return None
```

### Step 2.2: Middleware for Auth & Rate Limiting

**Create `src/middleware/auth.py`:**

```python
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
    # FIX: use Depends(get_db) instead of db: Session = None
    # The original code made FastAPI try to resolve Session as a Pydantic type
    db: Session = Depends(get_db),
) -> Tenant:
    """Validate API key and return tenant"""
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
```

**Create `src/middleware/rate_limiter.py`:**

```python
from fastapi import Request, HTTPException, status
from src.core.redis_client import redis_client
from src.core.models import Tenant
import structlog

logger = structlog.get_logger()

async def check_rate_limit(tenant: Tenant):
    """Check if tenant has exceeded rate limit"""
    is_allowed, remaining = await redis_client.check_rate_limit(
        tenant.id,
        tenant.rate_limit
    )
    
    if not is_allowed:
        logger.warning(
            "Rate limit exceeded",
            tenant_id=tenant.id,
            limit=tenant.rate_limit
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Limit: {tenant.rate_limit} requests/minute",
            headers={"Retry-After": "60"}
        )
    
    return remaining
```

### Step 2.3: Main API Routes

**Create `src/api/completions.py`:**

```python
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from datetime import datetime
import time
import structlog

from src.core.database import get_db
from src.core.models import Tenant, Request as RequestLog
from src.core.redis_client import redis_client
from src.middleware.auth import get_current_tenant
from src.middleware.rate_limiter import check_rate_limit
from src.providers.base import LLMRequest
from src.providers.provider_factory import ProviderFactory
from src.core.config import get_settings

router = APIRouter()
logger = structlog.get_logger()
settings = get_settings()

@router.post("/completions")
async def create_completion(
    llm_request: LLMRequest,
    request: Request,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Main completion endpoint with:
    - Authentication
    - Rate limiting
    - Caching
    - Provider fallback
    - Cost tracking
    - Audit logging
    """
    
    # Check rate limit
    remaining = await check_rate_limit(tenant)
    
    # Generate cache key
    cache_key = redis_client.generate_cache_key(
        tenant.id,
        "any",  # Provider-agnostic caching
        llm_request.model,
        str(llm_request.messages)
    )
    
    # Check cache
    cached_response = await redis_client.get_cache(cache_key)
    if cached_response:
        logger.info("Cache hit", tenant_id=tenant.id, cache_key=cache_key)
        
        # Log cached request
        request_log = RequestLog(
            tenant_id=tenant.id,
            provider="cached",
            model=llm_request.model,
            status="success",
            cache_hit=1,
            created_at=datetime.utcnow()
        )
        db.add(request_log)
        db.commit()
        
        return {
            "cached": True,
            "response": cached_response,
            "rate_limit_remaining": remaining
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
                tenant_id=tenant.id
            )
            
            response = await provider.complete(llm_request)
            
            # Calculate cost
            cost = provider.calculate_cost(
                response.prompt_tokens,
                response.completion_tokens
            )
            
            # Cache the response
            await redis_client.set_cache(cache_key, {
                "content": response.content,
                "model": response.model,
                "provider": response.provider
            })
            
            break
            
        except Exception as e:
            logger.error(
                "Provider failed",
                provider=provider_name,
                error=str(e),
                tenant_id=tenant.id
            )
            error_message = str(e)
            continue
    
    if not response:
        raise HTTPException(
            status_code=503,
            detail=f"All providers failed. Last error: {error_message}"
        )
    
    # Calculate latency
    latency_ms = int((time.time() - start_time) * 1000)
    
    # Log request
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
        created_at=datetime.utcnow()
    )
    db.add(request_log)
    db.commit()
    
    logger.info(
        "Completion successful",
        tenant_id=tenant.id,
        provider=response.provider,
        tokens=response.total_tokens,
        cost=cost,
        latency_ms=latency_ms
    )
    
    return {
        "cached": False,
        "response": response.model_dump(),  # FIX: .dict() is deprecated in Pydantic v2
        "cost": cost,
        "latency_ms": latency_ms,
        "rate_limit_remaining": remaining
    }
```

**Create `src/api/admin.py` (Admin Routes):**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from src.core.database import get_db
from src.core.models import Tenant, Request as RequestLog, UsageLog
import secrets

router = APIRouter(prefix="/admin")

@router.post("/tenants")
async def create_tenant(
    name: str,
    rate_limit: int = 100,
    monthly_budget: float = None,
    db: Session = Depends(get_db)
):
    """Create a new tenant"""
    api_key = f"llm-gw-{secrets.token_urlsafe(32)}"
    
    tenant = Tenant(
        name=name,
        api_key=api_key,
        rate_limit=rate_limit,
        monthly_budget=monthly_budget
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    
    return {
        "tenant_id": tenant.id,
        "name": tenant.name,
        "api_key": api_key,
        "rate_limit": tenant.rate_limit
    }

@router.get("/tenants/{tenant_id}/usage")
async def get_tenant_usage(
    tenant_id: str,
    days: int = 30,
    db: Session = Depends(get_db)
):
    """Get usage statistics for a tenant"""
    start_date = datetime.utcnow() - timedelta(days=days)
    
    usage = db.query(
        func.count(RequestLog.id).label("total_requests"),
        func.sum(RequestLog.total_tokens).label("total_tokens"),
        func.sum(RequestLog.cost).label("total_cost"),
        func.avg(RequestLog.latency_ms).label("avg_latency_ms"),
        RequestLog.provider
    ).filter(
        RequestLog.tenant_id == tenant_id,
        RequestLog.created_at >= start_date
    ).group_by(RequestLog.provider).all()
    
    return {
        "tenant_id": tenant_id,
        "period_days": days,
        "usage_by_provider": [
            {
                "provider": row.provider,
                "requests": row.total_requests,
                "tokens": row.total_tokens or 0,
                "cost": float(row.total_cost or 0),
                "avg_latency_ms": float(row.avg_latency_ms or 0)
            }
            for row in usage
        ]
    }
```

### Step 2.4: Main Application

**Create `src/main.py`:**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import structlog

from src.api import completions, admin
from src.core.config import get_settings
from src.core.redis_client import redis_client
from src.core.database import engine, Base

settings = get_settings()

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
)

logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting LLM Gateway")
    await redis_client.connect()
    Base.metadata.create_all(bind=engine)
    yield
    # Shutdown
    logger.info("Shutting down LLM Gateway")
    await redis_client.disconnect()

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(completions.router, prefix=settings.API_V1_STR, tags=["completions"])
app.include_router(admin.router, prefix=settings.API_V1_STR, tags=["admin"])

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "llm-gateway"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
```

---

## Phase 3: Local Testing & Docker (Week 3-4)

### Step 3.1: Docker Setup

**Create `Dockerfile`:**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini .

# Run migrations and start app
CMD alembic upgrade head && uvicorn src.main:app --host 0.0.0.0 --port 8000
```

**Create `docker-compose.yml`:**

```yaml
# FIX: removed deprecated 'version' key — modern Docker Compose infers it
services:
  gateway:
    build: .
    ports:
      - "8000:8000"
    environment:
      - REDIS_HOST=redis
      - POSTGRES_HOST=postgres
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    depends_on:
      - redis
      - postgres
    volumes:
      - ./src:/app/src
    command: uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB=llm_gateway
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus

volumes:
  redis_data:
  postgres_data:
  prometheus_data:
```

### Step 3.2: Testing

> **FIX:** The original tests required a running Postgres and Redis, and didn't mock LLM
> providers. The corrected version below uses SQLite in-memory with `StaticPool`, mocks Redis,
> and mocks provider responses so tests run standalone with no external dependencies.

**Create `tests/conftest.py`** (shared fixtures):

```python
import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# StaticPool ensures all connections share the same in-memory SQLite database
TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=TEST_ENGINE)

# Patch database module BEFORE app imports use engine/SessionLocal
import src.core.database as db_module
db_module.engine = TEST_ENGINE
db_module.SessionLocal = TestSession

from src.core.database import Base, get_db
from src.core.models import Tenant
from src.main import app


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=TEST_ENGINE)
    yield
    Base.metadata.drop_all(bind=TEST_ENGINE)


@pytest.fixture
def db():
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_tenant(db):
    tenant = Tenant(name="Test Tenant", api_key="test-api-key", rate_limit=100)
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


@pytest.fixture
def mock_redis():
    mock = AsyncMock()
    mock.check_rate_limit = AsyncMock(return_value=(True, 99))
    mock.get_cache = AsyncMock(return_value=None)
    mock.set_cache = AsyncMock()
    mock.generate_cache_key = lambda *a: "test-cache-key"
    with patch("src.api.completions.redis_client", mock), \
         patch("src.middleware.rate_limiter.redis_client", mock):
        yield mock


@pytest.fixture
def client():
    with patch("src.main.redis_client") as mock_rc:
        mock_rc.connect = AsyncMock()
        mock_rc.disconnect = AsyncMock()
        from fastapi.testclient import TestClient
        with TestClient(app) as c:
            yield c
```

**Create `tests/test_completions.py`:**

```python
from unittest.mock import AsyncMock, patch
from src.providers.base import LLMResponse


def test_missing_api_key(client):
    response = client.post("/api/v1/completions", json={
        "model": "gpt-4", "messages": [{"role": "user", "content": "Hello"}],
    })
    assert response.status_code == 401


def test_successful_completion(client, test_tenant, mock_redis):
    fake_response = LLMResponse(
        content="Hello!", model="gpt-4", prompt_tokens=10,
        completion_tokens=8, total_tokens=18,
        finish_reason="stop", provider="openai",
    )
    mock_provider = AsyncMock()
    mock_provider.complete = AsyncMock(return_value=fake_response)
    mock_provider.calculate_cost = lambda pt, ct: (pt + ct) / 1000 * 0.002

    with patch("src.api.completions.ProviderFactory.get_provider",
               return_value=mock_provider):
        response = client.post("/api/v1/completions", json={
            "model": "gpt-4", "messages": [{"role": "user", "content": "Hello"}],
        }, headers={"X-API-Key": "test-api-key"})

    assert response.status_code == 200
    data = response.json()
    assert data["cached"] is False
    assert "cost" in data


def test_rate_limit_exceeded(client, test_tenant, mock_redis):
    mock_redis.check_rate_limit = AsyncMock(return_value=(False, 0))
    response = client.post("/api/v1/completions", json={
        "model": "gpt-4", "messages": [{"role": "user", "content": "Hello"}],
    }, headers={"X-API-Key": "test-api-key"})
    assert response.status_code == 429
```

**Run tests:**
```bash
pytest tests/ -v --cov=src
```

---

## Phase 4: Kubernetes Deployment (Week 4-5)

### Step 4.1: Kubernetes Manifests

**Create `k8s/namespace.yaml`:**

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: llm-gateway
```

**Create `k8s/configmap.yaml`:**

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: llm-gateway-config
  namespace: llm-gateway
data:
  REDIS_HOST: "redis-service"
  POSTGRES_HOST: "postgres-service"
  API_V1_STR: "/api/v1"
  DEFAULT_RATE_LIMIT: "100"
  CACHE_TTL: "3600"
  LOG_LEVEL: "INFO"
```

**Create `k8s/secrets.yaml`:**

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: llm-gateway-secrets
  namespace: llm-gateway
type: Opaque
stringData:
  OPENAI_API_KEY: "your-openai-key"
  ANTHROPIC_API_KEY: "your-anthropic-key"
  SECRET_KEY: "your-secret-key"
  POSTGRES_PASSWORD: "your-postgres-password"
```

**Create `k8s/deployment.yaml`:**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: llm-gateway
  namespace: llm-gateway
spec:
  replicas: 3
  selector:
    matchLabels:
      app: llm-gateway
  template:
    metadata:
      labels:
        app: llm-gateway
    spec:
      containers:
      - name: gateway
        image: your-registry/llm-gateway:latest
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: llm-gateway-config
        - secretRef:
            name: llm-gateway-secrets
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: llm-gateway-service
  namespace: llm-gateway
spec:
  selector:
    app: llm-gateway
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

**Create `k8s/redis.yaml`:**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: llm-gateway
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        ports:
        - containerPort: 6379
        resources:
          requests:
            memory: "128Mi"
            cpu: "100m"
---
apiVersion: v1
kind: Service
metadata:
  name: redis-service
  namespace: llm-gateway
spec:
  selector:
    app: redis
  ports:
  - port: 6379
    targetPort: 6379
```

**Create `k8s/postgres.yaml`:**

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
  namespace: llm-gateway
spec:
  serviceName: postgres-service
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgres:15-alpine
        ports:
        - containerPort: 5432
        env:
        - name: POSTGRES_DB
          value: llm_gateway
        - name: POSTGRES_USER
          value: postgres
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: llm-gateway-secrets
              key: POSTGRES_PASSWORD
        volumeMounts:
        - name: postgres-storage
          mountPath: /var/lib/postgresql/data
  volumeClaimTemplates:
  - metadata:
      name: postgres-storage
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 10Gi
---
apiVersion: v1
kind: Service
metadata:
  name: postgres-service
  namespace: llm-gateway
spec:
  selector:
    app: postgres
  ports:
  - port: 5432
    targetPort: 5432
```

### Step 4.2: Terraform Infrastructure

**Create `terraform/main.tf`:**

```hcl
terraform {
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.0"
    }
  }
}

provider "kubernetes" {
  config_path = "~/.kube/config"
}

provider "helm" {
  kubernetes {
    config_path = "~/.kube/config"
  }
}

# Create namespace
resource "kubernetes_namespace" "llm_gateway" {
  metadata {
    name = "llm-gateway"
  }
}

# ConfigMap
resource "kubernetes_config_map" "gateway_config" {
  metadata {
    name      = "llm-gateway-config"
    namespace = kubernetes_namespace.llm_gateway.metadata[0].name
  }

  data = {
    REDIS_HOST         = "redis-service"
    POSTGRES_HOST      = "postgres-service"
    API_V1_STR         = "/api/v1"
    DEFAULT_RATE_LIMIT = "100"
    CACHE_TTL          = "3600"
    LOG_LEVEL          = "INFO"
  }
}

# Secrets (use variables in production)
resource "kubernetes_secret" "gateway_secrets" {
  metadata {
    name      = "llm-gateway-secrets"
    namespace = kubernetes_namespace.llm_gateway.metadata[0].name
  }

  data = {
    OPENAI_API_KEY    = var.openai_api_key
    ANTHROPIC_API_KEY = var.anthropic_api_key
    SECRET_KEY        = var.secret_key
    POSTGRES_PASSWORD = var.postgres_password
  }
}

# Gateway Deployment
resource "kubernetes_deployment" "gateway" {
  metadata {
    name      = "llm-gateway"
    namespace = kubernetes_namespace.llm_gateway.metadata[0].name
  }

  spec {
    replicas = 3

    selector {
      match_labels = {
        app = "llm-gateway"
      }
    }

    template {
      metadata {
        labels = {
          app = "llm-gateway"
        }
      }

      spec {
        container {
          name  = "gateway"
          image = var.gateway_image

          port {
            container_port = 8000
          }

          env_from {
            config_map_ref {
              name = kubernetes_config_map.gateway_config.metadata[0].name
            }
          }

          env_from {
            secret_ref {
              name = kubernetes_secret.gateway_secrets.metadata[0].name
            }
          }

          resources {
            requests = {
              memory = "256Mi"
              cpu    = "250m"
            }
            limits = {
              memory = "512Mi"
              cpu    = "500m"
            }
          }

          liveness_probe {
            http_get {
              path = "/health"
              port = 8000
            }
            initial_delay_seconds = 30
            period_seconds        = 10
          }

          readiness_probe {
            http_get {
              path = "/health"
              port = 8000
            }
            initial_delay_seconds = 5
            period_seconds        = 5
          }
        }
      }
    }
  }
}

# Gateway Service
resource "kubernetes_service" "gateway" {
  metadata {
    name      = "llm-gateway-service"
    namespace = kubernetes_namespace.llm_gateway.metadata[0].name
  }

  spec {
    selector = {
      app = "llm-gateway"
    }

    port {
      port        = 80
      target_port = 8000
    }

    type = "LoadBalancer"
  }
}

# Output the service endpoint
output "gateway_endpoint" {
  value = kubernetes_service.gateway.status[0].load_balancer[0].ingress[0].ip
}
```

**Create `terraform/variables.tf`:**

```hcl
variable "openai_api_key" {
  description = "OpenAI API Key"
  type        = string
  sensitive   = true
}

variable "anthropic_api_key" {
  description = "Anthropic API Key"
  type        = string
  sensitive   = true
}

variable "secret_key" {
  description = "Application Secret Key"
  type        = string
  sensitive   = true
}

variable "postgres_password" {
  description = "PostgreSQL Password"
  type        = string
  sensitive   = true
}

variable "gateway_image" {
  description = "Docker image for LLM Gateway"
  type        = string
  default     = "llm-gateway:latest"
}
```

**Create `terraform/terraform.tfvars.example`:**

```hcl
openai_api_key    = "sk-..."
anthropic_api_key = "sk-ant-..."
secret_key        = "your-secret-key"
postgres_password = "your-postgres-password"
gateway_image     = "your-registry/llm-gateway:v1.0.0"
```

---

## Phase 5: Monitoring & Observability (Week 5-6)

### Step 5.1: Prometheus Metrics

**Create `src/core/metrics.py`:**

```python
from prometheus_client import Counter, Histogram, Gauge
from prometheus_client import make_asgi_app

# Request metrics
request_count = Counter(
    'llm_gateway_requests_total',
    'Total requests',
    ['tenant_id', 'provider', 'status']
)

request_latency = Histogram(
    'llm_gateway_request_duration_seconds',
    'Request latency',
    ['provider']
)

token_usage = Counter(
    'llm_gateway_tokens_total',
    'Total tokens used',
    ['tenant_id', 'provider', 'type']  # type: prompt or completion
)

cost_total = Counter(
    'llm_gateway_cost_total',
    'Total cost in USD',
    ['tenant_id', 'provider']
)

cache_hits = Counter(
    'llm_gateway_cache_hits_total',
    'Cache hits',
    ['tenant_id']
)

rate_limit_exceeded = Counter(
    'llm_gateway_rate_limit_exceeded_total',
    'Rate limit exceeded',
    ['tenant_id']
)

active_requests = Gauge(
    'llm_gateway_active_requests',
    'Active requests',
    ['provider']
)
```

**Update `src/main.py` to include metrics:**

```python
# FIX: import make_asgi_app from prometheus_client, not from src.core.metrics
from prometheus_client import make_asgi_app

# Mount Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)
```

**Create `prometheus.yml`:**

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'llm-gateway'
    static_configs:
      - targets: ['gateway:8000']
```

### Step 5.2: Grafana Dashboard

**Create `grafana/dashboards/llm-gateway.json`:** (abbreviated)

```json
{
  "dashboard": {
    "title": "LLM Gateway Metrics",
    "panels": [
      {
        "title": "Requests per Minute",
        "targets": [
          {
            "expr": "rate(llm_gateway_requests_total[1m])"
          }
        ]
      },
      {
        "title": "Cost by Tenant",
        "targets": [
          {
            "expr": "sum by (tenant_id) (llm_gateway_cost_total)"
          }
        ]
      },
      {
        "title": "Cache Hit Rate",
        "targets": [
          {
            "expr": "rate(llm_gateway_cache_hits_total[5m]) / rate(llm_gateway_requests_total[5m])"
          }
        ]
      }
    ]
  }
}
```

---

## Phase 6: Documentation & Polish (Week 6)

### Step 6.1: API Documentation

**Create `docs/API.md`:**

```markdown
# LLM Gateway API Documentation

## Authentication

All requests require an API key in the header:
```
X-API-Key: your-api-key
```

## Endpoints

### POST /api/v1/completions

Create a completion request.

**Request Body:**
```json
{
  "model": "gpt-4",
  "messages": [
    {"role": "user", "content": "Hello"}
  ],
  "temperature": 0.7,
  "max_tokens": 1000
}
```

**Response:**
```json
{
  "cached": false,
  "response": {
    "content": "Hello! How can I help you?",
    "model": "gpt-4",
    "prompt_tokens": 10,
    "completion_tokens": 8,
    "total_tokens": 18,
    "provider": "openai"
  },
  "cost": 0.00036,
  "latency_ms": 1250,
  "rate_limit_remaining": 99
}
```

### POST /api/v1/admin/tenants

Create a new tenant (admin only).

### GET /api/v1/admin/tenants/{tenant_id}/usage

Get usage statistics for a tenant.
```

### Step 6.2: README

**Create `README.md`:**

```markdown
# Multi-Tenant LLM Gateway

Production-ready API gateway for LLM providers with enterprise features.

## Features

✅ **Multi-Provider Support** - OpenAI, Anthropic, local models
✅ **Automatic Fallback** - Switch providers on failure
✅ **Rate Limiting** - Per-tenant rate limits
✅ **Cost Tracking** - Real-time cost attribution
✅ **Prompt Caching** - Redis-based semantic caching
✅ **Audit Logging** - Complete request/response logs
✅ **Monitoring** - Prometheus metrics & Grafana dashboards

## Quick Start

### Local Development

```bash
# Clone and setup
git clone <your-repo>
cd llm-gateway
cp .env.example .env
# Edit .env with your API keys

# Run with Docker Compose
docker-compose up -d

# Create a tenant
curl -X POST http://localhost:8000/api/v1/admin/tenants \
  -H "Content-Type: application/json" \
  -d '{"name": "My App", "rate_limit": 100}'

# Make a request
curl -X POST http://localhost:8000/api/v1/completions \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

### Kubernetes Deployment

```bash
# Using kubectl
kubectl apply -f k8s/

# Using Terraform
cd terraform
terraform init
terraform apply
```

## Architecture

[Include your architecture diagram]

## Monitoring

Access Grafana at `http://localhost:3000`
Access Prometheus at `http://localhost:9090`

## Testing

```bash
pytest tests/ -v --cov=src
```

## License

MIT
```

---

## Additional Learning Resources

### Core Technologies
1. **FastAPI**: https://fastapi.tiangolo.com/tutorial/
2. **Redis**: https://redis.io/docs/getting-started/
3. **PostgreSQL**: https://www.postgresql.org/docs/
4. **Kubernetes**: https://kubernetes.io/docs/tutorials/
5. **Terraform**: https://learn.hashicorp.com/terraform

### Advanced Topics
1. **Distributed Systems**: "Designing Data-Intensive Applications" by Martin Kleppmann
2. **API Gateway Patterns**: https://microservices.io/patterns/apigateway.html
3. **Rate Limiting Algorithms**: https://redis.io/glossary/rate-limiting/
4. **Multi-tenancy**: https://docs.microsoft.com/en-us/azure/architecture/guide/multitenant/overview

### LLM-Specific
1. **OpenAI Best Practices**: https://platform.openai.com/docs/guides/production-best-practices
2. **Anthropic API Docs**: https://docs.anthropic.com/
3. **Token Counting**: https://github.com/openai/tiktoken
4. **Prompt Engineering**: https://www.promptingguide.ai/

### Monitoring & Observability
1. **Prometheus**: https://prometheus.io/docs/introduction/overview/
2. **Grafana**: https://grafana.com/docs/
3. **Structured Logging**: https://www.structlog.org/

---

## Project Milestones & Checkpoints

### Week 1-2: Foundation
- [ ] Project setup complete
- [ ] Database models created
- [ ] Basic API structure
- [ ] Local development working

### Week 2-3: Core Features
- [ ] Provider abstraction implemented
- [ ] Rate limiting working
- [ ] Caching functional
- [ ] Fallback mechanism tested

### Week 3-4: Testing & Docker
- [ ] Unit tests written (>70% coverage)
- [ ] Integration tests
- [ ] Docker compose working
- [ ] Local end-to-end test

### Week 4-5: Kubernetes
- [ ] K8s manifests created
- [ ] Terraform modules written
- [ ] Deployed to local/dev cluster
- [ ] Health checks passing

### Week 5-6: Polish
- [ ] Monitoring setup
- [ ] Documentation complete
- [ ] README with examples
- [ ] Blog post written

---

## Tips for Success

1. **Start Small**: Get basic completion endpoint working first
2. **Test Early**: Write tests as you build features
3. **Use Docker**: Simplifies dependency management
4. **Log Everything**: Makes debugging easier
5. **Iterate**: Don't try to build everything at once

## Common Pitfalls to Avoid

❌ Not handling API errors properly
❌ Ignoring rate limit headers from providers
❌ Not implementing circuit breakers
❌ Forgetting to close database connections
❌ Hardcoding secrets

## What Makes This Project Stand Out

1. **Production-Ready**: Not a toy project
2. **Your Expertise**: Leverages your IaC/infra background
3. **Real Problem**: Something AI teams actually need
4. **Measurable Impact**: Show cost savings, latency improvements
5. **Open Source**: Can share and get feedback

---

## Next Steps After Completion

1. **Blog Post**: Write about architecture decisions
2. **Video Demo**: Record a walkthrough
3. **Open Source**: Share on GitHub
4. **Case Study**: Document real usage metrics
5. **Present**: Local meetup or HashiCorp internal talk

Good luck! This project will demonstrate exactly what AI Infrastructure Engineers need to know.
```
