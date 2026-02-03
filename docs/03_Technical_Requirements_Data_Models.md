# Technical Requirements & Data Models
# Multi-Tenant LLM Gateway
## Version 1.0 | Local Deployment Edition

---

**Document Owner:** Infrastructure Engineering Team  
**Date:** February 2026  
**Status:** Draft - For Implementation

---

## Table of Contents

1. [System Requirements](#1-system-requirements)
2. [Data Models](#2-data-models)
3. [API Contracts](#3-api-contracts)
4. [Configuration Specifications](#4-configuration-specifications)
5. [Integration Requirements](#5-integration-requirements)
6. [Testing Requirements](#6-testing-requirements)
7. [Performance Requirements](#7-performance-requirements)
8. [Security Requirements](#8-security-requirements)

---

## 1. System Requirements

### 1.1 Development Environment

**Hardware Requirements:**
| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 2 cores | 4+ cores |
| RAM | 8 GB | 16 GB |
| Storage | 20 GB free | 50 GB free |
| Network | Broadband | Broadband |

**Software Requirements:**
| Software | Version | Purpose |
|----------|---------|---------|
| Docker Desktop | 24.0+ | Container runtime |
| Python | 3.11+ | Application runtime |
| Git | 2.40+ | Version control |
| curl/Postman | Latest | API testing |

**Optional Tools:**
| Tool | Version | Purpose |
|------|---------|---------|
| minikube | 1.32+ | Local Kubernetes |
| kind | 0.20+ | Local Kubernetes |
| Terraform | 1.6+ | Infrastructure automation |
| kubectl | 1.28+ | Kubernetes management |

### 1.2 Production Environment

**Kubernetes Cluster:**
- Version: 1.28+
- Node Count: 3+ (for HA)
- Node Size: 2 vCPU, 4GB RAM minimum per node

**Managed Services (Optional):**
- Cloud SQL / RDS for PostgreSQL
- ElastiCache / MemoryStore for Redis
- Cloud Load Balancer

### 1.3 External Service Requirements

**Required:**
- Internet connectivity for LLM provider APIs
- Valid API keys for at least one provider (OpenAI or Anthropic)

**Optional:**
- SMTP server for email notifications
- Slack webhook for alerting
- External monitoring service

---

## 2. Data Models

### 2.1 Entity Relationship Diagram

```
┌─────────────────────────────┐
│         Tenants             │
├─────────────────────────────┤
│ PK  id                      │
│     name                    │
│ UQ  api_key_hash            │
│     rate_limit              │
│     monthly_budget          │
│     is_active               │
│     created_at              │
│     updated_at              │
└──────────────┬──────────────┘
               │ 1
               │
               │ N
┌──────────────┴──────────────┐
│         Requests            │
├─────────────────────────────┤
│ PK  id                      │
│ FK  tenant_id               │
│     provider                │
│     model                   │
│     prompt_tokens           │
│     completion_tokens       │
│     total_tokens            │
│     cost                    │
│     latency_ms              │
│     status                  │
│     error_message           │
│     cache_hit               │
│     created_at              │
│                             │
│ IDX (tenant_id, created_at) │
│ IDX (provider, status)      │
└─────────────────────────────┘
               │ 1
               │
               │ N
┌──────────────┴──────────────┐
│        Usage Logs           │
├─────────────────────────────┤
│ PK  id                      │
│ FK  tenant_id               │
│     date                    │
│     total_requests          │
│     total_tokens            │
│     total_cost              │
│     provider_breakdown      │
│                             │
│ IDX (tenant_id, date)       │
└─────────────────────────────┘
```

### 2.2 Tenant Model

**Purpose:** Represents an application or team using the gateway

**Schema:**
```sql
CREATE TABLE tenants (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name              VARCHAR(255) NOT NULL,
    api_key_hash      VARCHAR(64) UNIQUE NOT NULL,
    rate_limit        INTEGER NOT NULL DEFAULT 100,
    monthly_budget    DECIMAL(10, 2),
    is_active         BOOLEAN NOT NULL DEFAULT true,
    created_at        TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_tenants_active ON tenants(is_active) WHERE is_active = true;
```

**Field Specifications:**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, NOT NULL | Unique tenant identifier |
| name | VARCHAR(255) | NOT NULL | Display name for tenant |
| api_key_hash | VARCHAR(64) | UNIQUE, NOT NULL | SHA-256 hash of API key |
| rate_limit | INTEGER | NOT NULL, DEFAULT 100 | Requests per minute |
| monthly_budget | DECIMAL(10,2) | NULL | Optional spending cap (USD) |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | Enable/disable tenant |
| created_at | TIMESTAMP | NOT NULL | Creation timestamp |
| updated_at | TIMESTAMP | NOT NULL | Last update timestamp |

**Business Rules:**
- API key must be 32+ characters
- Rate limit must be between 1 and 10,000
- Monthly budget, if set, must be positive
- Inactive tenants cannot make requests

**Validation Logic:**
```python
class TenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    rate_limit: int = Field(ge=1, le=10000, default=100)
    monthly_budget: Optional[float] = Field(ge=0.01)
    
    @validator('name')
    def name_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError('Name cannot be empty')
        return v.strip()
```

### 2.3 Request Model

**Purpose:** Log every LLM API request for auditing and cost tracking

**Schema:**
```sql
CREATE TABLE requests (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    provider            VARCHAR(50) NOT NULL,
    model               VARCHAR(100) NOT NULL,
    prompt_tokens       INTEGER NOT NULL DEFAULT 0,
    completion_tokens   INTEGER NOT NULL DEFAULT 0,
    total_tokens        INTEGER NOT NULL DEFAULT 0,
    cost                DECIMAL(10, 6) NOT NULL DEFAULT 0.0,
    latency_ms          INTEGER,
    status              VARCHAR(20) NOT NULL,
    error_message       TEXT,
    cache_hit           BOOLEAN NOT NULL DEFAULT false,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_requests_tenant_created ON requests(tenant_id, created_at DESC);
CREATE INDEX idx_requests_provider_status ON requests(provider, status);
CREATE INDEX idx_requests_created ON requests(created_at DESC);
```

**Field Specifications:**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, NOT NULL | Unique request identifier |
| tenant_id | UUID | FK, NOT NULL | Reference to tenant |
| provider | VARCHAR(50) | NOT NULL | Provider used (openai, anthropic, local) |
| model | VARCHAR(100) | NOT NULL | Model name (gpt-4, claude-3-opus, etc) |
| prompt_tokens | INTEGER | NOT NULL, >= 0 | Input tokens consumed |
| completion_tokens | INTEGER | NOT NULL, >= 0 | Output tokens generated |
| total_tokens | INTEGER | NOT NULL, >= 0 | Sum of prompt + completion |
| cost | DECIMAL(10,6) | NOT NULL, >= 0 | Calculated cost in USD |
| latency_ms | INTEGER | NULL, > 0 | Time to complete request |
| status | VARCHAR(20) | NOT NULL | success, error, cached |
| error_message | TEXT | NULL | Error details if status=error |
| cache_hit | BOOLEAN | NOT NULL | Whether response came from cache |
| created_at | TIMESTAMP | NOT NULL | Request timestamp |

**Status Values:**
- `success`: Request completed successfully
- `error`: Request failed (provider error, validation, etc)
- `cached`: Response served from cache
- `rate_limited`: Blocked by rate limiter

**Validation Logic:**
```python
class RequestLog(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    provider: Literal["openai", "anthropic", "local", "cached"]
    model: str = Field(min_length=1, max_length=100)
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    cost: Decimal = Field(ge=0, decimal_places=6)
    latency_ms: Optional[int] = Field(gt=0)
    status: Literal["success", "error", "cached", "rate_limited"]
    error_message: Optional[str]
    cache_hit: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    @validator('total_tokens')
    def total_equals_sum(cls, v, values):
        if 'prompt_tokens' in values and 'completion_tokens' in values:
            expected = values['prompt_tokens'] + values['completion_tokens']
            if v != expected:
                raise ValueError(f'total_tokens must equal prompt + completion')
        return v
```

### 2.4 Usage Log Model

**Purpose:** Daily aggregated usage statistics per tenant

**Schema:**
```sql
CREATE TABLE usage_logs (
    id                    SERIAL PRIMARY KEY,
    tenant_id             UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    date                  DATE NOT NULL,
    total_requests        INTEGER NOT NULL DEFAULT 0,
    total_tokens          BIGINT NOT NULL DEFAULT 0,
    total_cost            DECIMAL(10, 2) NOT NULL DEFAULT 0.0,
    provider_breakdown    JSONB NOT NULL DEFAULT '{}',
    created_at            TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT unique_tenant_date UNIQUE (tenant_id, date)
);

CREATE INDEX idx_usage_logs_tenant_date ON usage_logs(tenant_id, date DESC);
```

**Field Specifications:**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | SERIAL | PK | Auto-incrementing ID |
| tenant_id | UUID | FK, NOT NULL | Reference to tenant |
| date | DATE | NOT NULL | Aggregation date |
| total_requests | INTEGER | NOT NULL, >= 0 | Total requests this day |
| total_tokens | BIGINT | NOT NULL, >= 0 | Total tokens consumed |
| total_cost | DECIMAL(10,2) | NOT NULL, >= 0 | Total cost in USD |
| provider_breakdown | JSONB | NOT NULL | Per-provider statistics |
| created_at | TIMESTAMP | NOT NULL | Log creation time |

**Provider Breakdown JSON Structure:**
```json
{
  "openai": {
    "requests": 1234,
    "tokens": 567890,
    "cost": 123.45,
    "models": {
      "gpt-4": {
        "requests": 800,
        "tokens": 450000,
        "cost": 100.00
      },
      "gpt-3.5-turbo": {
        "requests": 434,
        "tokens": 117890,
        "cost": 23.45
      }
    }
  },
  "anthropic": {
    "requests": 345,
    "tokens": 123456,
    "cost": 45.67,
    "models": {
      "claude-3-opus": {
        "requests": 200,
        "tokens": 89000,
        "cost": 35.00
      },
      "claude-3-sonnet": {
        "requests": 145,
        "tokens": 34456,
        "cost": 10.67
      }
    }
  }
}
```

### 2.5 Redis Data Structures

**Rate Limiting:**
```
Key:   rate_limit:{tenant_id}
Type:  String (integer counter)
Value: Current request count
TTL:   60 seconds (sliding window)

Example:
rate_limit:abc-123 → "47" (expires in 38 seconds)
```

**Response Caching:**
```
Key:   cache:{sha256_hash}
Type:  String (JSON)
Value: Cached LLM response
TTL:   3600 seconds (1 hour, configurable)

Example:
cache:a1b2c3d4e5f6... → '{"content":"...","model":"gpt-4","provider":"openai"}'
```

**Health Check Status:**
```
Key:   health:{provider_name}
Type:  String (JSON)
Value: Provider health status
TTL:   60 seconds

Example:
health:openai → '{"status":"healthy","last_check":"2026-02-02T10:30:00Z","latency_ms":234}'
```

---

## 3. API Contracts

### 3.1 Completion Request

**Endpoint:** `POST /api/v1/completions`

**Headers:**
```
Content-Type: application/json
X-API-Key: {tenant_api_key}
```

**Request Body Schema:**
```json
{
  "model": "gpt-4",
  "messages": [
    {
      "role": "system",
      "content": "You are a helpful assistant."
    },
    {
      "role": "user",
      "content": "What is the capital of France?"
    }
  ],
  "temperature": 0.7,
  "max_tokens": 1000,
  "stream": false
}
```

**Request Field Validation:**

| Field | Type | Required | Constraints | Default |
|-------|------|----------|-------------|---------|
| model | string | Yes | Non-empty, max 100 chars | - |
| messages | array | Yes | 1-100 messages | - |
| messages[].role | string | Yes | "system", "user", or "assistant" | - |
| messages[].content | string | Yes | Non-empty, max 100K chars | - |
| temperature | float | No | 0.0 - 2.0 | 0.7 |
| max_tokens | integer | No | 1 - 8000 | 1000 |
| stream | boolean | No | true or false | false |

**Success Response (200 OK):**
```json
{
  "cached": false,
  "response": {
    "content": "The capital of France is Paris.",
    "model": "gpt-4",
    "prompt_tokens": 23,
    "completion_tokens": 8,
    "total_tokens": 31,
    "finish_reason": "stop",
    "provider": "openai"
  },
  "cost": 0.00093,
  "latency_ms": 1247,
  "rate_limit_remaining": 99
}
```

**Response Field Descriptions:**

| Field | Type | Description |
|-------|------|-------------|
| cached | boolean | Whether response came from cache |
| response.content | string | LLM generated text |
| response.model | string | Actual model used |
| response.prompt_tokens | integer | Input tokens consumed |
| response.completion_tokens | integer | Output tokens generated |
| response.total_tokens | integer | Total tokens used |
| response.finish_reason | string | Why completion stopped |
| response.provider | string | Provider that fulfilled request |
| cost | float | Cost in USD (6 decimal places) |
| latency_ms | integer | Request duration in milliseconds |
| rate_limit_remaining | integer | Requests remaining this minute |

**Error Responses:**

**401 Unauthorized:**
```json
{
  "detail": "Invalid API key"
}
```

**429 Too Many Requests:**
```json
{
  "detail": "Rate limit exceeded. Limit: 100 requests/minute",
  "headers": {
    "Retry-After": "42"
  }
}
```

**503 Service Unavailable:**
```json
{
  "detail": "All providers failed. Last error: OpenAI timeout after 30s"
}
```

**422 Validation Error:**
```json
{
  "detail": [
    {
      "loc": ["body", "temperature"],
      "msg": "ensure this value is less than or equal to 2.0",
      "type": "value_error.number.not_le"
    }
  ]
}
```

### 3.2 Create Tenant

**Endpoint:** `POST /api/v1/admin/tenants`

**Headers:**
```
Content-Type: application/json
X-Admin-Key: {admin_api_key}  # Admin authentication
```

**Request Body:**
```json
{
  "name": "Engineering Team",
  "rate_limit": 100,
  "monthly_budget": 500.00
}
```

**Request Field Validation:**

| Field | Type | Required | Constraints | Default |
|-------|------|----------|-------------|---------|
| name | string | Yes | 1-255 chars, non-empty | - |
| rate_limit | integer | No | 1-10000 | 100 |
| monthly_budget | float | No | > 0 or null | null |

**Success Response (201 Created):**
```json
{
  "tenant_id": "abc-123-def-456",
  "name": "Engineering Team",
  "api_key": "llm-gw-abc123def456...",
  "rate_limit": 100,
  "monthly_budget": 500.00,
  "is_active": true,
  "created_at": "2026-02-02T10:30:00Z"
}
```

### 3.3 Get Tenant Usage

**Endpoint:** `GET /api/v1/admin/tenants/{tenant_id}/usage`

**Headers:**
```
X-Admin-Key: {admin_api_key}
```

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| days | integer | No | 30 | Number of days to analyze |
| provider | string | No | null | Filter by provider |

**Success Response (200 OK):**
```json
{
  "tenant_id": "abc-123-def-456",
  "tenant_name": "Engineering Team",
  "period_days": 30,
  "summary": {
    "total_requests": 1781,
    "total_tokens": 1016341,
    "total_cost": 203.27,
    "avg_latency_ms": 1156,
    "cache_hit_rate": 0.42
  },
  "usage_by_provider": [
    {
      "provider": "openai",
      "requests": 1547,
      "tokens": 892451,
      "cost": 178.49,
      "avg_latency_ms": 1203,
      "models": {
        "gpt-4": {
          "requests": 1200,
          "tokens": 750000,
          "cost": 150.00
        },
        "gpt-3.5-turbo": {
          "requests": 347,
          "tokens": 142451,
          "cost": 28.49
        }
      }
    },
    {
      "provider": "anthropic",
      "requests": 234,
      "tokens": 123890,
      "cost": 24.78,
      "avg_latency_ms": 987,
      "models": {
        "claude-3-opus": {
          "requests": 150,
          "tokens": 89000,
          "cost": 20.00
        },
        "claude-3-sonnet": {
          "requests": 84,
          "tokens": 34890,
          "cost": 4.78
        }
      }
    }
  ],
  "daily_breakdown": [
    {
      "date": "2026-02-02",
      "requests": 67,
      "tokens": 38945,
      "cost": 7.89
    },
    {
      "date": "2026-02-01",
      "requests": 54,
      "tokens": 31234,
      "cost": 6.25
    }
  ]
}
```

### 3.4 Health Check

**Endpoint:** `GET /health`

**Response (200 OK):**
```json
{
  "status": "healthy",
  "service": "llm-gateway",
  "version": "1.0.0",
  "timestamp": "2026-02-02T10:30:00Z"
}
```

**Response (503 Service Unavailable):**
```json
{
  "status": "unhealthy",
  "service": "llm-gateway",
  "errors": [
    "Database connection failed",
    "Redis unavailable"
  ],
  "timestamp": "2026-02-02T10:30:00Z"
}
```

---

## 4. Configuration Specifications

### 4.1 Environment Variables

**Required Variables:**

| Variable | Type | Example | Description |
|----------|------|---------|-------------|
| SECRET_KEY | string | `random-32-char-string` | Application secret for encryption |
| DATABASE_URL | string | `postgresql://user:pass@host:5432/db` | PostgreSQL connection string |
| REDIS_HOST | string | `localhost` | Redis server hostname |
| REDIS_PORT | integer | `6379` | Redis server port |

**Optional Variables:**

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| API_V1_STR | string | `/api/v1` | API version prefix |
| REDIS_PASSWORD | string | `null` | Redis authentication password |
| REDIS_DB | integer | `0` | Redis database number |
| OPENAI_API_KEY | string | `null` | OpenAI API key |
| ANTHROPIC_API_KEY | string | `null` | Anthropic API key |
| DEFAULT_RATE_LIMIT | integer | `100` | Default requests per minute |
| CACHE_TTL | integer | `3600` | Cache TTL in seconds |
| ENABLE_PROMPT_CACHE | boolean | `true` | Enable/disable caching |
| LOG_LEVEL | string | `INFO` | Logging level |
| ENABLE_METRICS | boolean | `true` | Enable Prometheus metrics |

### 4.2 Configuration File (Optional)

**Format:** YAML configuration file for advanced settings

```yaml
# config.yaml
gateway:
  name: "LLM Gateway"
  version: "1.0.0"
  environment: "production"

providers:
  fallback_order:
    - "openai"
    - "anthropic"
    - "local"
  
  openai:
    enabled: true
    models:
      - "gpt-4"
      - "gpt-3.5-turbo"
    timeout_seconds: 30
    max_retries: 3
    
  anthropic:
    enabled: true
    models:
      - "claude-3-opus-20240229"
      - "claude-3-sonnet-20240229"
    timeout_seconds: 30
    max_retries: 3

rate_limiting:
  default_limit: 100
  burst_allowance: 10
  window_seconds: 60

caching:
  enabled: true
  ttl_seconds: 3600
  max_size_mb: 1024
  eviction_policy: "lru"

monitoring:
  prometheus:
    enabled: true
    port: 9090
  
  logging:
    level: "INFO"
    format: "json"
    output: "stdout"
```

---

## 5. Integration Requirements

### 5.1 LLM Provider Integration

**OpenAI Integration:**
- SDK: `openai>=1.10.0`
- Authentication: API key in header
- Endpoint: `https://api.openai.com/v1/chat/completions`
- Rate limits: Respect `x-ratelimit-*` headers
- Error handling: Retry on 429, 500, 503

**Anthropic Integration:**
- SDK: `anthropic>=0.8.0`
- Authentication: `x-api-key` header
- Endpoint: `https://api.anthropic.com/v1/messages`
- Rate limits: Respect `anthropic-ratelimit-*` headers
- Error handling: Retry on 429, 529

**Local Model Integration:**
- Protocol: HTTP REST API
- Endpoint: Configurable base URL
- Format: OpenAI-compatible
- Health check: GET `/health`

### 5.2 Database Integration

**Connection Pooling:**
```python
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600
)
```

**Migration Management:**
- Tool: Alembic
- Version control: All migrations in Git
- Automated: Run on startup in Docker
- Manual: Separate command for production

### 5.3 Monitoring Integration

**Prometheus Metrics:**
- Exposition format: OpenMetrics
- Endpoint: `/metrics`
- Scrape interval: 15 seconds
- Cardinality limits: Monitor label values

**Grafana Dashboards:**
- Pre-built dashboard JSON
- Import via ConfigMap in Kubernetes
- Update frequency: Real-time (15s refresh)

---

## 6. Testing Requirements

### 6.1 Unit Testing

**Coverage Requirements:**
- Minimum: 70% code coverage
- Target: 80%+ code coverage
- Critical paths: 100% coverage

**Test Categories:**
- Model validation
- Business logic
- Cost calculations
- Cache key generation
- Rate limiting logic

**Example Test:**
```python
def test_cost_calculation():
    """Test accurate cost calculation for GPT-4"""
    provider = OpenAIProvider(api_key="test")
    cost = provider.calculate_cost(
        prompt_tokens=1000,
        completion_tokens=500
    )
    # GPT-4: $0.03/1K input + $0.06/1K output
    expected = (1000 * 0.03 / 1000) + (500 * 0.06 / 1000)
    assert cost == expected
```

### 6.2 Integration Testing

**Test Scenarios:**
1. End-to-end completion request
2. Rate limiting enforcement
3. Cache hit/miss behavior
4. Provider fallback mechanism
5. Database persistence
6. Metrics collection

**Test Environment:**
- Docker Compose for dependencies
- Mock LLM providers for controlled responses
- Test database separate from development

### 6.3 Load Testing

**Performance Benchmarks:**
- 100 concurrent users
- 1000 requests over 60 seconds
- Measure: P50, P95, P99 latency
- Acceptable error rate: <0.1%

**Tools:**
- Locust or k6 for load generation
- Prometheus for metrics collection
- Grafana for visualization

---

## 7. Performance Requirements

### 7.1 Response Time Targets

| Metric | Target | Critical Threshold |
|--------|--------|--------------------|
| Gateway Overhead | <100ms | <200ms |
| Cache Lookup | <10ms | <20ms |
| Database Query | <50ms | <100ms |
| Total Request (cache hit) | <150ms | <300ms |
| Total Request (cache miss) | Provider latency + 200ms | Provider latency + 500ms |

### 7.2 Throughput Targets

| Configuration | Target RPS | Notes |
|---------------|------------|-------|
| Single pod | 50-100 | Depends on cache hit rate |
| 3 pods | 150-300 | Kubernetes deployment |
| Auto-scaled | 500+ | With HPA |

### 7.3 Resource Utilization

**Per Gateway Pod:**
- CPU: <70% average utilization
- Memory: <80% of limit
- Database connections: <50% of pool
- Redis connections: <100 per pod

---

## 8. Security Requirements

### 8.1 Authentication & Authorization

**API Key Requirements:**
- Minimum length: 32 characters
- Character set: Base64 URL-safe
- Format: `llm-gw-{32-byte-base64}`
- Storage: SHA-256 hash in database
- Transmission: HTTPS only, in header

**Authorization Rules:**
- Tenants can only access their own data
- Admin endpoints require separate authentication
- No cross-tenant data access

### 8.2 Data Protection

**In Transit:**
- TLS 1.3 minimum
- Strong cipher suites only
- Certificate validation required
- No downgrade attacks

**At Rest:**
- Database encryption at rest
- Kubernetes secrets encrypted
- No plain text API keys in logs
- Secure credential rotation

**PII Handling:**
- No PII in logs by default
- Optional request/response logging (disabled in production)
- GDPR compliance considerations

### 8.3 Audit & Compliance

**Audit Logging:**
- All authentication attempts
- All API requests (metadata only)
- Configuration changes
- Admin actions

**Retention:**
- Request logs: 90 days minimum
- Usage logs: 365 days minimum
- Audit logs: 7 years (compliance)

---

## Appendix A: Sample Requests

### Create Tenant
```bash
curl -X POST http://localhost:8000/api/v1/admin/tenants \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: admin-secret-key" \
  -d '{
    "name": "Engineering Team",
    "rate_limit": 100,
    "monthly_budget": 500.00
  }'
```

### Make Completion Request
```bash
curl -X POST http://localhost:8000/api/v1/completions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: llm-gw-abc123..." \
  -d '{
    "model": "gpt-4",
    "messages": [
      {"role": "user", "content": "What is 2+2?"}
    ],
    "temperature": 0.7,
    "max_tokens": 100
  }'
```

### Get Usage Statistics
```bash
curl -X GET "http://localhost:8000/api/v1/admin/tenants/{tenant_id}/usage?days=30" \
  -H "X-Admin-Key: admin-secret-key"
```

---

## Appendix B: Database Indexes

```sql
-- Performance-critical indexes
CREATE INDEX CONCURRENTLY idx_requests_tenant_created 
  ON requests(tenant_id, created_at DESC);

CREATE INDEX CONCURRENTLY idx_requests_provider_status 
  ON requests(provider, status);

CREATE INDEX CONCURRENTLY idx_requests_created 
  ON requests(created_at DESC);

CREATE INDEX CONCURRENTLY idx_usage_logs_tenant_date 
  ON usage_logs(tenant_id, date DESC);

-- Partial index for active tenants only
CREATE INDEX CONCURRENTLY idx_tenants_active 
  ON tenants(is_active) 
  WHERE is_active = true;
```

---

**Document History:**

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Feb 2026 | Infrastructure Team | Initial release |

